# PostgreSQL local — Jaka chatbot

Esta etapa agrega persistencia operativa. No reemplaza ni copia el catálogo JSON existente.

## Qué guarda

- Contactos identificados por teléfono internacional normalizado (E.164).
- Conversaciones y modo: `bot_active`, `human` o `closed`.
- Mensajes entrantes, salientes e internos.
- ID externo del proveedor para deduplicar reintentos de webhooks.
- Pedidos y líneas como `pending_confirmation`.
- Auditoría de cambios de modo y creación de pedidos.

Los productos, precios y disponibilidad siguen consultándose en la API de catálogo. Los pedidos guardan una fotografía del nombre, precio y disponibilidad devueltos al momento de armarlos. No descuentan stock ni representan una venta confirmada.

## Requisitos Windows

1. Instalar Docker Desktop para Windows y esperar que indique que Docker está iniciado.
2. Desde PowerShell, en la raíz del repositorio, copiar la plantilla:

```powershell
Copy-Item bot/db/.env.example bot/db/.env
notepad bot/db/.env
```

3. Cambiar `POSTGRES_PASSWORD` por una clave larga y única. El archivo `.env` no debe subirse a Git.
4. Iniciar PostgreSQL:

```powershell
docker compose --env-file bot/db/.env -f bot/db/docker-compose.yml up -d
docker compose --env-file bot/db/.env -f bot/db/docker-compose.yml ps
```

El puerto queda enlazado solamente a `127.0.0.1`; no queda expuesto a la red local ni a Internet. Los datos persisten en el volumen Docker `jaka_postgres_data`.

## Verificar tablas

```powershell
docker exec -it jaka-chatbot-postgres psql -U jaka_bot -d jaka_chatbot -c "\dt"
```

Si cambiaste el usuario o la base en `.env`, reemplazá los valores del comando.

## Preparar Python

```powershell
py -3 -m pip install -r bot/db/requirements.txt
```

Configurar la conexión para la terminal actual (usar exactamente los valores de tu .env):

```powershell
$env:DATABASE_URL = "postgresql://jaka_bot:TU_CLAVE@127.0.0.1:5432/jaka_chatbot"
```

No pegues la contraseña en chats, capturas ni repositorios.

## API de repositorio

`repository.py` es una capa interna Python, no un endpoint HTTP público. Hoy no está conectada a
WhatsApp, n8n ni al servidor de catálogo.

| Función | Para qué |
|---|---|
| `get_or_create_contact(phone, nombre)` | Alta o actualización del contacto por teléfono E.164 |
| `get_or_create_conversation(contact_id)` | Devuelve la conversación abierta o crea una nueva |
| `save_message(...)` | Guarda un mensaje y deduplica por id externo del proveedor |
| `set_conversation_mode(id, modo, actor=)` | Alterna `bot_active` / `human` / `closed` con auditoría |
| `create_pending_order(...)` | Arma un pedido `pending_confirmation` con sus renglones |
| `get_recent_messages(conv, limit, include_internal=)` | Historial en orden cronológico, para el contexto del asistente |
| `get_conversation_history(contact_id)` | Conversación abierta + últimos mensajes en una sola llamada |
| `get_order(order_id)` | Pedido con sus renglones |
| `set_order_status(order_id, estado, actor=)` | Confirma, rechaza o cancela, con auditoría y transiciones controladas |

### Transiciones de pedido

```
pending_confirmation ──► confirmed ──► cancelled
        │
        ├──► rejected
        └──► cancelled
```

`rejected` y `cancelled` son finales: un pedido cancelado no se "des-cancela", se crea uno nuevo, así
queda la traza de qué pasó. Repetir el estado que ya tiene es idempotente, para que un reintento de n8n
no rompa ni duplique la auditoría. El cambio bloquea la fila con `FOR UPDATE`, así dos operadores
confirmando a la vez no generan dos eventos contradictorios.

Ningún cambio de estado descuenta stock ni cobra nada: el pedido es un registro comercial y la venta se
cierra por WhatsApp.

## Pruebas

Con PostgreSQL levantado y `DATABASE_URL` configurada en la terminal:

```powershell
py -3 -m pip install -r bot/db/requirements.txt
$env:DATABASE_URL = "postgresql://jaka_bot:TU_CLAVE@127.0.0.1:5432/jaka_chatbot"
py -m unittest discover -s bot/db/tests -t . -v
```

Son **35 pruebas contra la base real**, no contra un doble: alta idempotente de contactos, teléfono
inválido rechazado por el `CHECK`, una sola conversación abierta por contacto, apertura de una nueva al
cerrar la anterior, deduplicación de mensajes por id externo, auditoría del cambio bot/humano, subtotal
del pedido, **rollback completo** cuando un renglón falla después de insertar el pedido, orden
cronológico del historial, exclusión de mensajes internos, transiciones de estado inválidas y
confirmación concurrente del mismo pedido.

Los tests aplican `schema.sql` al empezar (es idempotente) y borran sus propios datos al terminar, así
que se pueden correr contra la base de desarrollo sin dejar basura. Sin `DATABASE_URL` se saltean en vez
de fallar.

### Validación realizada

- PostgreSQL **16.9**, la misma versión mayor que la imagen `postgres:16-alpine` del compose.
- Esquema aplicado sobre una base **vacía**: crea las 6 tablas y los 2 índices únicos parciales.
- 35/35 pruebas en verde, tres corridas seguidas.

Lo que **no** quedó probado: el `docker compose up` en sí (la máquina donde se validó no tiene Docker
Desktop) y el comportamiento con volumen persistente entre reinicios.

## Seguridad y operación

- No publicar el puerto 5432 ni habilitar conexiones remotas.
- No guardar tokens de Meta ni claves de IA en la base o en Git.
- Usar credenciales separadas para producción.
- Definir luego política de privacidad, retención y borrado de datos de clientes.
- Hacer copias de seguridad antes de actualizaciones importantes.
- `docker compose down` detiene el contenedor sin borrar datos.
- No ejecutar `docker compose down -v`: elimina el volumen y los datos persistidos.
- El esquema se ejecuta automáticamente solo al crear el volumen por primera vez. En instalaciones existentes, aplicar migraciones explícitas.

## Limitación de esta entrega

Es la base de persistencia local. No incluye aún panel web, API de conversaciones, automatizaciones, envío de mensajes ni integración real de WhatsApp.

