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

## Siguiente trabajo
Ejecutar pruebas con el snapshot local del repositorio, corregir cualquier diferencia de precio o estructura, añadir tests de integración con productos reales y luego integrar n8n/IA. No activar WhatsApp real antes de validar coexistencia.
