# Especificación de implementación — Chatbot híbrido Jaka Bicicletería

## Decisiones confirmadas
- Desarrollo y primera operación en una computadora local.
- IA consumida mediante API externa; proveedor/modelo se configura en una fase posterior.
- Conservar +595 993 539 237 y WhatsApp Business App mediante coexistencia oficial de Meta, si el número es elegible.
- Reutilizar el repositorio y catálogos existentes.

## Arquitectura objetivo

WhatsApp Business App + Cloud API (coexistence)
→ webhook HTTPS público
→ n8n local (orquestación)
→ API local de catálogo (este módulo)
→ API de IA (intención y redacción)
→ respuesta por Cloud API.

PostgreSQL local se incorpora en una fase posterior para conversaciones, estados de atención, auditoría y pedidos. Los catálogos comerciales no se duplican en la base de datos: los JSON de tienda/data continúan siendo la fuente de verdad.

## Primera etapa: API de catálogo

Implementación en bot/api/server.py, Python estándar.

Fuentes:
- tienda/data/catalogo.json: bicicletas, accesorios, fitness e indumentaria.
- tienda/data/motos/v/todos.json: catálogo de motos.
- tienda/data/indice.json: fecha, fuente, categorías y metadatos.
- tienda/assets/config.js: recargo, redondeo y servicios publicados.

Rutas:
- GET /health
- GET /catalog/status
- GET /catalog/search?q=&type=&category=&limit=&offset=
- GET /catalog/product/{id}
- GET /catalog/categories
- GET /services

La búsqueda no llama a scrapers ni a la IA. Normaliza acentos y puntuación, consulta nombre, marca, SKU y categoría, y ordena coincidencias.

### Reglas comerciales obligatorias
- El precio de venta se calcula con la misma lógica de tienda/assets/app.js: recargo configurado y redondeo hacia arriba según el tramo.
- La API devuelve source_price y price. El asistente muestra price y no vuelve a aplicar margen.
- Productos de motos: disponibilidad siempre requiere confirmación porque el scraper de Chacomer no informa stock.
- Productos Ciclovía: e=0 significa figura en catálogo; e=1 sin stock; e=2 requiere consulta; e=3 sin dato.
- No inferir compatibilidad mecánica. Ante repuestos, pedir marca, modelo, año y cilindrada/versión, y derivar cuando no exista información concluyente.
- Envíos y costos: no inventar. La tienda indica que el costo se coordina por WhatsApp según zona.

## Segunda etapa: asistente con IA
La IA recibe el mensaje y contexto mínimo, identifica intención y decide qué consulta estructurada necesita. La búsqueda se ejecuta en la API. La respuesta final se construye solo con campos retornados por la API y reglas de atención.
Intenciones iniciales: buscar_producto, consultar_precio, consultar_disponibilidad, compatibilidad_repuesto, servicio_tecnico, envio, ubicacion, pedido, humano, fuera_de_alcance.
No se permite a la IA inventar productos, precios, existencias, compatibilidades ni plazos.

## Tercera etapa: WhatsApp
- Crear/validar Meta Business Portfolio y acceso a WhatsApp Cloud API.
- Verificar elegibilidad para coexistencia antes de tocar el número actual.
- Configurar Embedded Signup compatible con coexistencia.
- No desinstalar la app, no desvincular el número ni migrar a Cloud API tradicional como prueba.
- Validar mensajes entrantes, salientes, mensajes enviados desde la app y eventos de eco.
- Mantener comando HUMANO y control de pausa aunque la coexistencia permita sincronización.
- Probar con número de prueba antes de habilitar atención real.

## Cuarta etapa: n8n y datos operativos
Workflows:
1. Recepción: validar webhook, deduplicar mensajes y normalizar eventos.
2. Asistente: intención → API catálogo → IA redacta → enviar.
3. Atención humana: pausar, asignar y reactivar bot.
4. Pedidos: armar solicitud pendiente, confirmar manualmente; no descontar stock.
5. Monitoreo: fallos, catálogo desactualizado y alertas.

PostgreSQL guardará contactos, conversaciones, mensajes, estados bot/humano, pedidos, líneas y auditoría. No almacenar secretos ni información innecesaria.

## Operación local
- Python API en 127.0.0.1:8787.
- n8n y PostgreSQL en Docker Compose en la computadora.
- Para webhook de Meta se necesita URL HTTPS pública temporal (túnel seguro) o pasarela. No abrir puertos domésticos directamente.
- La computadora debe permanecer encendida, con Internet y energía estable. Si se apaga, el bot deja de atender; por eso local es adecuado para desarrollo/piloto, no disponibilidad comercial 24/7.
- Secretos en variables de entorno/credenciales; nunca en Git ni frontend.

## Seguridad y cumplimiento
- Verificación de firma de Meta, token de verificación, idempotencia y rate limits.
- CORS restringido y API no expuesta públicamente sin autenticación/pasarela.
- Respetar políticas de WhatsApp, ventanas de atención, plantillas y tarifas aplicables.
- Respetar términos de los sitios origen de los catálogos y no intensificar scraping.
- Política de privacidad y retención para mensajes y datos de clientes.

## Criterios de aceptación de la API
- Arranca con Python sin dependencias externas.
- Carga catálogo de bicicletas y motos desde los JSON existentes.
- Busca por nombre, marca, SKU y categoría.
- Devuelve el mismo precio final que la tienda para un mismo precio de origen.
- No presenta el stock de Chacomer como confirmado.
- Servicios y precios coinciden con config.js.
- Devuelve 404 para ID inexistente y 400 para parámetros inválidos.
- Pruebas unitarias pasan.

## Estado de validación de la primera etapa

Validada contra el snapshot real del repositorio, no contra datos de ejemplo. Se corrió dos veces: sobre
el catálogo de la rama (15.884 fichas, 21/11) y después sobre el snapshot publicado hoy en producción
(15.871 fichas, 24/11), para que el resultado no dependa de datos viejos.

| Chequeo | Resultado |
|---|---|
| Productos cargados por la API | **15.871** en el snapshot de producción, igual al total de `indice.json` |
| Precio de venta vs. tienda | **15.871 fichas comparadas, 0 diferencias** (y 15.884 en el snapshot anterior). Se compara contra el código real de `tienda/assets/app.js` (extraído y ejecutado con Node), no contra una copia de la fórmula |
| Recargo y redondeo | La API lee `recargoPct`, `recargoBajoPct`, `umbralBajo` y `redondeoPrecio` de `config.js` y coinciden con el frontend |
| Servicios técnicos | Los 3 planes y sus ítems se leen de `config.js`; coinciden en nombre, precio y detalle |
| Códigos de stock | La distribución por estado coincide con `por_estado` del índice en los dos snapshots |
| Motos | Las 13.105 quedan con disponibilidad `confirm`; ninguna se informa como stock confirmado |
| Productos sin precio | Las fichas de Ciclovía sin precio devuelven `price: null`; no se inventa precio |
| Rutas HTTP | 200 / 400 / 404 conforme a la especificación, verificadas sobre un servidor real |

No hizo falta corregir diferencias de precio ni de estructura: la etapa 1 cumple los criterios de aceptación.

## Estado de validación de la cuarta etapa (persistencia)

La rama `feat/chatbot-conversations-db` quedó validada contra PostgreSQL real:

| Chequeo | Resultado |
|---|---|
| Versión | PostgreSQL **16.9**, misma versión mayor que `postgres:16-alpine` del compose |
| Esquema en base vacía | Crea las 6 tablas (`contacts`, `conversations`, `messages`, `orders`, `order_items`, `audit_log`) y los 2 índices únicos parciales |
| Pruebas | **35/35**. Alta idempotente de contactos, teléfono inválido rechazado por el `CHECK`, una sola conversación abierta por contacto, conversación nueva al cerrar la anterior, deduplicación por id externo, auditoría del cambio bot/humano, subtotal del pedido, rollback completo cuando falla un renglón, orden cronológico del historial, exclusión de mensajes internos, transiciones de estado inválidas y confirmación concurrente del mismo pedido |
| Validación de entrada | `delivery_method` se valida en Python; antes un valor inválido salía como `CheckViolation` de psycopg |
| Lectura de contexto | `get_recent_messages` y `get_conversation_history` devuelven el historial en orden cronológico y dejan afuera los mensajes internos; leer no crea conversaciones |
| Estado de pedidos | `set_order_status` con transiciones controladas, auditoría por cambio, idempotencia ante reintentos y `FOR UPDATE` contra confirmaciones simultáneas |

Lo que **no** quedó probado: el `docker compose up` en sí (la máquina de validación no tiene Docker
Desktop) y el comportamiento con volumen persistente entre reinicios.

## Estado de la segunda etapa (asistente local)

Implementado en `bot/service/`, corriendo en local y sin WhatsApp. Se probó de punta a punta
con conversaciones reales contra el catálogo publicado.

| Chequeo | Resultado |
|---|---|
| Precio inventado | **Imposible por diseño**: si la búsqueda no devuelve nada, no se llama al modelo para redactar y se responde con una plantilla honesta |
| Precio real | Los importes salen de la API de catálogo; se verificaron contra ella (cámara, cubierta 700x25, casco, planes de service) |
| Contexto | "y cuánto sale el más barato?" después de "tenés cascos scott?" resuelve la referencia con el historial |
| Producto inexistente | "bici voladora láser" → responde que no lo tiene y ofrece el WhatsApp del taller |
| Consulta con modificadores | "cámaras 26 para mtb" no daba resultados (la API exige todas las palabras); se agregó reintento soltando la última palabra |
| Latencia | 1,0–2,9 s por respuesta con `gemini-3.1-flash-lite`. `gemini-3.5-flash` tardó 17–35 s y `gemini-3.8-flash` devolvió 503: por eso el default es el lite |
| Historial | Guarda en PostgreSQL cuando hay `DATABASE_URL` + psycopg; si no, en memoria. El `/health` informa cuál está activo |
| Pruebas | **33/33** con dobles del modelo y del catálogo, sin red ni API key |
| Foto del producto | Se manda una foto del primer resultado **no agotado**, dimensionada a 800x800 (~60 KB en vez de 350 KB). Se le indica al modelo qué producto muestra para que la respuesta hable de ese. En el chat local se ve; en WhatsApp falta el adaptador |
| Búsqueda por velocidades | "piñón 7 velocidades" devolvía **1** producto de los **5** que hay: el catálogo escribe "7 VELOCIDADES", "7V" y "7VL". Se unifican todas al token "7v" al buscar; ahora devuelve los 5 correctos y ningún falso positivo |
| Varias opciones | Cuando hay más de un resultado el bot dice cuántos hay y nombra hasta 3 con sus precios, en vez de mostrar uno solo |

Lo que **no** hace todavía: no recibe WhatsApp, no agenda turnos (explica los planes pero no
reserva), no arma pedidos y el "quiero hablar con una persona" no avisa a nadie. La foto se
devuelve lista pero nadie la envía al cliente todavía.

> Las imágenes son de Ciclovía y su uso comercial es la condición #1 del `PLAN.md`.

## Siguiente trabajo

Conectar el servicio al webhook de WhatsApp (etapa 3). Antes hay que validar la coexistencia
del número actual con la Cloud API y conseguir las credenciales de Meta.

Después, cerrar el circuito comercial: que el asistente use `create_pending_order` para armar
el pedido y `set_order_status` para que una persona lo confirme.

No activar WhatsApp real antes de validar coexistencia con el número actual.

