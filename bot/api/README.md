# API de catálogo — Jaka Bicicletería

API HTTP local, sin dependencias externas, que consulta los JSON que ya genera la tienda. No modifica scrapers, builders ni el frontend existente.

## Requisitos

- Python 3.10 o superior.
- Ejecutar desde la raíz del repositorio (el script resuelve las rutas automáticamente).

## Ejecutar

```bash
python bot/api/server.py
```

Por defecto escucha solo en `127.0.0.1:8787`, para pruebas locales.

Variables opcionales:

- `CATALOG_HOST`: interfaz de escucha. Mantener `127.0.0.1` mientras solo se pruebe en la computadora.
- `CATALOG_PORT`: puerto, por defecto `8787`.
- `CATALOG_ALLOWED_ORIGIN`: origen CORS permitido. Para pruebas desde una web, indicar el origen exacto. No dejar `*` en un servicio expuesto públicamente.
- `CATALOG_SITE_URL`: URL pública de la tienda usada para formar enlaces de productos.

## Endpoints

| Método | Ruta | Función |
|---|---|---|
| GET | `/health` | Estado del proceso |
| GET | `/catalog/status` | Cantidad de productos y fecha del catálogo |
| GET | `/catalog/search?q=shimano` | Búsqueda por nombre, marca, SKU y categoría |
| GET | `/catalog/search?q=aceite&type=motos` | Filtrar por tipo |
| GET | `/catalog/search?q=casco&category=motos/accesorios` | Filtrar por categoría |
| GET | `/catalog/product/{id}` | Ficha de producto por ID |
| GET | `/catalog/categories` | Categorías detectadas |
| GET | `/services` | Servicios técnicos y precios |

La búsqueda admite `limit` (1–50) y `offset`.

## Precio y disponibilidad

La API lee los parámetros comerciales actuales de `tienda/assets/config.js` y reproduce el recargo y redondeo que usa `tienda/assets/app.js`. Devuelve tanto `source_price` como `price` para auditoría. El bot debe mostrar solo `price` al cliente y nunca volver a aplicar el recargo.

Estados de disponibilidad:

- `available_in_catalog`: el catálogo de Ciclovía marca el producto con estado 0; se informa como “figura en catálogo”, no como reserva confirmada.
- `out_of_stock`: el catálogo de Ciclovía marca estado 1.
- `confirm`: se requiere confirmación humana. Todos los productos de motos entran aquí porque el scraper de Chacomer no obtiene stock.
- `no_data`: el catálogo no aporta información suficiente.

## Fuente de datos

- Bicicletas, accesorios y fitness: `tienda/data/catalogo.json` (respaldo: `tienda/data/v/todos.json`).
- Motos: `tienda/data/motos/v/todos.json`.
- Metadatos: `tienda/data/indice.json`.

La API carga los archivos al iniciar el proceso. Tras una actualización de catálogo, reiniciar el proceso para recargar el snapshot.

## Pruebas

```bash
python -m unittest discover -s bot/api/tests -t . -v
```

El `-t .` no es opcional: fija la raíz del repositorio como punto de partida para que los tests
puedan importar `bot.api.server`. Sin él, `unittest` intenta importar los módulos como si estuvieran
sueltos y falla con `Start directory is not importable`.

Hay dos niveles:

- **Unitarias** (`test_server.py`): normalización de texto, redondeo por tramos y reglas de disponibilidad.
- **Integración** (`test_integracion_catalogo.py`): cargan el catálogo real del repositorio y verifican que la
  API devuelva los mismos 15.884 productos que publica la tienda, que los códigos de stock coincidan con
  `tienda/data/indice.json`, que los servicios salgan de `config.js` y que las rutas HTTP respondan
  200/400/404 según la especificación.

La prueba de precio compara las **15.884 fichas** contra el código real de `tienda/assets/app.js`, extraído y
ejecutado con Node. Es la que detecta que el recargo o el redondeo del frontend cambien y la API quede
desfasada. Si Node no está instalado, esa prueba se saltea; el resto corre igual con Python estándar.

> Si cambia la forma de las funciones de precio de `app.js`, el extractor
> (`tests/precios_app_js.mjs`) falla a propósito: hay que revisarlo antes de dar por buena la paridad.

## Seguridad / siguiente fase

No exponer el puerto local directamente a Internet. Para recibir webhooks de Meta desde la computadora será necesario un túnel HTTPS temporal o una pasarela segura, con verificación de firma, autenticación, rate limit y secretos en variables de entorno. Esta API de catálogo es de solo lectura; no incluye aún pedidos, base de datos ni conexión a WhatsApp.
