# Jaka Bicicletería — tienda con catálogo y precios sincronizados

**En línea:** https://llnikoll.github.io/jaka.com/

Tienda propia para revender **CICLOVIA** (`https://www.ciclovia.com.py/`, grupo Chacomer, Paraguay) con el
catálogo sincronizado desde la página original, un **recargo de margen configurable (+15 % por defecto)** y los
pedidos llegando por **WhatsApp**.

## Empezá por acá

| Archivo | Para qué sirve |
|---|---|
| **[tienda/index.html](tienda/index.html)** | **La tienda** (abrir en el navegador). Catálogo + canasta + pedido por WhatsApp |
| **[tienda/README.md](tienda/README.md)** | Cómo publicarla, cómo actualizar precios y cómo configurarla |
| **[PLAN.md](PLAN.md)** | Análisis de viabilidad y plan completo: arquitectura, reglas, fases, costos y riesgos |
| **[poc/REPORTE.md](poc/REPORTE.md)** | Prueba de extracción: 2.681 productos, 100 % de cobertura de los 4 pilares |
| **[recon/ANALISIS_TECNICO.md](recon/ANALISIS_TECNICO.md)** | Análisis técnico del sitio: selectores, variantes, stock, caché, robots |
| **[investigacion/TIENDA_Y_COMERCIO.md](investigacion/TIENDA_Y_COMERCIO.md)** | Pagos, envíos, impuestos y marco legal en Paraguay |

## Cómo está armado

```
poc/scraper_ciclovia.py  →  extrae el catálogo de ciclovia.com.py
        ↓
poc/data/*.jsonl         →  datos crudos (precio, stock, variantes, imágenes)
        ↓
tienda/build_catalogo.py →  genera tienda/data/indice.json + tienda/data/v/*.json
        ↓
tienda/index.html        →  catálogo + canasta + pedido por WhatsApp
```

## Lo que hace hoy

- **2.681 productos** publicados con **un solo precio limpio** (+15 % de margen ya incluido, sin tachado ni
  porcentajes), stock, marca e imagen.
- **Abre en Accesorios** (752 productos) y carga cada categoría bajo demanda: la primera pantalla pesa **55 KB**
  comprimida en lugar del catálogo completo.
- **Categorías completas:** Accesorios, Bicicletas, Fitness, Indumentaria, Autoaccesorios, Ofertas y Todos.
- **Búsqueda** y orden por precio/descuento/nombre; filtro “solo disponibles”.
- **Canasta** con cantidades, subtotal y total; se guarda en el navegador.
- **Checkout por WhatsApp** al **+595 993 539 237** con: detalle del pedido, cantidades, total, nombre, teléfono,
  dirección, referencia y **ubicación GPS** del cliente (link de Google Maps).
- **Sin pagos online, sin clientes registrados, sin panel de administración**: todo se cierra por WhatsApp.

## Actualización automática (en la nube, sin depender de la PC)

El workflow **“Actualizar catalogo y publicar”** (`.github/workflows/actualizar-catalogo.yml`) corre en GitHub
**todos los días a las 06:00 de Paraguay** (09:00 UTC):

```
lee ciclovia.com.py → regenera tienda/data → commit + push → GitHub Pages republica
```

No necesita que la PC esté encendida, ni tu internet, ni la tarea de Windows (esa quedó desactivada).

- **Ver corridas:** https://github.com/llnikoll/jaka.com/actions
- **Forzar una actualización ahora:** Actions → “Actualizar catalogo y publicar” → **Run workflow**
- **Cambiar la hora:** editar el `cron` del workflow (UTC; Paraguay = UTC-3)

> En repositorios públicos, GitHub puede pausar los workflows programados tras 60 días sin actividad. Como este
> workflow hace commit todos los días, el repositorio queda activo y no se pausa.

Manual (si alguna vez hace falta):

```powershell
.\tienda\actualizar.ps1                 # lee + regenera + publica por git desde tu PC
.\tienda\actualizar.ps1 -SinRed         # regenera desde la caché, 0 requests
python tienda\servidor.py 8080          # servidor local para probar (con gzip)
.\tienda\lanzar.ps1                     # servidor + URL temporal de Cloudflare (para mostrar sin hosting)
```

## Estado de la extracción

| Métrica | Resultado |
|---|---|
| Productos únicos | 2.681 (de 5.711 tarjetas en 111 páginas) |
| Cobertura 4 pilares | 100 % (1.302 + 1.233 + 141 + 22) |
| Calidad | 0 duplicados, 0 precios inválidos, 100 % con imagen |
| Costo de mantenimiento | ~45 requests por pasada de precios (≈70 s) |

> Antes de invertir en volumen: leer las **3 condiciones** del `PLAN.md` §0 (autorización de Ciclovía, cruce costo
> mayorista vs precio online y definición de SKU padre/hijo).
