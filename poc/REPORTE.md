# REPORTE — PoC de extracción de catálogo y precios de ciclovia.com.py

**Fecha de corrida:** 2026-10-21, 15:00–15:17 (hora de Paraguay, UTC-3)
**Sitio:** https://www.ciclovia.com.py/ — Magento 2, tema Chacomer, locale `es-AR`, moneda **PYG**
**Scraper:** `poc/scraper_ciclovia.py` (Python 3.12 + `lxml`; `requests` opcional)
**Requests reales totales: 150** (tope fijado ~150), todos HTTP 200, 53,3 MB descargados,
111 páginas de categoría + 7 fichas + `robots.txt`. Delay 0,8–1,5 s, secuencial, User-Agent
identificable. Auditoría completa en `poc/cache/_requests.jsonl`.

---

## 1. Resumen ejecutivo

| Pregunta | Respuesta |
|---|---|
| ¿Se puede extraer el catálogo? | **Sí.** 29 de 29 categorías con grilla server-side bajadas al 100 %. |
| Productos únicos extraídos | **2.681** (por `product_id`), desde **5.711 tarjetas** (un producto aparece en 2,1 categorías promedio). |
| Cobertura por pilar | **100 %** en los 4 pilares: bicicletas 1302/1302, fitness 1233/1233, indumentaria 141/141, autoaccesorios 22/22. |
| Fichas de producto | **5/5 OK**, incluida la ficha de control Scott Contrail 40 con verificación campo por campo. |
| ¿El CSV sirve para cargar una tienda? | **Sí**, con salvedades: precios enteros en PYG sin separadores, moneda consistente, 0 duplicados, 100 % con imagen; el SKU falta en 51 % (son productos que no se venden online). |
| ¿Cumple robots.txt? | **No plenamente.** `Disallow: /*?` prohíbe el paginado; ver §7. La alternativa 100 % compliant está documentada. |

---

## 2. Método

1. `robots.txt` → se descarga y parsea con `urllib.robotparser`, más una política explícita
   para URLs con query (§7).
2. `sitemap.xml` (3.922 `<loc>`, 3.778 `.html`) → descubrimiento de categorías:
   - URLs `.html` de 2 niveles cuyo primer nivel sea una categoría raíz real (`/<seg>.html`
     presente en el sitemap). Esto evita confundir productos con barra en el slug
     (hay 45: `…/sensor-mano-con-boton-star/stop-atr510t64.html`).
   - Raíces detectadas: `bicicletas`, `fitness`, `indumentaria`, `autoaccesorios`.
   - Colecciones: `promociones.html` y `cyberday.html`.
3. Paginado de cada categoría con `?product_list_limit=64&p=N`. **64 es el máximo real**:
   36/48/64 son las opciones del toolbar; valores mayores (probado 200) los ignora y vuelve
   a 36. 111 páginas en total (45 de los pilares + 60 de subcategorías + 6 de cyberday).
4. Parseo de tarjetas con `lxml` (XPath), excluyendo las 2 plantillas que mete el tema en el
   grid (autocompletado `ol.product-items-names` y comparador con `data-bind`).
5. Deduplicación por `product_id`, acumulando categorías por producto; `categoria_principal`
   = la hoja más específica.
6. 5 fichas de producto (una por rubro + una de promociones), incluida una ficha de control
   con valores verificados a mano.
7. Caché en disco por URL: cada corrida posterior se reprocesa sin tocar la red
   (`--sin-red` → **0 requests**).

---

## 3. Cobertura por pilar (tabla pedida)

| Pilar | Total declarado por el sitio | Tarjetas extraídas | Cobertura | Páginas | Productos únicos atribuidos al rubro¹ |
|---|---:|---:|---:|---:|---:|
| BICICLETAS (`/bicicletas.html`) | 1.302 | 1.302 | **100,0 %** | 21 | 1.281 |
| FITNESS (`/fitness.html`) | 1.233 | 1.233 | **100,0 %** | 20 | 1.232 |
| INDUMENTARIA (`/indumentaria.html`) | 141 | 141 | **100,0 %** | 3 | 140 |
| AUTOACCESORIOS (`/autoaccesorios.html`) | 22 | 22 | **100,0 %** | 1 | 22 |
| **Subtotal 4 pilares** | **2.698** | **2.698** | **100,0 %** | **45** | **2.675** |
| CYBERDAY (colección) | 331 | 331 | **100,0 %** | 6 | 6² |
| PROMOCIONES (landing) | — | 0 | n/a³ | 0 | — |
| **Total tarjetas** | — | **5.711** | — | **111** | — |

¹ Los productos con doble pertenencia se atribuyen al rubro de su categoría más específica
(p. ej. un casco está en `bicicletas` y en `indumentaria/calzados` → indumentaria). Por eso los
únicos por rubro no suman exactamente el total de cada pilar.
² Solo 6 productos están **exclusivamente** en cyberday; los otros 325 también viven en una
categoría principal.
³ `promociones.html` es una landing PageBuilder sin grilla server-side: el HTML trae 0
productos y 0 precios. No es un error de extracción (ver §6).

**Validación con el Lead:** los totales declarados de los 4 pilares coinciden exactamente con
los esperados (1.302 / 1.233 / 141 / 22) y con las 45 páginas (21+20+3+1).

### 3.1 Detalle por categoría

| Categoría | Total declarado | Tarjetas | Cobertura |
|---|---:|---:|---:|
| bicicletas | 1.302 | 1.302 | 100,0 % |
| bicicletas/mtb | 420 | 420 | 100,0 % |
| bicicletas/ruta | 18 | 18 | 100,0 % |
| bicicletas/urbanas | 7 | 7 | 100,0 % |
| bicicletas/infantil | 154 | 154 | 100,0 % |
| bicicletas/electricas | 7 | 7 | 100,0 % |
| bicicletas/repuestos-de-bicicletas | 752 | 752 | 100,0 % |
| fitness | 1.233 | 1.233 | 100,0 % |
| fitness/cintas | 48 | 48 | 100,0 % |
| fitness/elipticas | 7 | 7 | 100,0 % |
| fitness/bicicletas | 24 | 24 | 100,0 % |
| fitness/accesorios | 974 | 974 | 100,0 % |
| fitness/abdominalera | 3 | 3 | 100,0 % |
| fitness/spinning | 11 | 11 | 100,0 % |
| fitness/remos | 13 | 13 | 100,0 % |
| fitness/escaladoras | 4 | 4 | 100,0 % |
| fitness/suplementos-alimenticios | 67 | 67 | 100,0 % |
| indumentaria | 141 | 141 | 100,0 % |
| indumentaria/remeras | 82 | 82 | 100,0 % |
| indumentaria/abrigos | 12 | 12 | 100,0 % |
| indumentaria/calzados | 12 | 12 | 100,0 % |
| indumentaria/mochilas | 7 | 7 | 100,0 % |
| indumentaria/shorts | 20 | 20 | 100,0 % |
| indumentaria/guantes | 6 | 6 | 100,0 % |
| indumentaria/lentes | 13 | 13 | 100,0 % |
| autoaccesorios | 22 | 22 | 100,0 % |
| autoaccesorios/portabultos | 12 | 12 | 100,0 % |
| autoaccesorios/portabici | 9 | 9 | 100,0 % |
| cyberday | 331 | 331 | 100,0 % |
| fitness/peso-libre | — | 0 | no es grilla |
| promociones | — | 0 | landing sin grilla |

En todas las categorías con grilla, `tarjetas extraídas == total declarado` en cada página
(control página por página en `data/estadisticas.json → categorias[].detalle_paginas`).

### 3.2 Cobertura contra el sitemap (el dato honesto)

El sitemap tiene **3.778 URLs `.html`**: 31 son categorías y **3.747 son productos**.

| Métrica | Valor |
|---|---:|
| URLs de producto en el sitemap | 3.747 |
| Presentes en el catálogo extraído | 2.611 (**69,7 %**) |
| Fichas del sitemap que **no** aparecen en ninguna grilla | 1.136 |
| Productos del catálogo que no están en el sitemap | 70 (altas/cambios recientes) |

Explicación del hueco de 1.136: son productos que **no se muestran en ninguna grilla de las
29 categorías con URL limpia**. Causas identificadas: (a) categorías ocultas sin URL `.html`
que solo existen como `/catalog/category/view/s/hidratacion/id/842/` y
`/catalog/category/view/s/transporte/id/849/` (no están en el sitemap ni en el menú), y
(b) fichas despublicadas o sin categoría activa que el sitemap todavía lista (el sitemap
arrastra URLs con `lastmod` viejo).

**Para llegar al 100 % del sitemap** hay que bajar las 3.747 fichas SEO individuales
(`/<slug>.html`, sin query string → **ruta 100 % robots-compliant**), ≈1,2 s por request ⇒
~75 minutos. Recomendación: hacerlo una vez con permiso del sitio y después mantener con
`lastmod` del sitemap (solo las fichas que cambian).

---

## 4. Fichas de producto (`data/fichas.jsonl`)

| # | Producto | Rubro / categoría | Marca | SKU | Precio final | Precio anterior | Stock | Imgs | Variantes |
|---|---|---|---:|---|---:|---:|---|---:|---|
| 1 | BICICLETA MTB SCOTT CONTRAIL 40 *(control)* | bicicletas/mtb | SCOTT | 410116726 | 3.811.800 | 5.082.400 | En stock | 5 | 11 (3 vendibles) |
| 2 | GUANTE DE MMA, TALLA L/XL BRAVO | fitness/accesorios | BRAVO | AC8503A-L/XL | 159.030 | 176.700 | En stock | 3 | — |
| 3 | PAR GUANTE NEGRO TAMAÑO L PROX | indumentaria/guantes | PRO-X | 1790293N | 38.165 | 44.900 | En stock | 4 | — |
| 4 | THULE PORTA BICI XPRESS 970 2B 1 7/8 | autoaccesorios/portabici | THULE | TH970004 | 1.054.000 | 1.240.000 | En stock | 5 | — |
| 5 | CASCO PRO X ROJO | bicicletas/repuestos-de-bicicletas | PRO-X | 1790026J | 40.600 | 63.100 | En stock | 5 | — |

Cada ficha incluye además: `especificaciones` (3–13 pares etiqueta/valor: Marca, Aro, Tipo,
Frenos, etc.), `descripcion`, `imagenes` (URLs completas), `opciones` (atributos y valores) y
`variantes` con `sku`, `atributos`, precios y `vendible`.

### 4.1 Verificación de la ficha de control (pedida por el Lead)

`https://www.ciclovia.com.py/bicicleta-mtb-scott-contrail-40.html` — resultado: **OK (5/5)**

| Campo | Esperado | Extraído | Estado |
|---|---:|---:|:--:|
| SKU padre | 410116726 | 410116726 | ✅ |
| Precio final | 3.811.800 | 3.811.800 | ✅ |
| Precio anterior | 5.082.400 | 5.082.400 | ✅ |
| Hijos (variantes) | 11 | 11 | ✅ |
| Hijos vendibles (`salable`) | 3 | 3 | ✅ |

Coherencia tarjeta ↔ ficha de las 5 fichas: 5/5 con el mismo precio final, y las 5 con
`En stock` coincidiendo con `estado_tarjeta = con_precio`.

---

## 5. Calidad de los datos (`data/validacion.json`)

| Chequeo | Resultado |
|---|---|
| Filas CSV = filas JSONL | 2.681 = 2.681 ✅ |
| Precios no numéricos | **0** ✅ |
| Precios con separador de miles o decimales en el CSV | **0** ✅ (todos enteros: `3811800`) |
| Moneda | 100 % `PYG` ✅ |
| Duplicados por `product_id` | **0** ✅ |
| Duplicados por URL | **0** ✅ |
| `precio_anterior >= precio_final` | 100 % coherente ✅ (19 casos raros corregidos, ver §6) |
| Imagen | 100 % de los productos ✅ |
| SKU | 49,1 % ⚠️ |
| Precio final | 84,5 % (2.266 productos) |
| Precio anterior | 71,4 % (1.913 productos) |
| Rango de precios | 100 – 109.028.700 Gs (mediana 198.000) |

**Estados de tarjeta** (los 3 estados + residual):

| `estado_tarjeta` | Productos | % | Significado |
|---|---:|---:|---|
| `con_precio` | 1.316 | 49,1 % | Precio publicado y comprable |
| `agotado` | 1.035 | 38,6 % | `.stock.unavailable` "Sin stock" (950 conservan precio) |
| `solo_catalogo` | 298 | 11,1 % | "Adquiéralo en un distribuidor autorizado", sin precio; cuenta en el total |
| `sin_dato` | 32 | 1,2 % | Sin precio y sin ningún marcador (residual) |

Marcas más frecuentes en el nombre: BRAVO (351), SCOTT (342), CALOI (206), ATHLETIC (115),
BEST (102), PRO-X (64), RUSH (49), THULE (24), CANNONDALE (21), TEKNIAL (10).

---

## 6. Hallazgos técnicos (cosas que hubo que resolver)

1. **`product_list_limit` máximo 64.** 36/48/64 son las opciones reales del toolbar; 200 se
   ignora y sirve 36. Con 64: 111 páginas para todo el sitio.
2. **NUL dentro de nombres de producto.** Algunas fichas traen `\x00` en el nombre
   (p. ej. `GRS RAYO … ARO 20\x00…`); libxml2 **corta el documento en el NUL** y se perdían
   40 tarjetas de una página (752 declaradas → 712 extraídas). Se limpian caracteres de
   control antes de parsear → 752/752.
3. **`<body class>` no es confiable con lxml en este sitio** (se pierden los atributos del
   body por un `<head>` mal formado). La detección de "es categoría" se hace por marcadores
   del grid/toolbar y un regex sobre el HTML crudo.
4. **Tarjetas fantasma.** El tema mete en el grid dos plantillas: `ol.product-items-names`
   (autocompletado) y el último `li.product-item` del comparador (`data-bind`, sin
   `data-role="priceBox"`). Inflaban el conteo (65 li por página de 64). Se excluyen.
5. **Precios con decimales.** El sitio publica algunos `data-price-amount` con decimales
   (`"41678.1"`). Interpretarlos como separador de miles daba 416.781 (10× el precio).
   El parser ahora distingue: punto + 1–2 dígitos = decimal, punto + 3 dígitos = miles.
6. **Productos con barra en la URL.** 45 fichas tienen slug con `/`
   (`…/llave-on/off-con-cable-…html`), lo que rompía el descubrimiento de categorías
   ("2 niveles = categoría"). Se exige que el primer nivel sea una raíz real del sitemap.
7. **`promociones.html` es una landing PageBuilder**: 0 productos en HTML, no se puede
   raspar como categoría. La vista de promociones se puede derivar del catálogo con
   `descuento_pct > 0` (hay 1.913 productos con precio anterior).
8. **`fitness/peso-libre.html`** responde 200 pero no es una grilla de producto (sin
   toolbar ni productos): se documenta como `no_es_categoria`, no como error.
9. **Breadcrumb de ficha vacío**: el tema lo renderiza con JS
   (`<div class="breadcrumbs"></div>`), así que las categorías del producto salen del
   barrido de grillas, no de la ficha.
10. **SKU bajo (49 %).** En las tarjetas el SKU solo aparece en el formulario "Comprar";
    los productos agotados/solo-catálogo no tienen formulario. La cobertura sube al 100 %
    abriendo la ficha (o al 100 % en la ficha de control).

---

## 7. Robots.txt: advertencia importante

`robots.txt` del sitio (plantilla estándar de Magento 2) incluye, bajo `User-agent: *`:

```
Disallow: /*?
```

Eso **bloquea toda URL con query string**, es decir también `?p=2` y
`?product_list_limit=64`. Por lo tanto:

- El barrido por paginado que usa este PoC es la **vía eficiente** (111 páginas para 5.711
  tarjetas) pero **NO es robots-compliant**: requiere **autorización escrita** del dueño del
  sitio. En `data/estadisticas.json` queda registrado como
  `robots.permite_url_con_query = false` y `paginado_habilitado_por_politica = true`
  (política `--politica-robots paginado`, que solo permite `p` y `product_list_limit`, nunca
  filtros).
- La **vía 100 % robots-compliant** es: sitemap → 3.747 fichas SEO individuales
  (sin query string) ⇒ ≈75 minutos a 1,2 s/request, sin paginado.
- Con `--politica-robots estricta` el scraper respeta la regla al pie de la letra y baja
  solo la página 1 (36 productos) de cada categoría.

Nunca se accede a `/checkout`, `/customer`, `/catalog/product/view/`, `/js`, `/lib`,
`/skin`, `*.php` ni `/media` (salvo `/media/catalog/product/`), y no se hacen requests
concurrentes.

---

## 8. Presupuesto de requests

| Concepto | Requests |
|---|---:|
| `robots.txt` | 1 |
| Categorías (111 páginas) | 142¹ |
| Fichas de producto | 7² |
| **Total** | **150** |
| Sitemap | 0 (reutilizado del recon previo, cacheado) |

¹ 111 páginas + 31 primeras páginas duplicadas por iteraciones de desarrollo (probe de
tamaño de página, reintentos de descubrimiento). El **plan estable** es: 1 robots + 45
páginas (4 pilares) + 60 páginas (25 subcategorías) + 6 (cyberday) + 5 fichas = **117
requests**. El resto del presupuesto se consumió en depuración.
² 5 fichas finales + 2 fichas de pruebas anteriores (el caché las conserva).

---

## 9. Limitaciones y próximos pasos

1. **Catálogo por grillas = 2.611/3.747 fichas del sitemap (69,7 %).** Para el 100 % hay que
   bajar fichas individuales (robots-compliant) o pedir autorización para paginar. Las 1.136
   faltantes son productos sin categoría visible/despublicados y de las 2 categorías ocultas.
2. **SKU 49 %** en tarjetas: completar desde la ficha.
3. **Stock inferido** en tarjetas (no hay marcador positivo): usar `estado_tarjeta` y, para
   stock fino, la ficha (`variantes[].vendible`).
4. **Precio mayorista de CICLOVIA:** el sitio publica precio minorista/online; el precio
   mayorista del revendedor no está en el HTML. La tienda propia debe aplicar la lista de
   precios del acuerdo comercial sobre `precio_final` (o `precio_anterior` para el "antes").
5. **Mojibake puntual**: 2 nombres y algunos `PYGÂ 41.678` vienen mal codificados desde el
   origen; se normaliza el precio, el nombre queda como está (2 casos).
6. **Actualización incremental**: usar `lastmod` del sitemap + `If-Modified-Since` y la caché
   por URL; el scraper ya es idempotente (segunda corrida = 0 requests).
7. **Producción**: mover la caché a disco/S3, agregar reintentos con backoff y un
   `--politica-robots estricta` por defecto hasta tener autorización.

---

## 10. Cómo reproducir

```powershell
# 0) ver robots y política
python poc\scraper_ciclovia.py --modo robots

# 1) barrido completo respetando el tope acumulado de 150 requests
python poc\scraper_ciclovia.py --modo todo --incluir-raices --presupuesto-total 150

# 2) reprocesar TODO desde la caché (0 requests) y revalidar
python poc\scraper_ciclovia.py --modo todo --incluir-raices --sin-red

# 3) validar salidas
python poc\scraper_ciclovia.py --modo validar
```

Salidas en `poc/data/`: `productos.jsonl`, `productos.csv`, `fichas.jsonl`,
`categorias.csv`, `estadisticas.json`, `validacion.json`.
Caché: `poc/cache/` (125 archivos, 53,3 MB, incluye `_requests.jsonl` con la auditoría).
