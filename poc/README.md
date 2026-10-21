# PoC: extractor de catálogo y precios de ciclovia.com.py

Scraper en Python que recorre el catálogo público de
[www.ciclovia.com.py](https://www.ciclovia.com.py/) (Magento 2, tema Chacomer, locale
`es-AR`, moneda `PYG`) y deja los datos listos para importar a una tienda propia:
tarjetas de categoría (nombre, SKU, precio final, precio anterior, moneda,
disponibilidad, imagen) + 5 fichas de producto completas (marca, stock, imágenes,
descripción, especificaciones y variantes con SKU y precio por hijo).

El sitio tiene `/graphql` bloqueado por Varnish (403) y `/rest/V1` con 401, así que todo
se extrae de HTML server-side.

- Fecha de la corrida documentada: **2026-10-21** (hora de Paraguay, UTC-3).
- Resultado: **ver `REPORTE.md`** (métricas, cobertura por pilar, limitaciones).

---

## 1. Requisitos

- Python 3.9 o superior.
- [`lxml`](https://lxml.de/) — **obligatorio** (parseo de HTML).
- `requests` — opcional. Si no está, el scraper usa `urllib` de la biblioteca estándar.

```powershell
# con el Python del sistema
python -m pip install lxml requests

# o con el Python que trae el harness (ya incluye lxml, no incluye requests)
C:\Users\<usuario>\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe poc\scraper_ciclovia.py --modo robots
```

Si falta `lxml`, el script corta con un mensaje que indica cómo instalarlo.

## 2. Uso rápido

```powershell
# 1) Ver robots.txt y qué permite
python poc\scraper_ciclovia.py --modo robots

# 2) Planificar sin tocar la red (lee la caché existente)
python poc\scraper_ciclovia.py --modo inventario

# 3) Barrido completo: categorías + 5 fichas + validación
python poc\scraper_ciclovia.py --modo todo --presupuesto-total 150

# 4) Reprocesar TODO desde la caché (0 requests)
python poc\scraper_ciclovia.py --modo todo --sin-red

# 5) Validar las salidas ya escritas
python poc\scraper_ciclovia.py --modo validar
```

Modos disponibles: `robots`, `probe`, `inventario`, `categorias`, `fichas`, `todo`,
`validar`.

### Opciones principales

| Opción | Default | Qué hace |
|---|---|---|
| `--modo` | `todo` | Fase a ejecutar. |
| `--limite-pagina` | `64` | `product_list_limit`. El sitio ofrece 36/48/64; valores mayores se ignoran y vuelve a 36. |
| `--delay-min` / `--delay-max` | `0.8` / `1.5` | Pausa aleatoria entre requests (segundos). |
| `--max-requests` | `150` | Tope duro de requests HTTP de la corrida. |
| `--presupuesto-total` | `0` | Tope acumulado: descuenta lo que ya figura en `cache/_requests.jsonl` (sirve para respetar un presupuesto global entre corridas). |
| `--reservado` | `10` | Requests que se dejan libres para fichas/reintentos. |
| `--incluir-raices` | apagado | Incluye las 4 categorías raíz (pilares). Son supersets de las hojas: cuestan requests y duplican tarjetas (se deduplican igual). |
| `--politica-robots` | `paginado` | `paginado`: permite solo `?p=` y `?product_list_limit=` (ver §6). `estricta`: respeta `Disallow: /*?` y baja solo la página 1 de cada categoría. |
| `--ficha-control` | ficha de Scott Contrail 40 | Ficha extra que se verifica contra valores conocidos. |
| `--seed` | `20261021` | Semilla para elegir las 5 fichas (reproducible). |
| `--force` | apagado | Ignora la caché y vuelve a pedir todo. |
| `--sin-red` | apagado | No hace ningún request: solo caché. |
| `--sin-fichas` | apagado | No extrae fichas. |

## 3. Estructura

```
poc/
├── scraper_ciclovia.py     # el scraper (único archivo ejecutable)
├── README.md               # este archivo
├── REPORTE.md              # hallazgos, métricas y limitaciones
├── cache/                  # HTML crudo por URL + sitemap + robots + log de requests
│   ├── robots.txt
│   ├── sitemap.xml
│   ├── cat__<categoria>__product_list_limit64_p<N>.html
│   ├── ficha__<slug>.html
│   └── _requests.jsonl     # auditoría: ts, url, status, bytes, ms, user-agent
└── data/
    ├── productos.jsonl     # una tarjeta por línea (todos los campos + categorías)
    ├── productos.csv       # tabla plana para importar (UTF-8 con BOM, precios enteros)
    ├── fichas.jsonl        # 5 fichas completas (variantes anidadas)
    ├── categorias.csv      # una fila por categoría con totales y cobertura
    ├── estadisticas.json   # métricas de la corrida + robots + ficha de control
    └── validacion.json     # chequeos automáticos de las salidas
```

## 4. Qué extrae

### 4.1 Tarjetas de categoría → `data/productos.jsonl` / `data/productos.csv`

| Campo | Ejemplo | Notas |
|---|---|---|
| `id_magento` | `463859` | `product_id` de Magento. **Clave de deduplicación.** |
| `sku` | `410116726` | Del formulario "Comprar" (`data-product-sku`). Solo existe si la tarjeta es comprable (≈48% del catálogo). |
| `nombre` | `BICICLETA MTB SCOTT CONTRAIL 40` | |
| `url` | `https://www.ciclovia.com.py/bicicleta-mtb-scott-contrail-40.html` | URL canónica `.html`. |
| `moneda` | `PYG` | |
| `precio_final` | `3811800` | Entero en guaraníes, **sin separadores de miles**. |
| `precio_anterior` | `5082400` | Entero o vacío. |
| `descuento_pct` | `25.0` | Calculado. |
| `etiqueta` | `HASTA 25% OFF` | Claim de descuento del tema. |
| `estado_tarjeta` | `con_precio` | `con_precio` / `agotado` / `solo_catalogo` / `sin_dato` (ver §5). |
| `disponibilidad` | `En stock` | En tarjetas es **inferida** (el grid no publica stock positivo). |
| `imagen` | `https://…/media/catalog/product/….jpg` | Imagen del grid. |
| `rubro` | `bicicletas` | Derivado del primer nivel de categoría. |
| `categoria_principal` | `bicicletas/mtb` | La categoría más específica donde apareció. |
| `categorias` | `bicicletas/mtb|cyberday` | En JSONL es lista; en CSV va separado por `|`. |
| `fecha_captura` | `2026-10-21T15:20:00-03:00` | |

### 4.2 Fichas → `data/fichas.jsonl`

Una por rubro (bicicletas, fitness, indumentaria, autoaccesorios) + una de promociones.
Campos: `nombre`, `url`, `marca`, `sku`, `tipo_producto`, `moneda`, `precio_final`,
`precio_anterior`, `descuento_pct`, `disponibilidad` (real: `En stock` / `Agotado`),
`descripcion`, `especificaciones` (dict), `imagenes` (lista), `imagen_principal`,
`opciones` (atributos y valores, p. ej. Tamaño/Color), `variantes` (lista con
`id_variante`, `sku`, `atributos`, `precio_final`, `precio_anterior`, `vendible`),
`cantidad_variantes`, `variantes_vendibles`, `categorias_catalogo`.

## 5. Reglas de modelado (importante para la tienda)

1. **Deduplicación por `product_id`**, no por URL: la misma ficha aparece como
   `/slug.html` y como `/catalog/product/view/id/<id>/…` y el sitio no siempre expone
   canonical. Un producto puede estar en varias categorías: `categorias` acumula todas y
   `categoria_principal` es la hoja más específica.
2. **Tres estados de tarjeta** (no son errores):
   - `con_precio`: precio final publicado.
   - `solo_catalogo`: `div.onlycatalog-message` → "Adquiéralo en un distribuidor
     autorizado". Sin precio pero **cuenta en el total de la categoría**.
   - `agotado`: `.stock.unavailable` con "Sin stock". Puede conservar precio.
   - `sin_dato`: ni precio ni marcador (raro).
3. **Stock**: no hay marcador positivo en el grid. Si no dice "Sin stock" se asume
   `En stock` y se marca `disponibilidad_inferida: true`. Solo las fichas de producto
   dan `En stock`/`Agotado` reales.
4. **Precios**: enteros en PYG, tal como los publica `data-price-amount`
   (`3811800`). Nunca con puntos ni decimales. El texto formateado se guarda aparte en
   `precio_final_texto`.
5. **Variantes**: de `x-magento-init` → `Magento_Swatches/js/swatch-renderer` →
   `jsonConfig` se toman `optionPrices[childId].finalPrice.amount`, `sku[childId]`,
   `index` (combinación de atributos) y `salable` (hijos vendibles).

## 6. Robots.txt: la parte incómoda (leer antes de producción)

El `robots.txt` del sitio es la plantilla de Magento 2 y trae, bajo `User-agent: *`:

```
Disallow: /*?
Disallow: /*?p=*&
```

Eso **prohíbe toda URL con query string**, incluido el paginado
`?p=2&product_list_limit=64`. Consecuencias:

- El barrido por paginado que hace este PoC es la **vía eficiente** (≈45 páginas para los
  4 pilares) pero **NO es robots-compliant**: requiere autorización escrita del dueño del
  sitio. Queda documentado así en `data/estadisticas.json` (`robots.permite_url_con_query
  = false`).
- La **vía 100% robots-compliant** es: sitemap → fichas SEO individuales
  (`/<slug>.html`, 3.778 URLs, sin query string), ≈1,2 s por request ⇒ ~76 minutos. Se
  puede combinar: paginado (con permiso) + fichas SEO para lo que falte.
- Con `--politica-robots estricta` el scraper solo baja la página 1 de cada categoría
  (36 productos) y deja constancia en `categorias.csv`.

Además nunca se tocan `/checkout`, `/customer`, `/catalog/product/view/`, `/js`, `/lib`,
`/skin`, `*.php` ni `/media` (salvo `/media/catalog/product/`).

**Cortesía implementada**: 1 request a la vez, delay aleatorio 0,8–1,5 s, User-Agent
identificable (`BiciTiendaPoC/1.0 (+… ver poc/README.md)`), tope de requests, caché en
disco y reanudación sin repetir descargas.

## 7. Caché y reanudación

- Cada URL se guarda en `cache/` con nombre determinista. Si el archivo existe, no se
  vuelve a pedir (una segunda corrida es instantánea y hace 0 requests).
- `cache/_requests.jsonl` es la auditoría real de requests (sirve para demostrar el tope
  de ~150 y para `--presupuesto-total`).
- `--force` ignora la caché; `--sin-red` trabaja solo con lo cacheado.

## 8. Limitaciones conocidas (detalle y números en `REPORTE.md`)

- `promociones.html` es una landing PageBuilder: **0 productos en el HTML** (no es error).
  La vista de promociones se puede derivar de `descuento_pct > 0` del catálogo.
- `sku` de tarjeta: solo cuando el producto es comprable (≈48%). Para el resto hace falta
  abrir la ficha.
- El breadcrumb de las fichas de producto se renderiza con JS (el HTML trae
  `<div class="breadcrumbs"></div>` vacío): las categorías del producto salen del barrido
  del catálogo, no de la ficha.
- Categorías "ocultas" sin URL `.html` (`/catalog/category/view/s/hidratacion/id/842/`,
  `/…/transporte/id/849/`) quedan fuera: no están en el sitemap ni tienen URL limpia.
- Algunos productos tienen NUL dentro del nombre en el HTML; el scraper limpia caracteres
  de control antes de parsear (sin eso, lxml truncaba la página y se perdían tarjetas).
