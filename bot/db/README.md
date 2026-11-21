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

`repository.py` ofrece funciones para crear/recuperar contactos y conversaciones, guardar mensajes idempotentes, cambiar el modo bot/humano y crear pedidos pendientes. Es una capa interna Python, no un endpoint HTTP público. Todavía no está conectada a WhatsApp, n8n ni al servidor de catálogo.

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
