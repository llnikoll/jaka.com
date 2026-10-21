# Plan de implementación — Tienda propia con catálogo y precios sincronizados de Ciclovía

**Cliente:** revendedor con precio mayorista de CICLOVIA (Chacomer S.A.E., Paraguay)
**Objetivo:** ofrecer **todo el catálogo** de `https://www.ciclovia.com.py/` en una tienda propia, mostrando **los mismos precios publicados**, y que los cambios de la página original (precio, stock, altas y bajas) se reflejen automáticamente.
**Fecha:** 21 de octubre de 2026 · **Zona:** America/Asuncion
**Base del análisis:** dos relevamientos independientes del sitio (41 + 67 requests, sin credenciales) + un PoC de extracción. Evidencia en `recon/`, `poc/` e `investigacion/`.

---

## 0. Veredicto

**Sí, es posible.** Técnicamente el catálogo y los precios se pueden mantener sincronizados con un barrido de ~45 requests cada pocas horas (≈70 segundos), sin abusar del sitio y sin APIs pagas.

Lo que hace viable el proyecto:

1. El sitio es **Magento 2** y publica el precio **renderizado en el servidor**, más microdata `schema.org`, meta `og:product:*` y JSON embebido de Magento. No hay que ejecutar JavaScript.
2. La **grilla de categoría ya trae el precio y el SKU de cada variante** (talle/color) dentro de `jsonConfig`: no hace falta abrir las ~3.700 fichas para mantener precios.
3. El sitio **no tiene anti-bot activo**: 108 requests en dos relevamientos → 0 bloqueos, 0 captchas, 0 rate limit observable. El límite real es de cortesía y de `robots.txt`.
4. El catálogo es **finito y acotado**: 4 pilares con 2.698 productos visibles (BICICLETAS 1.302 · FITNESS 1.233 · INDUMENTARIA 141 · AUTOACCESORIOS 22) + 24 subcategorías + 8 categorías ocultas.
5. **Ya está demostrado con código**: el PoC extrajo **2.681 productos únicos** desde **111 páginas de categoría** (5.711 tarjetas, cobertura **100 %** en los 4 pilares: 1.302/1.302, 1.233/1.233, 141/141, 22/22) y **5 fichas completas** (SKU, specs, galería, 11 variantes y 3 vendibles en la ficha de control).

**Las 3 condiciones que definen el éxito (no son técnicas, son comerciales/legales):**

| # | Condición | Por qué es bloqueante |
|---|---|---|
| 1 | **Acuerdo escrito con Ciclovía/Chacomer** que autorice (a) el barrido automático de su catálogo, (b) el uso de fotos y textos, y (c) la venta online a los precios publicados | `robots.txt` prohíbe `/*?` (paginación) y `/catalog/product/view/`; las fotos y descripciones son material de terceros (Ley 4868/2013 art. 16 + derecho de autor). Sin esto, el proyecto funciona técnicamente pero queda expuesto |
| 2 | **Cruce real precio mayorista vs. precio online** por SKU | Ciclovía publica precios con badge “Precio EXCLUSIVO Online” y descuentos de hasta 25–75 %. Si replicás el precio online y tu costo mayorista es mayor, **vendés a pérdida**. El sistema debe detectarlo y frenar el producto |
| 3 | **Definir el identificador de la lista mayorista**: SKU padre (`410116726`) o SKU hijo (`4101167M26B`)** | En los productos configurables el SKU visible no coincide con ningún SKU hijo. Sin este mapeo no hay control de margen ni control de stock |

Si esas 3 condiciones no se pueden cerrar, la alternativa es una **vitrina sin precios** (botón “consultar por WhatsApp”), que sí es posible sin autorización expresa pero pierde el objetivo principal.

---

## 1. Qué se verificó (evidencia, no supuestos)

| Dato | Resultado | Fuente |
|---|---|---|
| Plataforma | Magento 2, tema `Chacomer/ciclovia`, ElasticSuite, Fastly + Varnish, PIM externo para imágenes | `recon/ANALISIS_TECNICO.md` §1 |
| API oficial | `/graphql` → **403**, `/rest/V1` → **401**. No hay API pública | ídem §1, §11 |
| Paginación | `?p=N`; `?product_list_limit=36/48/64` (200 se cae a 36). Total real en `.toolbar-amount` (“1302 Resultados”), los links de `.pages` son una ventana ±2 | ídem §2 |
| Catálogo por pilar | BICICLETAS 1.302 (21 pág. a 64) · FITNESS 1.233 (20) · INDUMENTARIA 141 (3) · AUTOACCESORIOS 22 (1) | ídem §7 |
| Sitemap | 3.922 URLs: 3.810 fichas (3.747 SEO + 63 sin SEO, estas prohibidas por robots), 31 categorías, 71 CMS. `lastmod` se actualiza **en bloque** (2.216 URLs el mismo día) → inservible para precios; su `ETag` sí sirve para detectar altas/bajas | ídem §6 |
| Precio en la grilla | `data-price-amount` + `oldPrice`/`finalPrice` + `jsonConfig.optionPrices` por variante | ídem §2.5, §3.4 |
| Precio en la ficha | 3 fuentes: microdata `itemprop="price"`, `meta property="product:price:amount"`, `data-price-type="finalPrice"` | ídem §4 |
| Stock | `og:availability` (`in stock`/`out of stock`) + `.stock.unavailable` (“Sin stock”). **No hay cantidades**; `stockItems.qty` es un valor por defecto y no sirve | ídem §3.2, §4.3 |
| Variantes | Modelo configurable con N hijos (ej. 11 hijos, 3 vendibles), precio distinto por talle/color; además 218 URLs legacy con talle/SKU en el slug | ídem §3.3 |
| Estado “catalog-only” | (a) con precio, (b) sin precio con CTA **“Ver Distribuidor”** / **“Adquiéralo en un distribuidor autorizado”**, (c) agotado. Validado: **1.316 con precio · 1.035 agotados (950 conservan precio) · 298 solo-catálogo · 32 sin dato** | ídem §2.5 + `poc/REPORTE.md` §5 |
| Caché | HTML con `Cache-Control: no-store` y **sin ETag**; una lectura puede venir con `Age` de minutos | ídem §5.1 |
| Anti-bot | 41 requests en el recon + 67 del PoC: 0×403, 0×429, sin captcha. Límite = cortesía | ídem §5.3 |
| `robots.txt` | `Disallow: /*?` → **toda URL con query** (paginación, filtros) queda fuera. `Allow: /media/catalog/product/` | ídem §8 |
| Marco legal/comercial PY | Ley 4868/2013 (info obligatoria, PI, retracto, sanciones), uPay 2–2,9 %, Bancard vPOS Gs 74.900, AEX logística, SIFEN | `investigacion/TIENDA_Y_COMERCIO.md` |
| PoC | 150 requests (plan estable: 117) → **2.681 productos únicos**, 5.711 tarjetas, **100 % de cobertura en los 4 pilares**, 100 % con imagen, 84,5 % con precio (el resto son solo-catálogo/agotados sin precio), 0 duplicados, precios enteros PYG validados, 5/5 fichas | `poc/REPORTE.md` |

**Cobertura real (dato honesto):** las grillas cubren 2.611 de las 3.747 fichas del sitemap (**69,7 %**). Las **1.136 restantes** no aparecen en ninguna grilla: son fichas de las 2 categorías ocultas (hidratación 842, transporte 849) y URLs despublicadas que el sitemap todavía arrastra. Llegar al 100 % del sitemap requiere bajar las fichas individuales (ruta 100 % robots-compliant, ~75 min) o autorización para paginar.

---

## 2. Qué se puede sincronizar y qué no

| Campo | ¿Sincronizable? | Fuente | Confiabilidad | Nota |
|---|---|---|---|---|
| Precio final (online) | ✅ Sí | grilla + ficha | Alta | Es el precio con descuento; incluye IVA 10 % |
| Precio de lista (tachado) | ✅ Sí | `oldPrice` | Alta | Sirve para mostrar “antes / ahora” |
| Descuento % | ✅ Sí, derivado | `1 − final/lista` | Alta | Y también el badge “HASTA x% OFF” |
| Nombre del producto | ✅ Sí | grilla/ficha | Alta | Texto factual, sin problema de derechos |
| Marca | ✅ Sí | `.product-item-brand` / `og:product:brand` | Alta | SCOTT, CANNONDALE, BEST, BRAVO, etc. |
| Categoría / subcategoría | ✅ Sí | grilla + `content_category` | Alta | Los 4 pilares + 25 subcategorías |
| SKU padre | ✅ Sí | `itemprop="sku"` | Alta | Formato `410116726` |
| SKU hijo (variante) | ✅ Sí | `jsonConfig.sku` | Alta | Mapear contra la lista mayorista (condición 3) |
| Atributos de variante | ✅ Sí | `jsonConfig.attributes` + `index` | Alta | Talle, color, aro… |
| Precio por variante | ✅ Sí | `jsonConfig.optionPrices` | Alta | Distinto por talle (ej. 3.811.800 vs 4.320.040) |
| Disponibilidad (sí/no) | ✅ Sí, binaria | `og:availability` | Alta | **No hay cantidades** |
| Vendibilidad por variante | ⚠️ Derivada | `jsonConfig.salable` | Media | Sirve para “qué combinación se puede comprar”, no para unidades |
| Imágenes | ✅ Técnicamente | `media/catalog/product/...` | Alta | **Requiere permiso** de uso; hay que rehospedarlas (2–6 GB) |
| Descripción | ⚠️ Pobre | `[itemprop="description"]` | Media | Texto corto autogenerado (“Detalles BICICLETA …”), poco útil |
| Especificaciones | ✅ Sí | tabla de 5–13 pares | Alta | Marca, aro, materiales, frenos, cambios… |
| “Solo catálogo” (sin precio en el listado) | ✅ Se detecta | `Ver Distribuidor` / `.onlycatalog-message` | Alta | **298 productos (11,1 %)**: la ficha **sí puede exponer precio y stock** aunque el listado lo oculte; es una decisión de política (§6.1.8), no un dato faltante |
| Stock exacto (unidades) | ❌ No | — | — | Solo existe “En stock / Sin stock” |
| Productos dados de baja | ✅ Sí | sitemap ETag + ausencia en grilla | Media | Requiere 2 lecturas para evitar falsos positivos |
| Costo mayorista | ❌ No está en la web | lista propia (Excel/ERP) | — | Se carga y cruza en tu base, nunca se publica |

---

## 3. Arquitectura propuesta

```
                    ┌────────────────────────── TU INFRAESTRUCTURA ──────────────────────────┐
                    │                                                                        │
  ciclovia.com.py   │  1. COLECTOR            2. NORMALIZADOR       3. DIFUSOR               │
  ───────────────   │  (Python, cron)         (SQLite/Postgres)     (aplica cambios)         │
  sitemap.xml ──────►  ETag → altas/bajas    productos, variantes    WooCommerce REST API    │
  grillas (45 req) ─►  precios, stock,    ─► precios, stock,      ─► o JSON estático         │
  fichas (a demanda)►  variantes, flags      margen, hash            + invalidación de caché  │
                    │        │                     │                        │                 │
                    │        ▼                     ▼                        ▼                 │
                    │  caché HTML 7 días     4. GUARDRAIL           5. TIENDA               │
                    │  (reproceso sin red)   margen mínimo,         catálogo + ficha        │
                    │                        pausa por anomalía    carrito / WhatsApp      │
                    │                              │                        │                 │
                    │                              ▼                        ▼                 │
                    │                        6. MONITOREO  ────────►  7. PEDIDO               │
                    │                        alertas + KPIs            WhatsApp / checkout    │
                    └────────────────────────────────────────────────────────────────────────┘
```

**Por qué esta forma y no un scraper suelto:**

- **Caché de HTML en disco** (7 días): si cambian el tema y el parser falla, se reprocesa sin volver a golpear el sitio. También permite auditar por qué un precio cambió.
- **Hash por campo**: solo se aplica lo que cambió. Sin esto, 2.698 productos × 6 corridas/día = ruido y riesgo de pisar ediciones manuales.
- **Guardrail de margen separado del publicador**: el publicador solo sabe de precios; el guardrail decide si ese precio se puede publicar. Así una promo agresiva de Ciclovía no te funde el margen en silencio.
- **Doble lectura ante saltos grandes** (>5 %): el HTML puede venir de caché intermedia con minutos de antigüedad; dos lecturas coincidentes evitan publicar un precio fantasma.

---

## 4. Ciclo de sincronización (costo real en requests)

| Paso | Frecuencia | Requests | Qué hace |
|---|---:|---:|---|
| **A. Inventario** | 1×/día (madrugada) | 1 | `GET /sitemap.xml` con `If-None-Match`. `304` → nada cambió en el universo de URLs. `200` → diff de `<loc>`, encola altas/bajas |
| **B. Precios + stock + variantes** | cada 4–6 h | **45** | 4 pilares con `?product_list_limit=64` (21+20+3+1). De cada tarjeta: `product_id`, nombre, marca, URL, precio final/anterior, badge, estado y, si es configurable, `optionPrices` + `sku` + `salable` por hijo |
| **C. Categorización + ofertas** | 1×/semana | **66** | 25 subcategorías + 6 páginas de cyberday: asigna la ruta de categoría a cada producto y detecta la colección de ofertas |
| **D. Detalle bajo demanda** | solo cambios | N | Ficha SEO de productos nuevos o con cambio estructural: specs, galería, descripción, `content_category` |
| **E. Categorías ocultas** | 1×/semana | 9 | Hidratación, transporte, trineo, ski, bancos, pilates, máquinas de gimnasio, 506 (si se venden) |
| **F. Repaso sitemap-only** | 1×/semana | ≤1.136 | Fichas del sitemap que no aparecen en las grillas (despublicadas o de categorías ocultas): validar y dar de baja |

**Costo total:** bootstrap ≈ **117 requests** (1 robots + 111 grillas + 5 fichas) ≈ 3 minutos. Mantenimiento normal: **46–47 requests/día** para precios (≈70 s) + 75 requests una vez por semana para categorización. La pasada completa de las 3.747 fichas del sitemap **nunca es necesaria**; si se hace, es 1×/mes de noche (~75 min a 1,2 s/req) y es la ruta 100 % robots-compliant.

**Reglas de cortesía (no negociables):**
- User-Agent identificable con contacto (`BiciTiendaSync/1.0 (+https://tutienda.com.py; contacto@…)`).
- 1 request cada 1–1,5 s, sin concurrencia; backoff exponencial ante 429/503 (`Retry-After`).
- Nada de `/checkout/`, `/customer/`, `/catalog/product/view/`, `/js/`, `/lib/`.
- **La paginación (`?p=`, `?product_list_limit=`) está prohibida por `robots.txt`.** Sin autorización escrita, el plan B es la vía 100 % compliant: sitemap + fichas SEO individuales (3.747 requests/pasada, ~1,5 h de madrugada). Es 80× más caro en requests y más frágil; por eso la autorización es la condición #1.

---

## 5. Modelo de datos (mínimo)

```sql
-- canónico, independiente de la tienda destino
producto (
  product_id        TEXT PRIMARY KEY,   -- ID Magento (dedupe; no hay canonical en el sitio)
  sku_padre         TEXT,
  url_ciclovia      TEXT,
  nombre            TEXT,
  marca             TEXT,
  categoria_path    TEXT,               -- "BICICLETAS,MTB"
  tipo              TEXT,               -- simple | configurable
  precio_lista      INTEGER,            -- oldPrice, PYG entero
  precio_online     INTEGER,            -- finalPrice
  descuento_pct     REAL,
  estado            TEXT,               -- ok | solo_catalogo | agotado
  badge             TEXT,               -- "PRECIO_Exclusivo_Online", "HASTA 25% OFF"
  specs_json        TEXT,
  primera_vez       TEXT,
  ultima_vez        TEXT,
  hash_campos       TEXT               -- detecta cambios reales
);

variante (
  child_id TEXT PRIMARY KEY,
  product_id TEXT REFERENCES producto,
  sku_hijo TEXT,
  opciones_json TEXT,                  -- {"tama_o_bicicletas":"LARGE","color_bicicletas":"NEGRO"}
  precio_online INTEGER,
  precio_lista INTEGER,
  vendible INTEGER                     -- derivado de jsonConfig.salable
);

precio_historico (product_id, variante_id, precio, leido_en, age_segundos, request_id);
costo_mayorista  (sku, costo_neto, actualizado_en);        -- tu lista
cambio           (id, tipo, entidad, antes_json, despues_json, estado, aplicado_en);
corrida          (id, inicio, fin, requests, errores, cobertura_pct, estado);
```

**Claves de mapeo:** `product_id` (Magento) ↔ `sku_padre` ↔ `url_ciclovia` ↔ `sku_hijo` (variantes) ↔ `external_id` (tu tienda). Se guardan **los dos SKU** (padre e hijo) para poder cruzar con la lista mayorista sin adivinar.

---

## 6. Reglas de negocio (el corazón del sistema)

### 6.1 Precio — “mantener el precio de la página original”

1. **Se publica `precio_online` (finalPrice) tal cual**, sin redondeo y sin sumarle IVA: en Paraguay el precio que se muestra ya incluye el 10 %.
2. Se muestra `precio_lista` tachado y el % de descuento **solo si existe** (`oldPrice > finalPrice`), replicando la lógica del sitio.
3. **Nunca** se copia el texto “Precio EXCLUSIVO Online” ni las cuotas: son condiciones del canal de Ciclovía, no de tu tienda. Copiar el precio sí; copiar la promoción, no.
4. **Regla de margen (guardrail):** `margen = 1 − costo_neto / precio_online`. Si `margen < mínimo` (sugerido 12 %, porque hay que cubrir 2–3 % de pasarela + envío + devoluciones + publicidad):
   - `margen < 0` → **no publicar / pasar a borrador** y alertar (producto a pérdida).
   - `0 ≤ margen < mínimo` → publicar pero marcado en el reporte semanal de “productos flojos”.
   - Sin costo cargado → publicar y marcar “sin dato de costo”.
5. **Histéresis:** un cambio de precio >5 % se aplica solo si dos lecturas con ≥5 min de diferencia coinciden. Evita publicar un precio corrupto o de caché.
6. **Precios por variante:** si el producto es configurable, el precio vive en la variante. El “desde” del listado es el mínimo; si tu tienda no soporta variantes, no publiques esos productos (mostrarías un precio falso).
7. **Redondeo:** no redondear (el objetivo es espejo exacto). Si querés un precio “psicológico”, es una decisión aparte que rompe el espejo y hay que aprobar explícitamente.
8. **Los “catalog-only”** (`Ver Distribuidor` / “Adquiéralo en un distribuidor autorizado”) son **298 productos (11,1 %)** sin precio en el listado, más 32 sin dato y 85 agotados sin precio: en total **415 productos (15,5 %) sin precio**. Son justamente los que Ciclovía **no vende online**: para el revendedor son la mejor oportunidad. Opciones: (a) mostrarlos como “precio a consultar”, (b) leer el precio de la ficha (existe, validado en `abdominalera-athletic-700ab.html`: PYG 1.009.800 → 584.600), o (c) publicarlos con **tu propio precio** calculado sobre el costo mayorista + margen. Recomendado: (c) para estos y (a) mientras no tengas costo cargado.
9. **Descuentos absurdos:** el espejo hereda errores del origen (ej. un buzo de PYG 490.800 a PYG 40.000, −92 %). El guardrail debe marcar descuentos >80 % para revisión manual antes de publicar: o es una liquidación real, o un error de precio que te haría vender a pérdida.

### 6.2 Stock

- Estados: `ok` → “En stock”; `agotado` → “Sin stock” + botón “avisarme”/“consultar”; `solo_catalogo` → “Precio a consultar” (o no publicar).
- **No hay cantidades.** Política sugerida: si vendés con stock propio, el stock de tu depósito manda y el de Ciclovía solo indica reposición. Si hacés dropshipping, el estado de Ciclovía manda pero se muestra “consultar disponibilidad” en productos de rotación lenta.
- Producto que desaparece: **no se borra**, se pasa a borrador tras 2 pasadas sin verlo (protege SEO, links y pedidos en curso).

### 6.3 Variantes

- Una bici SCOTT = 1 URL, N hijos con precio propio (ej. 11 hijos, 3 vendibles). Publicar como producto variable con atributos Talle y Color, y SKU = SKU hijo.
- Los 218 productos legacy “variante-como-producto” (slug con talle/SKU) se **fusionan** en el producto padre cuando se detecte que comparten modelo, o se publican aparte si no hay forma de vincularlos (para no duplicar fichas).
- Variante no vendible (`salable`) → no publicar o marcar agotada, según política.

### 6.4 Catálogo publicado

- Los **4 pilares + 25 subcategorías** (todas las páginas que pediste), más las 8 categorías ocultas si entran en tu rubro.
- **Filtrar el vertical**: el sitemap mezcla repuestos de moto/auto del grupo Chacomer; se excluyen por `content_category`/spec “Tipo de Producto” salvo que quieras venderlos.
- `promociones.html` y `cyberday.html` son landings (0 productos): se replican como página de ofertas propia usando la faceta `?descuento=` o `product_list_order=descuento`, no como categoría.

---

## 7. La tienda: dos caminos

> **Decisión tomada (21/10/2026): camino A.** El cliente no quiere cobros online ni cuentas de cliente: la tienda
> es catálogo + canasta y el pedido se cierra por WhatsApp con total, datos y ubicación. Ya está implementado en
> `tienda/` (ver §14). El camino B queda documentado por si más adelante quiere cobrar online.

| | **A. Vitrina + WhatsApp** (elegido e implementado) | **B. WooCommerce completo** (para más adelante) |
|---|---|---|
| Qué es | Catálogo navegable + ficha + carrito que arma el mensaje de WhatsApp (o link de pago TPago) | Tienda con carrito, checkout, cuentas, cupones, facturación |
| Tiempo de implementación | 5–8 días | 8–12 días (encima de A) |
| Costo mensual | Hosting USD 8–15 + dominio | Ídem + pasarela (uPay 0–45.000 Gs/mes + 2–3 %; Bancard vPOS Gs 74.900) |
| Ventaja | Se lanza en semanas, cero fricción de pago, el pedido se cierra por WhatsApp (como ya venden los revendedores en PY) | Cobro automático, escalable, integrable con AEX y SIFEN |
| Desventaja | Conciliación manual, no escala a volumen alto | Más mantenimiento (seguridad, backups, actualizaciones) |
| Cuándo | Primeros 1–3 meses / validación de demanda | Cuando hay >10–15 pedidos/semana o publicidad paga |

**Recomendación concreta:** hacer **A primero** con el sincronizador ya funcionando, y **B encima** cuando el negocio lo pida. La inversión difícil (el pipeline de sync) es común a los dos: la tienda es solo la capa que muestra el resultado.

Stack sugerido para A: Python (colector) + SQLite + Astro/Next estático o WordPress con tema liviano. Para B: **WooCommerce** (plugin propio que lee el JSON del sincronizador y aplica por REST API) — la investigación descartó Tiendanube/Empretienda/Bsale/Mercado Shops para operar desde Paraguay y ubicó a Shopify como opción cara por el recargo del 2 % de pasarela externa.

**Imágenes:** descargar y rehospedar **solo con autorización**, en WebP 1000 px (~120 KB c/u). 3.700 fichas × ~2 imágenes ≈ 7.600 archivos ≈ 1 GB. Hotlinkear el CDN de Ciclovía es legal y técnicamente frágil (y no permite cache propio).

**SEO:** vas a competir con la marca por las mismas fichas. No gana el que copia mejor: gana el que agrega intención local (“envío en Asunción”, “cuotas”, “retiro en local”, “stock inmediato”), contenido propio (guías de talle, comparativas) y velocidad. No copies las descripciones textualmente; no apuntes canonical a Ciclovía.

---

## 8. Plan por fases

### Fase 0 — Validación y acuerdos (3–5 días, sin desarrollo)

| # | Entregable | Criterio de aceptación |
|---|---|---|
| 0.1 | Acuerdo escrito con Ciclovía/Chacomer: autorización de barrido, uso de imágenes/textos, política de precios online, garantía y devoluciones | Documento firmado o correo con respuesta explícita |
| 0.2 | Lista mayorista en CSV/Excel con **SKU (padre o hijo), costo neto, IVA, plazo de pago** | Archivo cruzable por SKU contra el catálogo extraído |
| 0.3 | Definición de fulfillment: stock propio vs dropshipping, quién factura, quién entrega, quién atiende garantía | Una página de proceso |
| 0.4 | RUC, cuenta bancaria y alta de cobro (uPay plan Base o Bancard TPago) | Cuenta operativa de prueba |
| 0.5 | Decisión A (vitrina) o B (WooCommerce) | Aprobación tuya |

### Fase 1 — Pipeline de sincronización (5–7 días)

| # | Entregable | Criterio de aceptación |
|---|---|---|
| 1.1 | `colector.py`: sitemap + 111 grillas + fichas a demanda, con caché, delay, backoff y UA identificable | **2.698 tarjetas (100 % de los 4 pilares), 2.681 productos únicos**, 0 bloqueos |
| 1.2 | Base SQLite + snapshots + hash por campo | Corrida idempotente: misma entrada → 0 cambios |
| 1.3 | `diff.py`: genera cambios (precio, stock, alta, baja, variante) | Reporte legible + exit code para cron |
| 1.4 | Guardrail de margen contra csv mayorista | Producto a pérdida detectado y bloqueado |
| 1.5 | Alertas (Telegram/email) + log de corridas + cobertura % | Alerta real recibida en el celular |
| 1.6 | Tests de contrato con 5 productos canario (uno por rubro) | Falla el test si un selector deja de traer precio (>95 % cobertura) |

### Fase 2 — Tienda A: vitrina (5–8 días)

| # | Entregable | Criterio de aceptación |
|---|---|---|
| 2.1 | Home + 4 pilares + 25 subcategorías + buscador | Navegable en celular |
| 2.2 | Ficha con variantes, imágenes, specs, precio y “consultar por WhatsApp” | Mensaje prellenado con producto/SKU/precio |
| 2.3 | Publicación automática del catálogo desde el JSON del sincronizador | Precio cambiado en origen se ve en ≤6 h |
| 2.4 | Páginas legales (Ley 4868: info, devoluciones, retracto, garantía, contacto) | Checklist legal aprobado |
| 2.5 | Deploy + dominio + HTTPS + analítica | URL pública funcionando |

### Fase 3 — Tienda B: WooCommerce (8–12 días, opcional)

| # | Entregable | Criterio de aceptación |
|---|---|---|
| 3.1 | Productos variables + variaciones + categorías + atributos | 100 % de las fichas publicadas correctamente |
| 3.2 | Aplicador por REST API: altas, precios, stock, imágenes, borradores | `--dry-run` sin diferencias y luego apply real |
| 3.3 | Checkout uPay/Bancard + envío AEX (cotizador) + retiro | Pedido de prueba de punta a punta |
| 3.4 | Facturación (SIFEN / e-kuatia’i) y correos transaccionales | Factura emitida en la prueba |
| 3.5 | Backups, staging y plan de actualizaciones | Restauración probada |

### Fase 4 — Operación continua

- Revisión semanal del reporte de márgenes y de productos flojos.
- Reconciliación mensual contra la lista mayorista (precios que cambiaron de forma).
- Revisión de cobertura: si cae <95 %, hay cambio de tema → activar modo “caché + reproceso” y ajustar parser.

---

## 9. Costos estimados

| Rubro | Estimado | Nota |
|---|---|---|
| Dominio `.com.py` | a cotizar (NIC.py) | Anual |
| Hosting | USD 8–15/mes | 3.700 SKU + imágenes: mejor VPS chico o hosting con CDN |
| uPay | Gs 0 (Base) / Gs 45.000 (Pro, con RUC) + 2–3 % por venta | Verificado en `upay.com.py` |
| Bancard vPOS / TPago | Gs 74.900 / Gs 22.900 IVA incl. | Alta de la pasarela (confirmar si es única o mensual) |
| AEX | a cotizar (no publica tarifas) | Pago en destino o cuenta corriente |
| Imágenes (storage/CDN) | USD 0–5/mes | ~1 GB optimizado |
| Facturación electrónica | E-kuatia’i gratuito (1 punto) | SIFEN |
| **Desarrollo** | **25–35 días-persona** (vitrina) / **35–50** (WooCommerce completo) | El pipeline es el 40 % del esfuerzo |

No incluyo mano de obra en USD porque depende de quién lo haga (vos, un freelance local o una agencia): **es la variable a cotizar**, no un costo fijo del proyecto. La parte técnica no requiere licencias pagas.

---

## 10. Operación, monitoreo y KPIs

**Alertas (a tu WhatsApp/Telegram):**

| Alerta | Disparador | Acción |
|---|---|---|
| Corrida fallida | 2 corridas seguidas sin datos | Revisar conectividad/robots |
| Cobertura baja | <95 % de productos con precio | Posible cambio de tema → modo reproceso |
| Anomalía de precios | >10 % del catálogo cambió en una pasada | **Pausar publicación**, revisar (¿promo real o parseo roto?) |
| Bloqueo | 403/429/503 | Backoff + aviso; no reintentar en loop |
| Margen negativo | precio online < costo | Producto a borrador + aviso |
| Alta/baja | producto nuevo o desaparecido | Revisión rápida |

**KPIs:** cobertura de precios (≥99 %), latencia de sincronización (≤6 h), % de cambios aplicados sin error (≥99,5 %), productos con margen bajo (<X %) por semana, pedidos con quiebre de stock (objetivo 0).

**Runbook (1 página):** si el sitio cambia → revisar `poc/`/`recon/` para localizar el selector, corregir, correr tests de contrato con las 5 fichas canario, reprocesar desde caché. Nunca “arreglar en caliente” contra el sitio en producción.

---

## 11. Riesgos principales

| Riesgo | Impacto | Mitigación |
|---|---|---|
| Cambio de tema/ElasticSuite rompe selectores | Alto | Parsear microdata/meta/JSON primero; tests canario; alerta de cobertura |
| `robots.txt` prohíbe el barrido por paginación | Legal | Autorización escrita (Fase 0); sin ella, vía sitemap+fichas |
| Fotos/textos sin permiso | Legal | Autorización + rehospedaje propio; no copiar descripciones |
| SKU padre vs hijo | Alto | Definir con Ciclovía; guardar ambos; validar 20 productos a mano |
| Promos de Ciclovía dejan precio bajo costo | Alto | Guardrail de margen con bloqueo automático |
| Sin cantidades de stock | Medio | Mostrar “consultar” en rotación lenta; stock propio como fuente real |
| Mismo precio = competir contra la marca | Comercial | Diferenciar por servicio, entrega local, cuotas propias, packs, asesoramiento |
| Canibalización SEO / fichas duplicadas | Medio | Contenido propio, intención local, sin copiar meta descripciones |
| Precio leído de caché intermedia | Medio | Doble lectura en saltos >5 %, registrar `Age` |
| Catálogo mezclado con moto/auto | Medio | Filtro de vertical por categoría/specs |
| Garantía: el responsable ante el consumidor sos vos | Alto | Acuerdo de garantía por escrito con Chacomer antes de vender |

---

## 12. Primeras dos semanas (checklist)

**Semana 1**
- [ ] Hablar con Ciclovía/Chacomer: autorización de catálogo, imágenes, precios online, garantía. Pedir **feed/CSV mayorista** (si existe, reemplaza media Fase 1).
- [ ] Confirmar SKU padre/hijo de la lista mayorista.
- [ ] Correr el PoC (`poc/`) contra el catálogo completo y validar 20 precios a mano en el sitio.
- [ ] Decidir A o B y el nombre/dominio.

**Semana 2**
- [ ] Cerrar lista mayorista y cargarla en la base.
- [ ] Poner el colector en cron cada 6 h con alertas.
- [ ] Publicar la vitrina con las 4 categorías y las 25 subcategorías.
- [ ] Probar el flujo: cambio de precio simulado → se refleja → pedido de prueba por WhatsApp.

---

## 13. Decisiones que necesito de vos

1. **¿Ya tenés tienda online, RUC y cuenta para cobrar?** (define A vs B y el orden)
2. **¿Tenés la lista mayorista en Excel/CSV? ¿Usa SKU padre o SKU hijo?**
3. **¿Ciclovía te autoriza por escrito** (a) a leer el catálogo automáticamente, (b) a usar sus fotos y textos, (c) a vender online a esos precios?
4. **¿Entregás con stock propio o dropshipping?** ¿Quién factura y quién da garantía?
5. **¿Publicamos los 3.700 productos o solo el vertical ciclismo/fitness** (excluyendo repuestos de moto/auto)?
6. **¿Qué pasa cuando el precio online de Ciclovía queda por debajo de tu costo?** (¿ocultar, consultar, vender igual?)

---

## 14. Alcance ajustado (v2) — tienda implementada

El pedido real del cliente quedó acotado: **solo la página**, con canasta que llega a su WhatsApp (+595 993 539 237)
con total y ubicación para la entrega. Sin pasarela de pago, sin cuentas de cliente, sin precios mayoristas publicados.
Eso convierte el proyecto en **una tienda estática** y saca del alcance las fases 3 (WooCommerce, pagos, facturación
en la web) y la mitad de la fase 0 (alta de cobros). Se implementó en `tienda/`.

**Qué quedó hecho**

| Pieza | Estado |
|---|---|
| Catálogo de 2.681 productos (precio, precio anterior, descuento, stock, marca, imagen) | ✅ |
| 4 pilares + 24 subcategorías + vista Ofertas, buscador, orden y filtro “solo disponibles” | ✅ |
| Ficha de producto con precio, descuento, estado, SKU, categoría y link a la ficha original | ✅ |
| Canasta con cantidades, subtotal, total y persistencia en el navegador | ✅ |
| Checkout: nombre, teléfono, envío/retiro, dirección, referencia, notas y **ubicación GPS** | ✅ |
| Pedido por WhatsApp al número configurado, con detalle, total y datos de entrega | ✅ |
| Fallback “Copiar pedido” y enlace directo si el navegador bloquea la ventana | ✅ |
| Regeneración del catálogo con un comando (`build_catalogo.py`) | ✅ |
| **Actualización automática diaria** (tarea de Windows, 06:00) con logs y reporte de cambios | ✅ |
| **Publicación automática** FTP o git (se activa al crear `publicar.config.ps1`) | ✅ configurable |
| Prueba de punta a punta en navegador real | ✅ 9/9 verificaciones |

**Qué NO tiene (a propósito)**

- Pagos online, cupones, cuentas de cliente, historial de pedidos, facturación automática.
- Precios mayoristas visibles: el sitio muestra el precio publicado; el costo mayorista se usa solo para control de margen.
- Panel de administración: el catálogo se administra editando los JSON que genera el sincronizador.

**Decisiones funcionales**

1. **Precio limpio:** un solo precio por producto con el +15 % ya incluido, sin precio anterior tachado, sin
   % de descuento y sin ningún enlace a la página original.
2. Producto **sin stock** se puede pedir, pero el mensaje lo marca `⚠️ SIN STOCK (confirmar)`.
3. Producto **sin precio online** (“a consultar”) no entra a la canasta: abre WhatsApp para cotizar.
4. El envío **no se cobra en la web**: el total es de productos y el envío se coordina por WhatsApp.
5. La ubicación GPS la comparte el cliente con un botón (requiere HTTPS y su permiso).
6. Las imágenes se muestran desde el CDN de Ciclovía como referencia (producción: rehospedar con autorización).

**Automatización:** la tarea de Windows `BiciTienda - actualizar catalogo` corre **todos los días a las 06:00**
(`--force`, ~120 requests, 2–4 min), regenera el catálogo, guarda log en `tienda/logs/` y reporte de cambios en
`tienda/data/ultimos_cambios.json`. La subida al hosting se activa al crear `tienda/publicar.config.ps1` (FTP o git).
Si la PC estaba apagada, la corrida se recupera al encenderla. Se puede cambiar la hora o pasarla a cada 6 h con
`tienda/programar.ps1`.

**Ajuste comercial posterior (21/10/2026):** por pedido del cliente, los precios de venta se publican con un
**recargo de margen del +15 %** configurable (`tienda/assets/config.js → recargoPct`), aplicado también al precio
anterior para que el descuento siga siendo coherente. Deja de ser un espejo exacto del precio online: la tienda
queda por encima del original, lo que mejora el margen pero expone la diferencia ante quien compare con Ciclovía.
El control de margen automático contra la lista mayorista sigue pendiente (requiere el costo por SKU).

**Pendiente antes de salir a la calle:** dominio propio, HTTPS, autorización de Ciclovía para el catálogo y las
imágenes, y definir política de stock (si vende con stock propio o a pedido).

---

## Anexo A — Dónde está la evidencia

| Archivo | Contenido |
|---|---|
| `recon/ANALISIS_TECNICO.md` | 710 líneas: paginación, fichas, variantes, caché, sitemap, cobertura por categoría, 43 campos con selector y confiabilidad, 16 riesgos, presupuesto de requests |
| `investigacion/TIENDA_Y_COMERCIO.md` | Plataformas PY, pagos verificados, logística, SIFEN/IVA, Ley 4868, garantía, unit economics |
| `poc/` | Scraper funcional + datos extraídos + reporte de cobertura |
| `tienda/` | **La tienda implementada**: catálogo, canasta y checkout por WhatsApp, con capturas en `preview-*.png` |

## Anexo B — URLs y parámetros clave

```
Catálogo:        https://www.ciclovia.com.py/bicicletas.html      (y fitness, indumentaria, autoaccesorios)
Paginado:        ?p=N                                             (prohibido por robots: requiere autorización)
Tamaño página:   ?product_list_limit=64                            (válidos 36/48/64)
Orden:           ?product_list_order=position|name|price|updated_at|descuento
Filtros:         ?brand=, ?color_bicicletas=, ?tama_o_bicicletas=, ?aro=, ?descuento=, ?price=
Ficha SEO:       https://www.ciclovia.com.py/<slug>.html
Sitemap:         https://www.ciclovia.com.py/sitemap.xml            (ETag diario; 3.810 fichas)
Imágenes:        https://www.ciclovia.com.py/media/catalog/product/... (permitido por robots)
```
