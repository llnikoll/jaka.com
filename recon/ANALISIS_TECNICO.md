# Análisis técnico — ciclovia.com.py

**Objetivo:** documentar la estructura real de https://www.ciclovia.com.py/ para alimentar un sistema de sincronización automática de catálogo y precios hacia una tienda propia.

| | |
|---|---|
| Fecha del relevamiento | 2026-10-21 (14:57–15:40, America/Asuncion) |
| Autor | recon-tecnico (equipo BiciTienda) |
| Sitio auditado | https://www.ciclovia.com.py/ (Magento 2, tema `Chacomer/ciclovia`) |
| Método | HTTP GET/HEAD con `curl`, User-Agent identificable, **41 requests totales**, delay 1,3 s entre requests, sin concurrencia |
| Evidencia cruda | `%TEMP%\ciclovia-recon\` (headers de las 41 respuestas + HTML de 39; los 2 `HEAD` no tienen cuerpo + `requests.tsv`) y archivos del Lead en `recon/` y raíz |
| Alcance | Público, sin credenciales, sin tocar checkout/formularios |

> Este documento **no** modifica ni reemplaza los archivos existentes en `recon/`. Todo lo afirmado abajo está respaldado por una respuesta HTTP real capturada en este relevamiento; lo que quedó sin probar se marca explícitamente como **pendiente**.

---

## 0. Resumen ejecutivo

1. **La sincronización es viable por scraping HTTP, pero no con un solo parser frágil.** El sitio expone precio, SKU, stock y variantes en tres capas redundantes: **microdata `schema.org` + meta `og:/product:`** (fichas), **JSON embebido de `x-magento-init`** (variantes, precios por variante, SKUs) y **DOM del tema**. Conviene parsear en ese orden de prioridad y usar el DOM solo como respaldo.
2. **La grilla de categoría ya trae casi todo lo necesario para precio/stock de variantes.** Cada tarjeta de producto configurable incluye un `jsonConfig` de swatch-renderer con **mapa SKU hijo → precio final/anterior** y el mapa de vendibilidad (`salable`). No hace falta abrir cada ficha para mantener precios.
3. **El sitemap (`/sitemap.xml`) NO sirve como detector fino de cambios, pero sí como detector de altas/bajas.** Su `lastmod` se actualiza en bloque (2.216 URLs con fecha 2026-10-20, 1.066 con 2026-08-04) y hay URLs muertas (1 probada → 404). Sí sirve su `ETag`/`Last-Modified` para un `304` barato.
4. **Las fichas no tienen `<link rel="canonical">` y existen URLs duplicadas** (SEO `.html` y `/catalog/product/view/id/<id>/...`). Hay que deduplicar por `product_id`.
5. **No hay API pública utilizable**: `/graphql` → 403 (Varnish), `/rest/V1` → 401. No hay JSON-LD; sí microdata y `og:` meta.
6. **No se observó anti-bot activo**: 41 requests, 39×200 + 2×404, cero 403/429, sin captcha en páginas públicas. El límite real es la cortesía y —clave legal— el **`robots.txt`**, que prohíbe `/*?` y `/catalog/product/view/`.
7. **Volumen real:** 4 pilares suman 2.698 fichas (con solapamiento); el sitemap declara 3.810 URLs de ficha; el catálogo mezcla bici/fitness/indumentaria con repuestos de moto/auto del grupo Chacomer.
8. **Riesgo principal:** depender del DOM del tema. Mitigación: resolver el 90 % de los campos con microdata + `jsonConfig` + regex sobre JSON, y usar selectores DOM solo para ubicar esos bloques.

---

## 1. Stack y arquitectura observada

| Componente | Evidencia | Implicancia |
|---|---|---|
| **Magento 2** (Adobe Commerce) | `Magento_*` modules en `x-magento-init`, `static/version1792543259/frontend/Chacomer/ciclovia/es_AR`, `form_key`, `Magento_PageCache` | Estructura Magento estándar: predecible |
| **ElasticSuite** (`Smile_ElasticsuiteCatalog`) | Facetas por atributo con `Smile_ElasticsuiteCatalog/js/attribute-filter`, `ajaxLoadUrl` por faceta | Búsqueda/filtros vía ElasticSearch: los conteos y el orden no son los de MySQL |
| **Tema `Chacomer/ciclovia`** | `BASE_URL` + `require.baseUrl` en `<head>` | Selectores propios del tema (`product-item-brand`, `onlycatalog-message`, `product-items-names`) |
| **Locale / moneda** | `var LOCALE = 'es-AR'`; `product:price:currency = PYG`; `priceFormat.pattern = "PYG %s"` | Precios **enteros** en guaraníes, separador de miles `.` y decimal `,` (no se usa) |
| **CDN + caché** | `X-Served-By: cache-iad-…, cache-eze…`, `X-Cache: MISS/HIT`, `Age`, `X-Cache-Hits` (Fastly) + `x-esi: 1`, `x-platform-server`, `x-debug-info: eyJyZXRyaWVzIjowfQ==` (= `{"retries":0}`) | Fastly adelante, Varnish/Magento atrás; HTML **no** cacheable (`no-store`) |
| **PIM externo** | Rutas de imagen `media/catalog/product/.../api-v1.1-file-public_files-pim-assets-…` | El catálogo se alimenta desde un PIM con API propia (posible vía oficial de integración) |
| **Otros módulos** | `SummaSolutions_StorePickup`, `Meta_Conversion` (Meta pixel server-side), `Magento_GoogleTagManager`, `Propultech_SpecsBox`, `FullMage_Popup`, New Relic | Ruido en el HTML; el `dataLayer` de GTM es una fuente extra útil (§4.4) |
| **HTTP** | `HTTP/1.1`, `content-encoding: gzip`, HSTS 1 año, CSP en modo *report-only* | Sin negotiación HTTP/2 observada con `curl` (no bloqueante) |

---

## 2. Paginación de categorías

### 2.1 Parámetros (verificados en vivo)

| Parámetro | Valores | Evidencia |
|---|---|---|
| `?p=N` | 1..última página | links `.pages` → `bicicletas.html?p=2`… |
| `?product_list_limit=N` | **36 (default), 48, 64** | select de toolbar (`product_list_limit=36/48/64`); `limitDefault: 36` en `productListToolbarForm` |
| `?product_list_order=` | `position` (default), `name`, `price`, `updated_at`, `descuento` | `data-role="sorter" data-value="…"` |
| `?product_list_dir=` | `asc` (default), `desc` | idem |
| `?product_list_mode=` | `grid` (default) | `modeDefault:"grid"` (la vista lista no se usa) |

Los parámetros se combinan y la paginación los **preserva** (los links de las páginas 2+ repiten el filtro/orden/limit):

```
/bicicletas.html?p=2&product_list_dir=asc&product_list_order=price
/bicicletas.html?p=2&color_bicicletas=NEGRO
/bicicletas.html?p=2&product_list_limit=64
```

### 2.2 Cuántas páginas hay (no confiar en los links)

El bloque `.pages` muestra una **ventana de ±2 páginas**, no el total: en la página 1 de BICICLETAS solo aparecen links a 2, 3, 4, 5 y "Siguiente". El total hay que **calcularlo**:

```
total_paginas = ceil(total_productos / product_list_limit)
```

El total está en el HTML server-side, en `.toolbar-amount`:

```html
<p class="toolbar-amount" id="toolb…">1302 Resultados para BICICLETAS</p>
```

| Categoría | Total | Páginas a 36/pág | Páginas a 64/pág |
|---|---:|---:|---:|
| BICICLETAS (`/bicicletas.html`) | **1.302** | **37** | **21** |
| FITNESS (`/fitness.html`) | 1.233 | 35 | 20 |
| INDUMENTARIA (`/indumentaria.html`) | 141 | 4 | 3 |
| AUTOACCESORIOS (`/autoaccesorios.html`) | 22 | 1 | 1 |

→ **Con `product_list_limit=64` se recorre todo el catálogo de los 4 pilares en 45 requests** en lugar de 77. Verificado: `?product_list_limit=64` devolvió **64 productos reales** (65 `li`, uno es plantilla) y la página 2 incluye `product_list_limit=64`.

### 2.3 ¿El HTML de la página 2+ trae los productos igual?

Sí. Comparación página 1 vs página 2 de BICICLETAS (misma estructura, sin solapamiento):

- 36 productos por página en ambas; `toolbar-amount` idéntico (1.302).
- **0 de 36** `product_id` repetidos y **0 de 36** SKU repetidos entre `?p=1` y `?p=2`.
- La página 2 solo cambia los 4 links de paginación (apunta a `?p=3`) y el "next".
- La canonical de **todas** las páginas (1, 2, limit=64, orden, filtro) apunta a la URL base sin query: `https://www.ciclovia.com.py/bicicletas.html`.

### 2.4 Filtros / facetas (ElasticSuite)

Los filtros son **por código de atributo**, en la query string, y son combinables (`&`). Códigos observados en BICICLETAS (29):

```
brand, modelo, tipo_de_bicicleta, tipo, aro, tama_o, tama_o_bicicletas, color_bicicletas,
componentes, motor, freno_delantero, potencia, potencia_de_motor, peso_max_de_ususario,
litros, modalidad, nivel_de_resistencia, programas_de_entrenamiento, sugerencia_de_uso,
velocidad_maxima, descarrilador_delantero, aplicacion_1, aplicacion_2, cantidad_de_bicicletas,
descuento, tiempo_de_carga, capacidad, tipo_de_carga, largo, ancho, altura
```

| Filtro | URL de ejemplo | Verificación |
|---|---|---|
| Marca | `/bicicletas.html?brand=CALOI` | links server-side en el bloque de faceta |
| Color | `/bicicletas.html?color_bicicletas=NEGRO` | **probado**: toolbar pasa de 1.302 a **45 resultados**, aparece `.filter-current` con "Color NEGRO" |
| Talle | `/bicicletas.html?tama_o_bicicletas=LARGE` | links server-side (faceta tipo swatch) |
| Aro | `/bicicletas.html?aro=27.5%22` | links server-side |
| Descuento | `/bicicletas.html?descuento=25%25` | links server-side (valores 13 %…75 %) |
| Rango de precio | `/bicicletas.html?price=<desde>-<hasta>` | `urlTemplate` del `range-price-slider`; **pendiente** de probar |

Detalle importante: `color_bicicletas` y `tama_o_bicicletas` se renderizan **server-side** (bloque `swatch-layered`); el resto de las facetas se pinta con Knockout y sus opciones vienen igual en el HTML como JSON (`items`), pero hay además un endpoint AJAX por faceta:

```
/catalog/navigation_filter/ajax/id/172/?cat=172&filterName=brand
```

(id 172 = BICICLETAS). **No se probó** ese endpoint (fuera de presupuesto); se documenta como vía liviana a validar, útil para descubrir facetas pero **no** para precios.

### 2.5 Composición de la grilla (lo que hay que saber antes de parsear)

Cada `li` del grid puede ser de cuatro tipos y hay que clasificarlos:

1. **Producto simple con precio online** → tarjeta normal.
2. **Producto configurable** (bici/calzado): una sola URL, variantes en `jsonConfig`.
3. **Producto "solo catálogo"**: **no tiene precio**, muestra
   `<div class="onlycatalog-message"><span>Adquiéralo en un distribuidor autorizado</span></div>`.
   El producto **sí cuenta** en `.toolbar-amount`. Ejemplo: categoría URBANAS (7 resultados) → 7 tarjetas, **0 con precio**.
4. **Producto agotado**: tarjeta con precio y `<div class="stock unavailable"><span>Sin stock</span></div>`. No existe un marcador positivo de stock en la grilla (si no dice "Sin stock", asumir disponible).

Además hay que **excluir dos `li` que no son productos**:

- `ol.product-items.product-items-names > li` (plantilla de autocompletado), y
- el último `li.product-item` del grid, que es la **plantilla de "comparar"** con `data-bind` (no tiene `data-role="priceBox"`).

---

## 3. Ficha de producto

### 3.1 URLs

| Forma | Ejemplo | Notas |
|---|---|---|
| SEO `.html` | `/bicicleta-mtb-scott-contrail-40.html` | forma dominante (3.747 en sitemap) |
| Sin rewrite | `/catalog/product/view/id/463807/category/172/` | aparece **también en las grillas**; 63 URLs de este tipo en sitemap |
| Sin rewrite (sitemap) | `/catalog/product/view/id/456641` | sin `category/` |

- **No hay `<link rel="canonical">` en las fichas** (0 en las 3 fichas analizadas). `robots` = `INDEX,FOLLOW`.
- Las dos formas devuelven **200 y el mismo contenido** (misma `h1`, mismo SKU, mismo precio) → contenido duplicado; deduplicar por `product_id`.
- `og:url` sí está presente y apunta a la URL SEO canónica cuando existe.

### 3.2 Campos de la ficha (ejemplo real, configurable)

**`GET /bicicleta-mtb-scott-contrail-40.html`** → 333 KB decodificados, 74 KB en el cable.

| Campo | Valor real observado |
|---|---|
| `h1` / `og:title` | `BICICLETA MTB SCOTT CONTRAIL 40` |
| SKU (visible) | `410116726` → `<div class="value" itemprop="sku">410116726</div>` |
| Marca | `og:product:brand = SCOTT` (+ fila "Marca" de la tabla de especificaciones) |
| Precio final | `3.811.800` (`data-price-type="finalPrice"`, `og:product:price:amount`, `itemprop="price"`) |
| Precio anterior | `5.082.400` (`data-price-type="oldPrice"`) |
| Etiqueta del precio | `Valor mínimo` (configurable) / `Precio especial` (simple con descuento) / `Precio habitual` (anterior) |
| Descuento | `HASTA 25% OFF` (`.percentage-discount .special-price-discount`) |
| Moneda | `PYG` (`meta product:price:currency`, `priceFormat.pattern = "PYG %s"`, `precision: 0`) |
| Stock | `<div class="stock available"><span>En stock</span></div>` + `og:availability = in stock` |
| SKU de variantes | `{"463858":"4101167M26B","463857":"4101167M26N", …}` (11 hijos) |
| Precio por variante | `optionPrices[<childId>].finalPrice.amount` / `.oldPrice.amount` (ej.: `463855` → `4.320.040`) |
| Imágenes | 5 en galería (`thumb`/`img`/`full`), `media/catalog/product/…_1b.jpg`, `_2b.jpg`… |
| Descripción | `Detalles BICICLETA SCOTT CONTRAIL 40 MEDIUM BLANCO` + "Ver más" (texto corto autogenerado, **poco útil**) |
| Especificaciones | tabla de **13 pares** (Marca, Tipo de Bicicleta, Aro, Tipo de Producto, Modelo, Cubiertas, Descarrilador Trasero, Frenos, Material de Cuadro, Cuadro, Suspensión, Tipo de suspensión, Velocidades) |
| Relacionados | bloque **"Productos similares" con 20 tarjetas** (traen precio, `product_id`, SKU y stock) |
| Categoría (ruta) | `dataLayer` → `content_category: "BICICLETAS,MTB"` |

**Ficha simple** (`/casco-scott-jibe-pm-gris.html`, 190 KB): SKU `SC275226GPM`, `En stock`, `246.500` (antes `290.000`, `HASTA 15% OFF`), specs `Marca/Color/Modelo/Tamaño/Tipo de Producto`, `content_category: "REPUESTOS Y ACCESORIOS DE BICICLETAS,ACCESORIOS,ACCESORIOS DE BICICLETAS"`.

**Ficha agotada** (`/cinta-de-caminar-electrica-up-run-plus.html`, 259 KB):

```html
<div class="stock unavailable" title="Disponibilidad"><span>Sin stock</span></div>
<meta property="og:availability" content="out of stock" />
```
El precio sigue visible (`25.522.110`): **agotado ≠ sin precio**.

### 3.3 Variantes: dos modelos conviven

| Modelo | Cómo se detecta | Consecuencia para el catálogo |
|---|---|---|
| **Configurable** (mayoría de bicis) | tarjeta/ficha con `Magento_Swatches/js/swatch-renderer` y `jsonConfig.attributes` | 1 URL pública, N `product_id` hijos, N SKU hijos, precio por hijo |
| **Variante como producto separado** (legacy) | diferentes URLs/lugares con el talle o el SKU en el slug, ej. `bici-scott-scale-940-large-41011329l.html` | 218 URLs del sitemap con sufijo tipo SKU |

En el modelo configurable el SKU **visible es el del padre** (`410116726`), que **no coincide** con ningún SKU hijo (`4101167M26B`, …). Para mapear contra una lista de precios mayorista hay que definir con Ciclovia si el código que usan es el padre o el hijo — **riesgo abierto**.

### 3.4 Ejemplo de la joya: `jsonConfig` de variantes (recortado)

```json
{"attributes":{"560":{"id":"560","code":"tama_o_bicicletas","label":"Tamaño",
   "options":[{"id":"9365","label":"SMALL","products":["463855","463854","463850","463977"]}, …]},
 "561":{"id":"561","code":"color_bicicletas","label":"Color",
   "options":[{"id":"9387","label":"BLANCO","products":[…]} …]}},
 "optionPrices":{"463858":{"baseOldPrice":{"amount":5082400},"oldPrice":{"amount":5082400},
   "basePrice":{"amount":3811800},"finalPrice":{"amount":3811800},"tierPrices":[],"msrpPrice":{"amount":0}}, …},
 "priceFormat":{"pattern":"PYG %s","precision":0,"requiredPrecision":0,"decimalSymbol":",",
   "groupSymbol":".","groupLength":3,"integerRequired":true},
 "prices":{"baseOldPrice":{"amount":5082400},"oldPrice":{"amount":5082400},
   "basePrice":{"amount":3811800},"finalPrice":{"amount":3811800}},
 "productId":"463859","index":{"463858":{"560":"9366","561":"9387"}, …},
 "salable":{"560":{"9367":["463851","463849"],"9365":["463850"]},"561":{"9402":["463851"],"9387":["463850"],"9392":["463849"]}},
 "canDisplayShowOutOfStockStatus":true,"channel":"website","salesChannelCode":"ciclovia",
 "sku":{"463858":"4101167M26B","463857":"4101167M26N", …}}
```

**Stock por variante (derivado):** la unión de los `product_id` listados en `salable` son los hijos vendibles. En este producto hay **3 vendibles de 11** (`463851`, `463849`, `463850`). El resto está agotado. `canDisplayShowOutOfStockStatus: true` confirma que las variantes agotadas se siguen mostrando.

> **Cuidado:** `salable` sirve para "qué combinaciones se pueden comprar", no para cantidades. No hay cantidades por variante en el HTML público.

---

## 4. JSON embebido / microdata: ¿qué es más estable que el HTML?

**No hay JSON-LD** (`<script type="application/ld+json">` = 0 en categorías y fichas).

### 4.1 Microdata `schema.org` (fichas) — **prioridad 1**

```html
<div class="product-info-price" …>
  <div class="stock available" title="Disponibilidad"><span>En stock</span></div>
  <div class="product attribute sku"><strong class="type">SKU</strong>
     <div class="value" itemprop="sku">410116726</div></div>
  …
  <span class="price-container price-final_price tax weee" itemprop="offers" itemscope
        itemtype="http://schema.org/Offer">
     <span class="price-label">Valor mínimo</span>
     <span id="product-price-463859" data-price-amount="3811800" data-price-type="finalPrice">
        <span class="price">PYG 3.811.800</span>
```

`itemtype` presentes: `schema.org/Product` y `schema.org/Offer`. `itemprop` presentes: `name`, `sku`, `image`, `description`, `offers`, `price`, `priceCurrency`. **No hay `availability`** como itemprop: la disponibilidad está en el texto del div y en `og:availability`.

### 4.2 Meta tags `og:` / `product:` — **prioridad 1 (baratísimo)**

```html
<meta property="og:type" content="product" />
<meta property="og:title" content="BICICLETA MTB SCOTT CONTRAIL 40" />
<meta property="og:url" content="…/bicicleta-mtb-scott-contrail-40.html" />
<meta property="og:availability" content="in stock" />       <!-- o "out of stock" -->
<meta property="product:price:amount" content="3811800" />
<meta property="product:price:currency" content="PYG" />
<meta property="product:brand" content="SCOTT" />
```

### 4.3 `x-magento-init` — **prioridad 2 (datos ricos)**

Bloques JSON (no `data-mage-init`, que solo trae widgets de UI). En la ficha aparecen, entre otros:

| Módulo | Qué aporta |
|---|---|
| `Magento_Swatches/js/swatch-renderer` | `jsonConfig`: attributes, optionPrices, index, sku, salable, images por variante |
| `priceBox` | `priceConfig.priceFormat` + `prices` (final/old/base) |
| `mage/gallery/gallery` | `data[]` con `thumb`, `img`, `full`, `caption`, `position`, `isMain`, `type` (`image`/`video`) |
| `SummaSolutions_StorePickup` | `stockItems: [{sku, qty}]` — **qty NO confiable** (ver abajo) |
| `Magento_Customer/js/customer-data` | secciones de cliente (vacías para anónimo) |
| `Meta_Conversion/js/*` + GTM | ver 4.4 |

**`window.checkoutConfig` no existe** en páginas públicas (0 ocurrencias en categoría y ficha). `Magento_PageCache/js/form-key-provider` sí está: contiene un `form_key` de sesión — **no usarlo**, es solo para POST.

**Trampa detectada:** el JSON de store-pickup

```json
"stockItems" : [ { "sku": "410116726", "qty": 1 } ]
```

devolvió **`qty: 1` también en un producto agotado** (`MVUPRUNPLUS`). Es un valor por defecto del módulo, **no stock real** → no usarlo como inventario.

### 4.4 `dataLayer` (GTM / Meta Conversions API) — **prioridad 2 (mapeo a categoría)**

En cada ficha hay un JSON escapado (dentro de `<script>`) con:

```json
{"content_name":"CASCO SCOTT JIBE PM - GRIS",
 "contents":"[{\"id\":\"SC275226GPM\",\"quantity\":1}]",
 "content_category":"REPUESTOS Y ACCESORIOS DE BICICLETAS,ACCESORIOS,ACCESORIOS DE BICICLETAS",
 "value":246500,"currency":"pyg"}
```

Sirve para obtener **la ruta de categoría del producto** y validar SKU/precio (fuente independiente para testing de contrato).

### 4.5 Orden de confiabilidad sugerido

1. `meta[property="product:price:amount"]` / `og:availability` / `product:brand` / `itemprop` (microdata) — están pensados para consumo máquina.
2. `jsonConfig` de swatch (`optionPrices`, `sku`, `salable`) — JSON estructurado, sobrevive a cambios de CSS.
3. Regex sobre textos (`[data-price-amount]`, `toolbar-amount`, `[data-product-sku]`) — semántica de Magento estándar.
4. Selectores DOM del tema (`.product-item-brand`, `.onlycatalog-message`, `.percentage-discount`) — **los más frágiles**.

---

## 5. Comportamiento HTTP

### 5.1 Headers por tipo de recurso

| | HTML (categoría/ficha) | `sitemap.xml` | Imagen `media/catalog/product/` |
|---|---|---|---|
| Status | 200 / 404 | 200 | 200 |
| `Cache-Control` | **`no-store, no-cache, must-revalidate, max-age=0`** | `public, max-age=86400` | `max-age=31536000` |
| `ETag` | **ausente** | `W/"6ad82b07-519cf8"` | `"AYJmsya/2SbAnmiJS7KCrRf8sP56IGCxAM8T4wmyi1M"` |
| `Last-Modified` | **ausente** | `Wed, 21 Oct 2026 03:01:27 GMT` | — |
| `Expires` | …+1 h (contradice `no-store`) | — | …+1 año |
| `Age` | 0 (primera visita) | 1.734 s | 62.039 s |
| `X-Cache` (Fastly) | `MISS, MISS, MISS` | `MISS, HIT, MISS` | `MISS, MISS, MISS` |
| `X-Served-By` | 3 hops: `cache-iad-*` → `cache-eze-*` (Buenos Aires) | idem | idem |
| `Vary` | `Accept-Encoding,Cookie` | `Accept-Encoding,Cookie` | `Accept` |
| `content-encoding` | gzip | (no en HEAD; GET completo 5,1 MiB) | (binario) |
| Otros | `x-esi:1`, `x-platform-server`, `x-debug-info`, `x-timer`, `CSP-Report-Only`, `X-Frame-Options`, HSTS | `content-type: text/xml` | `content-type: image/jpeg` |

**Consecuencias prácticas:**

- **No hay validadores en el HTML** → un request condicional (`If-None-Match` + `If-Modified-Since`) **devuelve 200 completo**, no 304. Probado: 74.362 bytes con `If-None-Match: "recon-test-etag"`. No se ahorra ancho con reintentos condicionales en fichas.
- El `sitemap.xml` **sí tiene validadores** (`ETag` + `Last-Modified`, `max-age=86400`) → ahí un `304` es barato y es la base del detector de cambios (§6.3).
- **`Set-Cookie` no aparece** en páginas 200 anónimas; sí aparece `PHPSESSID` en los **404**. Es decir: navegación anónima es *stateless* y cacheable de punta a punta.
- Aunque el HTML dice `no-store`, en una repetición del mismo producto el último hop devolvió `HIT` con `Age: 184` s → **puede haber reutilización de caché intermedia**. Al sincronizar precios, asumir que una lectura puede tener **minutos** de antigüedad.

### 5.2 Tamaños y tiempos (medidos)

| Recurso | Decodificado | En el cable (gzip) |
|---|---:|---:|
| Categoría BICICLETAS p1 (36 productos, archivo del Lead) | 514 KB | ~81 KB |
| Categoría con `limit=64` | 656 KB | ~106 KB |
| Categoría FITNESS | 380 KB | ~79 KB |
| Ficha configurable (11 variantes + 20 relacionados) | 333 KB | ~74 KB |
| Ficha simple | 190 KB | ~61 KB |
| Ficha agotada | 259 KB | ~69 KB |
| Página 404 | 150 KB | **150 KB (sin gzip)** |
| `sitemap.xml` | **5.348.600 bytes** | ~5,1 MiB (GET completo) |

- Timing: **mín 0,71 s · mediana 1,13 s · promedio 1,32 s · máx 3,21 s** (el máximo fue la página de 656 KB).
- Total descargado en el relevamiento: **2,72 MB** en 41 requests (sin contar el sitemap que ya estaba descargado).
- Relación gzip ≈ 6–7× en HTML: parsear siempre el cuerpo descomprimido (curlc con `--compressed` / `requests` lo hace solo).

### 5.3 Rate limit / bloqueo / anti-bot

- **41 requests** espaciados ≥1,3 s, UA `BiciTiendaReconBot/0.1 (…; contacto: …)`: **39×200, 2×404, 0×403, 0×429, 0×503, sin captcha, sin challenge JS, sin fingerprinting visible**.
- No se probó concurrencia ni ráfagas (intencionalmente). **No hay evidencia de rate limit**, pero tampoco evidencia de tolerancia: mantener ≥1 req/s y backoff exponencial ante 429/503.
- `robots.txt` (verificado por el Lead, no re-pedido): `Disallow /js/, /lib/, /media/, /skin/, /*?, /checkout/, /customer/, /catalog/product/view/`; `Allow /media/catalog/product/`. → **no** se deben crawlear URLs con query (`?p=`, filtros) ni `/catalog/product/view/…` (§8).

---

## 6. Sitemap y `lastmod` como detector de cambios

### 6.1 Composición (`/sitemap.xml`, 3.922 `<url>`, 5.348.600 bytes)

| Tipo | Cantidad | Notas |
|---|---:|---|
| Home | 1 | sin `lastmod` (la única) |
| Categorías `.html` | 31 | 6 de primer nivel (`bicicletas`, `fitness`, `autoaccesorios`, `indumentaria`, `promociones`, `cyberday`) + 25 subcategorías |
| Categorías sin SEO (`/catalog/category/view/id/…`) | 9 | IDs 506, 743, 744, 841, 842, 847, 849, 851, 852 |
| Fichas SEO `.html` | **3.747** | 3.699 de 1 segmento + 45 de 2 segmentos (slug con `/`) + 3 de 3 segmentos |
| Fichas sin SEO (`/catalog/product/view/id/…`) | **63** | **prohibidas por robots** |
| CMS / landings / blogs | 71 | `quienes-somos`, `blog-*`, `beneficios-bancarios`, `demo`, etc. |
| **Total fichas estimadas** | **3.810** | 3.747 + 63 |

- Todas las URLs traen `<changefreq>daily</changefreq>` y `<priority>` (0.5, home 1.0); hay **7.597 `<image:loc>`** (≈2 imágenes por ficha) y **0** `xhtml:link` (sin variantes hreflang).
- **No hay duplicado por variante**: cada configurable tiene **una** URL. Sí hay duplicación por el par SEO/no-SEO y por el catálogo "variante-como-producto" legacy (218 URLs con SKU/talle en el slug, ej. `bici-scott-scale-940-large-41011329l.html`).

### 6.2 `lastmod`: distribución y veredicto

- 3.921 de 3.922 URLs tienen `lastmod` (ISO-8601 UTC). Rango: `2019-10-07` → `2026-10-21T01:08:56Z`.
- **Se actualiza en bloque**, no por cambio real:

| Día del `lastmod` | URLs de ficha |
|---|---:|
| 2026-10-20 | **2.216** |
| 2026-08-04 | **1.066** |
| 2026-10-19 | 383 |
| 2024-04-15 | 48 |
| 2023-05-16 | 35 |
| resto | < 50 |
| **fichas con `lastmod` < 2025** | **88** |

- El máximo (`2026-10-21T01:08:56Z`) coincide con la `Last-Modified` HTTP del sitemap (`2026-10-21T03:01:27Z`) → **el sitemap se regenera una vez por día, ~00:00 hora Paraguay (03:00 UTC)**.

**Veredicto:**

- ❌ `lastmod` **no sirve** para detectar cambios de precio: 2.216 fichas cambiaron "ayer" y 1.066 en una sola fecha de agosto; un cambio de precio no se distingue de una edición de texto o de un reproceso masivo del PIM.
- ❌ El sitemap **no es un inventario confiable**: contiene URLs muertas (1 de 1 probada derivada del sitemap → **404**) y no cubre todo lo visible (3.810 URLs de ficha vs 2.698 productos en los 4 pilares; la diferencia se explica por categorías ocultas, duplicados y productos despublicados/legacy).
- ✅ **Sí sirve para detectar altas y bajas** si se usa el `ETag`: un `GET` condicional con `If-None-Match: W/"6ad82b07-519cf8"` devolverá `304` mientras el set de URLs no cambie, a costo casi nulo. Cuando cambie (`200`), se hace diff de `<loc>` y se procesan solo las nuevas.

### 6.3 Receta de detección de cambios (resumen)

```
1) GET /sitemap.xml  con If-None-Match del ETag guardado   → 1 request/día
   - 304 → no cambió el inventario de URLs: no hacer nada
   - 200 → guardar nuevo sitemap, diff de <loc>, encolar altas/bajas
2) Barrido de precios por categoría (post 1, ver §9)      → ~45 requests
   - comparar hash por SKU contra la base local
3) Solo para productos nuevos/cambiados: GET de la ficha  → N requests
```

---

## 7. Cobertura por categoría

Total del catálogo en los pilares: **5.380 resultados** sumando categorías (con solapamiento, un producto aparece en varias). Cada categoría tiene **36 productos por página** (default). Las columnas "solo catálogo" y "agotados" se midieron **solo en la página 1**.

| Categoría | URL | Total | 36/pág | 64/pág | sin precio (p1) | agotados (p1) |
|---|---|---:|---:|---:|---:|---:|
| BICICLETAS | `/bicicletas.html` | 1.302 | 37 | 21 | 0 | 0 |
| ├ MTB | `/bicicletas/mtb.html` | 420 | 12 | 7 | 5 | 12 |
| ├ RUTA | `/bicicletas/ruta.html` | 18 | 1 | 1 | 0 | 18 |
| ├ URBANAS | `/bicicletas/urbanas.html` | 7 | 1 | 1 | 7 | 0 |
| ├ INFANTIL | `/bicicletas/infantil.html` | 154 | 5 | 3 | 7 | 18 |
| ├ ELECTRICAS | `/bicicletas/electricas.html` | 7 | 1 | 1 | 6 | 0 |
| ├ ACCESORIOS/REPUESTOS | `/bicicletas/repuestos-de-bicicletas.html` | 752 | 21 | 12 | 0 | 0 |
| FITNESS | `/fitness.html` | 1.233 | 35 | 20 | 0 | 0 |
| ├ CINTAS | `/fitness/cintas.html` | 48 | 2 | 1 | 6 | 5 |
| ├ ELÍPTICAS | `/fitness/elipticas.html` | 7 | 1 | 1 | 0 | 1 |
| ├ BICICLETAS | `/fitness/bicicletas.html` | 24 | 1 | 1 | 0 | 6 |
| ├ ACCESORIOS | `/fitness/accesorios.html` | 974 | 28 | 16 | 0 | 0 |
| ├ ABDOMINALERAS | `/fitness/abdominalera.html` | 3 | 1 | 1 | 0 | 0 |
| ├ SPINNING | `/fitness/spinning.html` | 11 | 1 | 1 | 0 | 4 |
| ├ REMOS | `/fitness/remos.html` | 13 | 1 | 1 | 0 | 2 |
| ├ ESCALADORAS | `/fitness/escaladoras.html` | 4 | 1 | 1 | 0 | 2 |
| ├ SUPLEMENTOS | `/fitness/suplementos-alimenticios.html` | 67 | 2 | 2 | 0 | 0 |
| INDUMENTARIA | `/indumentaria.html` | 141 | 4 | 3 | 0 | 0 |
| ├ REMERAS | `/indumentaria/remeras.html` | 82 | 3 | 2 | 0 | 9 |
| ├ ABRIGOS | `/indumentaria/abrigos.html` | 12 | 1 | 1 | 0 | 11 |
| ├ CALZADOS | `/indumentaria/calzados.html` | 12 | 1 | 1 | 0 | 5 |
| ├ MOCHILAS | `/indumentaria/mochilas.html` | 7 | 1 | 1 | 0 | 5 |
| ├ SHORTS | `/indumentaria/shorts.html` | 20 | 1 | 1 | 0 | 0 |
| ├ GUANTES | `/indumentaria/guantes.html` | 6 | 1 | 1 | 0 | 0 |
| ├ LENTES | `/indumentaria/lentes.html` | 13 | 1 | 1 | 0 | 0 |
| AUTOACCESORIOS | `/autoaccesorios.html` | 22 | 1 | 1 | 0 | 3 |
| ├ PORTA EQUIPAJES | `/autoaccesorios/portabultos.html` | 12 | 1 | 1 | 0 | 0 |
| └ PORTABICICLETAS | `/autoaccesorios/portabici.html` | 9 | 1 | 1 | 0 | 2 |
| **PROMOCIONES** | `/promociones.html` | **0** | — | — | — | — |
| **CYBERDAY** | `/cyberday.html` | n/d | — | — | — | — |

**Categorías ocultas** (no están en el menú de primer nivel como URL propia, pero sí en el menú desplegable y en el sitemap como `/catalog/category/view/…`). No se midió su conteo (fuera de presupuesto de requests):

| Categoría | URL | ID |
|---|---|---|
| BICICLETAS › HIDRATACIÓN | `/catalog/category/view/s/hidratacion/id/842/` | 842 |
| BICICLETAS › TRANSPORTE | `/catalog/category/view/s/transporte/id/849/` | 849 |
| FITNESS › TRINEO | `/catalog/category/view/s/trineo/id/743/` | 743 |
| FITNESS › SKI | `/catalog/category/view/s/ski/id/744/` | 744 |
| FITNESS › HIDRATACIÓN | `/catalog/category/view/s/hidratacion/id/841/` | 841 |
| FITNESS › BANCOS | `/catalog/category/view/s/bancos/id/847/` | 847 |
| FITNESS › PILATES | `/catalog/category/view/s/pilates/id/851/` | 851 |
| FITNESS › MÁQUINAS DE GIMNASIO | `/catalog/category/view/s/maquinas-de-gimnasio/id/852/` | 852 |
| (sin identificar, `lastmod` 2024-06-03) | `/catalog/category/view/id/506` | 506 |

**Notas de cobertura:**

- `promociones.html` **no es una categoría de producto**: es una landing de PageBuilder (`data-content-type="html"|"row"`, 0 tarjetas de producto, 0 `data-price-amount`). Las promos se descubren por el badge `HASTA x% OFF`, por la faceta `?descuento=…` o por el filtro de `product_list_order=descuento`.
- El catálogo **no es solo bicis**: el sitemap incluye repuestos de moto/auto del grupo Chacomer (cubetas, caboforro, `solucion-pparche`, etc.) y landings de motos. Para una tienda de ciclismo hay que **filtrar el vertical** (por `content_category` y por la spec "Tipo de Producto").
- Detalle llamativo: hay categorías casi íntegramente agotadas (RUTA: 18/18, ABRIGOS: 11/12) y categorías casi íntegramente "solo catálogo" (URBANAS: 7/7 sin precio). Hay que modelar ambos estados.

---

## 8. Restricciones de `robots.txt` y cortesía

`robots.txt` (verificado por el Lead):

```
Disallow: /js/
Disallow: /lib/
Disallow: /media/
Disallow: /skin/
Disallow: /*?          ← prohíbe TODA URL con query string
Disallow: /checkout/
Disallow: /customer/
Disallow: /catalog/product/view/
Allow: /media/catalog/product/
```

| URL que querríamos usar | ¿Permitida? | Alternativa |
|---|---|---|
| `/bicicletas.html` (base) | ✅ | usar con `?product_list_limit=64`… ❌ (query) |
| `/bicicletas.html?p=2` | ❌ (`/*?`) | — |
| `/bicicletas.html?color_bicicletas=NEGRO` | ❌ (`/*?`) | — |
| `/bicicleta-mtb-scott-contrail-40.html` | ✅ | vía preferida |
| `/catalog/product/view/id/463807/…` | ❌ | exigir/mapper a URL SEO |
| `/sitemap.xml` | ✅ | vía preferida |
| `/media/catalog/product/…` | ✅ | imágenes |

**Implicancia:** el `robots.txt` **excluye explícitamente la paginación y los filtros**, que es justo lo que necesita un barrido de catálogo. El diseño "robots-compatible" es:

1. Descubrir fichas vía `sitemap.xml` (permitido) y seguir solo URLs `.html` SEO (permitidas).
2. Evitar `/catalog/product/view/id/…` (prohibido) y deduplicar esas fichas por su URL SEO cuando exista.
3. No usar `?p=` / facetas como fuente de barrido (prohibido): si se necesitan, pedir autorización escrita a Ciclovia/Chacomer.

Recomendación operativa (independiente de robots): UA identificable con contacto, **1 request cada 1–2 s**, sin concurrencia, `Retry-After`/backoff ante 429/503, preferir el `304` del sitemap y no re-descargar páginas sin necesidad. Con 41 requests y 2,7 MB no hubo ninguna señal de bloqueo.

---

## 9. Estrategia de sincronización recomendada

**Fase 0 — Bootstrap (una vez):** bajar `sitemap.xml` + `robots.txt`; recorrer los 4 pilares con `?product_list_limit=64` (45 páginas); con las tarjetas armar el catálogo base (pid, SKU, precios, variantes); a las fichas SEO listadas solo si hace falta detalle. Poblar el mapa `product_id ↔ SKU ↔ URL`.

**Fase 1 — Detector de altas/bajas (diaria, ~1 request):** `GET /sitemap.xml` condicional con `If-None-Match`. `304` → fin. `200` → diff de `<loc>`; altas → encolar; bajas → marcar como no publicadas tras 2 días de ausencia (evita falsos positivos por caché).

**Fase 2 — Barrido de precios/stock (cada 6–12 h, ~45 requests):** para cada pilar, páginas con `?product_list_limit=64` (BICICLETAS 21 + FITNESS 20 + INDUMENTARIA 3 + AUTOACCESORIOS 1). De cada tarjeta extraer:
- `product_id`, nombre, marca, URL;
- precios `finalPrice`/`oldPrice` y (si configurable) `jsonConfig.optionPrices` por hijo + `jsonConfig.sku` + `jsonConfig.salable`;
- flags `Sin stock` y `onlycatalog-message`.

Comparar contra el estado guardado (hash por SKU). Marcar cambios.

**Fase 3 — Detalle bajo demanda (solo cambios):** para productos nuevos o con cambio estructural, `GET` de la ficha SEO → especificaciones, galería, descripción, relacionados, `content_category`, microdata (fuente de validación).

**Frescuras:** no confiar en una única lectura si el precio salta; el HTML puede venir de caché intermedia con `Age` de minutos. Releer una vez tras ≥5 min antes de disparar cambios grandes, o exigir 2 lecturas coincidentes para cambios de precio >5 %.

**Presupuesto estimado:** bootstrap ≈ 46 requests (sitemap + 45 páginas); mantenimiento diario ≈ 1 + 45 = 46 requests; con fichas de detalle, +N por cambio. A 1 req/1,5 s ≈ 70 s por pasada. Muy por debajo de cualquier umbral razonable, pero **hay que pedir autorización** por el punto de robots.

**Mapeo mayorista → tienda propia:** `data-price-amount` es el **precio minorista online con descuento** ("Precio EXCLUSIVO Online"), no el mayorista. Guardar por SKU: precio lista (`oldPrice`), precio online (`finalPrice`), % descuento y fecha de lectura; aplicar el margen del revendedor en la capa propia. Confirmar con Ciclovia qué código (padre `410116726` u hijo `4101167M26B`) figura en la lista mayorista.

---

## 10. Riesgos

| # | Riesgo | Prob. | Impacto | Mitigación |
|---|---|---|---|---|
| 1 | Cambio de tema `Chacomer/ciclovia` o de ElasticSuite rompe selectores | Media | Alto | Parsear primero microdata/meta/JSON; tests de contrato con 5 fichas canario; alerta si un campo baja de cobertura (ej. SKU < 95 %) |
| 2 | Fichas sin `canonical` + URLs duplicadas SEO/no-SEO → catálogo duplicado | Alta | Medio | Clave primaria `product_id`; mapear a URL SEO; excluir `/catalog/product/view/…` |
| 3 | Variantes solo en JSON escapado dentro de `<script>` | Alta | Medio | Parser JSON con conteo de llaves (no regex no-greedy); validar contra microdata del padre |
| 4 | SKU padre ≠ SKU hijo (formato distinto) | Alta | **Alto** | Definir con Ciclovia el identificador de la lista mayorista; guardar ambos |
| 5 | Stock: grilla solo informa "Sin stock"; sin cantidades | Alta | Medio | Derivar vendibilidad de `salable`; mostrar "consultar stock"; **no** usar `stockItems.qty` |
| 6 | Productos "solo catálogo" sin precio (cuentan en el total) | Alta | Medio | Flag `onlycatalog`; publicar como "consultar" o excluir |
| 7 | Precio leído desde caché intermedia (`Age` de minutos, HTML sin validadores) | Media | Medio | Doble lectura en cambios; registrar `Age`/`Date` de cada respuesta |
| 8 | `robots.txt` prohíbe `/*?` y `/catalog/product/view/` | Alta | **Alto (legal)** | Diseño sitemap+fichas SEO; pedir autorización escrita; no usar `?p=` masivamente |
| 9 | Sitemap con URLs muertas (404) e incompleto (3.810 vs 2.698) | Alta | Medio | Validar con la grilla de pilares; expirar por ausencia; no confiar en `lastmod` |
| 10 | Catálogo mezcla moto/auto (grupo Chacomer) | Alta | Medio | Filtrar por `content_category`/specs "Tipo de Producto" |
| 11 | Categorías ocultas (trineo, ski, hidratación, bancos, pilates, máquinas) con stock | Media | Bajo | Listarlas y barrerlas si el negocio las vende |
| 12 | Cambios silenciosos: precio igual, descripción/imagen distinta | Media | Bajo | Hash por campo; avisar solo campos que importan |
| 13 | Volumen: 3.810 fichas × ~250 KB decodificados ≈ 1 GB por pasada completa | Baja | Medio | Nunca bajar todo: grilla (45 req) + detalle incremental |
| 14 | Bloqueo por ráfagas o por UA genérico | Baja | Alto | UA identificable con contacto, 1 req/s, backoff, sin paralelismo |
| 15 | Derechos de imágenes/descripciones al replicar | Media | Medio | Descargar y rehospedar solo si hay permiso; atribuir marca; no copiar descripciones textualmente |
| 16 | `lastmod` masivo genera falsos cambios | **Alta** | Bajo | Usar `ETag` del sitemap + hash propio; ignorar `lastmod` para precio |

---

## 11. Alternativas (vías oficiales y semi-oficiales)

| Vía | Estado | Comentario |
|---|---|---|
| `/graphql` | ❌ 403 (Varnish) | Bloqueado a nivel CDN; no insistir |
| `/rest/V1` | ❌ 401 | Requiere token de integración |
| **Feeds de Google Shopping / Merchant Center** | No encontrados en el HTML | No hay `<link rel="alternate">` de feed ni evidencia. Preguntar a Ciclovia/Chacomer si publican feed (sería la fuente ideal: SKU+precio+stock+GTIN en un solo archivo) |
| **API del PIM** (origen de `pim-assets`) | Detectado indirectamente | Las imágenes vienen de `api-v1.1-file-public_files-pim-assets-…`; existe un PIM con API. Pedir acceso/contrato |
| **Acuerdo comercial / lista mayorista** | Recomendado | El negocio es revendedor: lo natural es solicitar feed mayorista (CSV/XML/ERP) y automatizar contra eso, no contra el retail |
| **Endpoint AJAX de facetas** (`/catalog/navigation_filter/ajax/id/<cat>/?cat=<cat>&filterName=<attr>`) | **Pendiente de probar** | JSON liviano con items, counts y URLs; útil para descubrimiento de facetas, **no** trae precios |
| `sitemap.xml` + microdata + `jsonConfig` | ✅ Verificado | Vía sin credenciales, la que sostiene el PoC |

---

## 12. Tabla final: campo → selector/regex → confiabilidad

> Convención: **alta** = semántica estable de Magento o dato pensado para máquinas; **media** = depende del tema pero con varias fuentes; **baja** = texto de negocio o dato no confiable.

| Campo | Selector / regex | Fuente | Conf. |
|---|---|---|---|
| Total de productos de categoría | `//*[contains(@class,"toolbar-amount")]` + `/([\d\.]+)\s+Resultados/` | HTML categoría | alta |
| Páginas de una categoría | `ceil(total / 36)` o `/64` | derivado | alta |
| Límite por página | `?product_list_limit=36\|48\|64` | query | alta |
| Orden | `?product_list_order=position\|name\|price\|updated_at\|descuento` + `?product_list_dir=asc\|desc` | query | alta |
| Filtro por atributo | `?<code>=<valor>` (`brand`, `color_bicicletas`, `tama_o_bicicletas`, `aro`, `modelo`, `tipo_de_bicicleta`, `descuento`, …) | query | alta |
| Rango de precio | `?price=<desde>-<hasta>` | `urlTemplate` del slider | media (no probado) |
| Filtro activo (estado) | `.filter-current .filter-label` + `.filter-value` | HTML categoría | alta |
| Tarjeta de producto | `ol.products.items.product-items > li.item.product.product-item` (excluir `ol.product-items-names li` y el `li` plantilla sin `data-role="priceBox"`) | DOM | alta |
| URL del producto | `a.product-item-link@href` (formas: `/slug.html` o `/catalog/product/view/id/<id>/category/<cat>/`) | DOM | alta (dedupe por id) |
| `product_id` | `[data-role="priceBox"]@data-product-id` · `form[data-role="tocart-form"] input[name="product"]@value` · `/product/(\d+)/` en `@action` | DOM | alta |
| Nombre | `strong.product.name.product-item-name` (texto) | DOM | alta |
| Marca | `div.product-item-brand span` · `meta[property="product:brand"]` (ficha) | DOM/meta | alta |
| SKU en tarjeta | `form[data-role="tocart-form"]@data-product-sku` | DOM | alta (simple=SKU real; configurable=SKU padre) |
| SKU real de ficha | `.product.attribute.sku [itemprop="sku"]` · `itemprop="sku">([^<]+)` | microdata | alta |
| SKU de variantes | `/"sku":\{(?:"\d+":"[^"]+",?)+\}/` dentro del `jsonConfig` de swatch | JSON | alta |
| Precio final (tarjeta) | `[data-price-type="finalPrice"]@data-price-amount` | DOM | alta |
| Precio anterior (tarjeta) | `[data-price-type="oldPrice"]@data-price-amount` | DOM | alta |
| Precio final (ficha) | `[data-price-type="finalPrice"]@data-price-amount` · `meta[property="product:price:amount"]` · `[itemprop="price"]@content` | 3 fuentes | alta |
| Precio por variante | `"optionPrices":\{"(\d+)":\{[^}]*"finalPrice":\{"amount":(\d+)\}` | JSON | alta |
| Moneda | `meta[property="product:price:currency"]` = `PYG` · `priceFormat.pattern` | meta/JSON | alta |
| Formato numérico | `"priceFormat":\{[^}]*"precision":0[^}]*\}` (entero, miles con `.`) | JSON | alta |
| Etiqueta del precio | `.price-label` (`Valor mínimo`/`Precio especial`/`Precio habitual`) | DOM | media |
| Descuento mostrado | `.percentage-discount .special-price-discount` → `HASTA (\d+)% OFF` | DOM | media |
| Descuento calculado | `1 - final/old` (enteros) | derivado | alta |
| Badge comercial | `.product-item-badge img@src` (`/media/catalog/badges/PRECIO_Exclusivo_Online.png`) | DOM | media |
| Stock (ficha) | `.product-info-stock-sku .stock.available span` = `En stock` · `.stock.unavailable span` = `Sin stock` | DOM | alta |
| Disponibilidad (meta) | `meta[property="og:availability"]` = `in stock` / `out of stock` | meta | alta |
| Stock en grilla | `.stock.unavailable span` = `Sin stock` (solo negativo) | DOM | alta (negativo) |
| Stock por variante | `"salable":\{…\}` → unión de `product_id` listados | JSON | media-alta (derivado) |
| Producto sin precio online | `.onlycatalog-message` / texto `Adquiéralo en un distribuidor autorizado` | DOM | alta |
| Atributos de variante | `"attributes":\{"(\d+)":\{"id".*?"code":"([^"]+)".*?"label":"([^"]+)".*?"options":\[(.*?)\]\}` | JSON | alta |
| Vínculo variante↔opciones | `"index":\{"(\d+)":\{"(\d+)":"(\d+)"` | JSON | alta |
| Imágenes (galería) | `"data":\s*(\[\{"thumb".*?\}\]),\s*"options"` → `img`/`full`/`thumb` | JSON | alta |
| Imagen principal | `meta[property="og:image"]` · primera de galería | meta/JSON | alta |
| URL base de imagen | `/https:\/\/www\.ciclovia\.com\.py\/media\/catalog\/product\/[^"\\]+/` (antes de `?`) | regex | alta |
| Imagen en grilla (fondo) | `span.product-image-photo[style*="background-image"]` → `url\('([^']+)'\)` | DOM | media |
| Descripción | `.product.attribute.description` · `[itemprop="description"]@content` | DOM/microdata | media (texto corto autogenerado) |
| Especificaciones | `#product-attribute-specs-table tr` → `th` / `td` | DOM | alta |
| Categoría del producto | `"content_category":"([^"]*)"` (dataLayer) | JSON | media |
| Relacionados | `.block.related li.product-item` (nombre, URL, precio, stock) | DOM | media |
| Productos similares (conteo) | `len(//*[contains(@class,"block related")]//li[contains(@class,"product-item")])` | DOM | media |
| Configurable sí/no | presencia de `Magento_Swatches/js/swatch-renderer` en la tarjeta/ficha | JSON | alta |
| Cantidad exacta en stock | `"stockItems"\s*:\s*\[\s*\{[^}]*"qty"\s*:\s*(\d+)` | JSON | **baja** (qty=1 incluso agotado) |
| `canonical` de ficha | `//link[@rel="canonical"]/@href` | **no existe** | baja (ausente) |
| `robots` de ficha | `meta[name="robots"]` = `INDEX,FOLLOW` | meta | alta |
| URL de ficha en sitemap | `<loc>(.*?)</loc>` | XML | alta |
| `lastmod` de ficha | `<lastmod>(.*?)</lastmod>` | XML | **baja** (cambios en bloque) |
| Detección de refresh del sitemap | `ETag` / `Last-Modified` + `If-None-Match` → 304 | HTTP | alta |
| Estado HTTP / 404 | `curl -o /dev/null -w '%{http_code}'` | HTTP | alta |
| Caché de HTML | `Cache-Control`, `Age`, `X-Cache` | HTTP | alta (dato) |
| Bloqueo / rate limit | status = 403/429/503 | HTTP | no observado en 41 requests |

---

## Anexo A — Método reproducible

```bash
UA='BiciTiendaReconBot/0.1 (analisis de catalogo; contacto: TU-CONTACTO)'
D="$TEMP/ciclovia-recon"; mkdir -p "$D"

# 1. Base de categoría (sin query = permitido por robots)
curl -sS --compressed -A "$UA" -o "$D/cat.html" -D "$D/cat.hdr" \
  'https://www.ciclovia.com.py/bicicletas.html'

# 2. Página 2 y límite 64 (ojo: robots prohíbe query strings)
curl -sS --compressed -A "$UA" -o "$D/p2.html" \
  'https://www.ciclovia.com.py/bicicletas.html?p=2'
curl -sS --compressed -A "$UA" -o "$D/l64.html" \
  'https://www.ciclovia.com.py/bicicletas.html?product_list_limit=64'

# 3. Ficha SEO
curl -sS --compressed -A "$UA" -o "$D/ficha.html" \
  'https://www.ciclovia.com.py/bicicleta-mtb-scott-contrail-40.html'

# 4. Sitemap + validadores
curl -sS -I -A "$UA" 'https://www.ciclovia.com.py/sitemap.xml'
curl -sS --compressed -A "$UA" -o "$D/sitemap.xml" 'https://www.ciclovia.com.py/sitemap.xml'

# 5. Condicional sobre el sitemap (esperado 304 si no cambió)
curl -sS -o /dev/null -w '%{http_code}\n' -A "$UA" \
  -H 'If-None-Match: W/"6ad82b07-519cf8"' 'https://www.ciclovia.com.py/sitemap.xml'
```

Extracción mínima en Python (sin dependencias raras: `lxml` + `json` + `re`):

```python
import re, json
from lxml import html

def productos_de_categoria(ruta_html):
    raw = open(ruta_html, encoding='utf-8').read()
    doc = html.fromstring(raw)
    total = int(re.search(r'([\d\.]+)\s+Resultados',
                          ' '.join(doc.xpath('string(//*[contains(@class,"toolbar-amount")])').split())
                          ).group(1).replace('.', ''))
    items = []
    for li in doc.xpath('//ol[contains(@class,"product-items")][1]/li[contains(@class,"product-item")]'):
        pid = li.xpath('.//*[@data-role="priceBox"]/@data-product-id')
        if not pid:                      # plantilla de comparar / sin precio
            if li.xpath('.//*[contains(@class,"onlycatalog-message")]'):
                items.append({'solo_catalogo': True,
                              'url': (li.xpath('.//a[contains(@class,"product-item-link")]/@href') or [None])[0]})
            continue
        items.append({
            'product_id': pid[0],
            'nombre': ' '.join(li.xpath('string(.//strong[contains(@class,"product-item-name")])').split()),
            'marca': ' '.join(li.xpath('string(.//*[contains(@class,"product-item-brand")])').split()),
            'url': (li.xpath('.//a[contains(@class,"product-item-link")]/@href') or [None])[0],
            'precio': int(li.xpath('.//*[@data-price-type="finalPrice"]/@data-price-amount')[0]),
            'precio_anterior': (li.xpath('.//*[@data-price-type="oldPrice"]/@data-price-amount') or [None])[0],
            'sku_padre': (li.xpath('.//form[@data-role="tocart-form"]/@data-product-sku') or [None])[0],
            'agotado': bool(li.xpath('.//*[contains(@class,"stock unavailable")]')),
        })
    return total, items
```

> Nota: el `jsonConfig` de variantes es JSON anidado dentro de un `<script>`; **no** extraerlo con una regex no-greedy (`\{.*?\}`), hay que hacer *brace matching* o buscar `"jsonConfig":` y parsear hasta la llave de cierre.

---

## Anexo B — Presupuesto de requests ejecutado

| Bloque | Requests | Detalle |
|---|---:|---|
| Estructura | 9 | `?p=2`, `limit=64`, orden por precio, filtro color, 2 fichas, 2 URLs 404, 1 URL sin SEO |
| Cobertura | 28 | 4 pilares + 24 subcategorías (ver §7) |
| Caché/sitemap/imagen | 3 | `HEAD sitemap.xml`, `HEAD imagen`, ficha con `If-None-Match`/`If-Modified-Since` |
| Ficha agotada | 1 | `cinta-de-caminar-electrica-up-run-plus.html` |
| **Total** | **41** | **39×200 + 2×404 · 0×403 · 0×429 · 2,72 MB · delay 1,3 s · UA identificable** |

---

## Anexo C — Pendientes (no cubiertos por este relevamiento)

1. **Probar el endpoint AJAX de facetas** (`/catalog/navigation_filter/ajax/id/<cat>/?cat=<cat>&filterName=<attr>`) — puede reducir a la mitad el costo de descubrimiento.
2. **Probar `?price=<desde>-<hasta>`** (rango de precios) y combinaciones de 2 filtros.
3. **Medir las 8 categorías ocultas** (§7) y la categoría 506.
4. **Probar `If-None-Match` sobre `/sitemap.xml`** (se leyó el `ETag`, no se envió el condicional).
5. **Verificar una ficha "solo catálogo"** para confirmar que no expone precio tampoco en `og:product:price:amount`.
6. **`cyberday.html`**: confirmar si es landing o categoría (mismo patrón que `promociones.html`).
7. **Cuantificar URLs muertas del sitemap** con una muestra mayor (aquí: 1 de 1 → 404).
8. **Definir con Ciclovia/Chacomer**: identificador de la lista mayorista (SKU padre vs hijo), autorización de barrido (robots) y existencia de feed (Merchant Center/CSV/API PIM).
9. **Verificar HTTP/2** con un cliente que lo negocie (con `curl` se observó HTTP/1.1).
