# Tienda online, pagos, envíos y marco legal — Paraguay 2026

**Investigación para:** revendedor con precio mayorista de CICLOVIA (Chacomer S.A.E., Paraguay)
**Objetivo:** vender en tienda propia los ~3.700 SKU del catálogo Ciclovía, mostrando los **mismos precios publicados** y manteniéndolos sincronizados.
**Fecha:** 21 de octubre de 2026 · **Zona horaria:** America/Asuncion
**Alcance:** plataformas, medios de pago, logística, obligaciones fiscales, marco legal del revendedor, garantía, modelo "vitrina + WhatsApp" vs "carrito con pago online".

> **Convención de precios:** no se convierte a un tipo de cambio fijo. Verificá la cotización del día en el [BCP](https://www.bcp.gov.py/). Cuando un costo no pudo verificarse en fuente pública se marca **"a cotizar"** en lugar de estimarlo.

---

## 0. Resumen ejecutivo (lo que importa)

1. **La plataforma recomendada es WooCommerce sobre hosting propio**, con la sincronización de catálogo resuelta a medida. Es la única opción que combina: 3.700 SKU sin límites, cero comisión por venta de la plataforma, control total del checkout y libertad para integrar Bancard/uPay, AEX y facturación electrónica. **PrestaShop** es la alternativa válida con el mismo perfil técnico. **Shopify** es la opción "menos mantenimiento", pero cuesta más por dos vías (suscripción + 2% adicional por usar pasarelas externas).
2. **Descartadas para operar desde Paraguay:** *Tiendanube* (no opera en PY: su sitio solo lista Argentina, Brasil, México, Colombia y Chile), *Empretienda* (operación y precios en ARS, foco Argentina), *Bsale* (tiene sitios en Chile, Perú, México y Colombia; **no** hay dominio ni operación paraguaya), *Mercado Shops* (`mercadoshops.com.py` redirige a `mercadolibre.com`, no existe como tienda propia en PY).
3. **Mercado Libre Paraguay sirve como canal complementario, no como tienda propia.** Ahí no controlás el precio final (cupones, envío, reputación) ni podés garantizar "mismo precio que Ciclovía".
4. **Medios de pago verificados:** Bancard vPOS **Gs 74.900 IVA incl.** y Bancard TPago **Gs 22.900 IVA incl.** (links de pago por WhatsApp); uPay (ex Pagopar, de ueno bank) **2% débito/QR, 2,9% crédito, 3% internacional**, con planes de Gs 0 / Gs 45.000 / personalizado.
5. **El punto más delicado no es la plataforma, es el margen.** Vender al mismo precio que Ciclovía deja como ingreso bruto solo el descuento mayorista. Sobre eso hay que pagar comisión de cobro (2–3%), envío, devoluciones y publicidad. **Antes de invertir en la tienda hay que confirmar por escrito el descuento mayorista y si incluye IVA.**
6. **Riesgo legal concreto y poco visible:** si replicás fotos y textos de Ciclovía sin autorización, hay exposición bajo derecho de autor y bajo el art. 16 de la Ley 4868/2013. La autorización de uso de material debe quedar **por escrito**.
7. **Riesgo comercial:** Ciclovía publica precios con badge **"Precio EXCLUSIVO Online"** (ver [ejemplo](https://www.ciclovia.com.py/bicicleta-mtb-scott-contrail-40.html)). Si copiás el precio online pero no el contexto (cuotas, envío, stock), competís en desventaja contra el propio fabricante. Eso se negocia, no se improvisa.
8. **Fase recomendada:** arrancar como **vitrina + checkout por WhatsApp con link de pago** (costo de entrada ≈ Gs 22.900 de TPago), y recién cuando haya volumen activar el **carrito con pago online** (uPay o vPOS sobre WooCommerce).

---

## 1. Plataformas de e-commerce: comparación real para 3.700 SKU con precios que cambian

### 1.1 Tabla comparativa

| Plataforma | Costo verificable | Comisión por venta | Límite de productos | ¿Opera/da soporte en PY? | Veredicto |
|---|---|---|---|---|---|
| **WooCommerce** (WordPress, hosting propio) | Plugin **gratis** ([woocommerce.com/pricing](https://woocommerce.com/pricing/)); hosting local desde **USD 4,15/mes** ([IDEIHOSTING](https://ideihosting.com/py/hosting-compartido/)) — plan recomendado USD 8,81–14,09/mes | 0% (solo la pasarela) | Sin límite práctico | Sí (es software libre, vos lo hosteás) | **Recomendada** |
| **PrestaShop** (open source) | Software **gratis** ([prestashop-project.org](https://www.prestashop-project.org/)); hosting igual al anterior | 0% (solo la pasarela) | Sin límite práctico | Sí (open source) | Alternativa técnica válida |
| **Shopify** | **USD 19/mes** anual o 25/mes mensual (Basic); **49/65** (Grow); **299/399** (Advanced); Plus desde **USD 2.300/mes** ([shopify.com/pricing](https://www.shopify.com/pricing)) | **+2% en Basic y +1% en Grow** por usar pasarelas de pago externas | Sin límite | Sí, pero **sin Shopify Payments** → se paga el recargo por pasarela externa | Buena si no querés mantener infraestructura; la más cara por venta |
| **Tiendli** (plataforma regional con tienda PY) | **₲ 0** (hasta 50 productos, 1% comisión), **₲ 75.000**, **₲ 150.000**, **₲ 225.000**/mes con impuestos ([tiendli.com/py](https://tiendli.com/py)) | 1% solo en plan gratuito | Plan gratuito: 50 productos → insuficiente | Sí, experiencia local en PYG, Bancard/Tigo Money/transferencia | Alternativa "llave en mano" si no hay equipo técnico |
| **Bsale** | Planes **a cotizar** | — | — | **No**: sitios en [Chile](https://www.bsale.cl/), [Perú](https://www.bsale.com.pe/), [México](https://www.bsale.com.mx/), [Colombia](https://www.bsale.co/); no hay dominio `.com.py` | Descartada (es ERP/POS, no e-commerce PY) |
| **Tiendanube** | No aplica | — | — | **No opera en Paraguay** ([lista de países del sitio](https://www.tiendanube.com/): AR, BR, MX, CO, CL) | Descartada |
| **Empretienda** | ARS 10.490 (plan publicado en [empretienda.com](https://empretienda.com/), "sin comisiones") | 0% | — | Operación centrada en Argentina (ARS, libro de quejas AR) | Descartada para operar desde PY |
| **Mercado Libre PY / Mercado Shops** | Comisiones **a cotizar** en la cuenta vendedor | Comisión por categoría + envío | Sin límite | ML PY sí; **Mercado Shops no existe en PY** (`mercadoshops.com.py` → `mercadolibre.com`) | Canal complementario, no tienda propia |

### 1.2 Por qué WooCommerce para este caso puntual

El requisito real del proyecto **no es "una tienda bonita", es un pipeline de sincronización de 3.700 precios**. Eso manda sobre el resto:

- **Precios que cambian seguido:** necesitás un proceso programado (cron) que lea precios/stock de Ciclovía y actualice tu catálogo. En WooCommerce lo resolvés con `WP All Import` + endpoint propio, o con un script PHP que pegue contra la API REST de WooCommerce. Sin límite de SKU ni de frecuencia.
- **Mismo precio publicado:** podés guardar en cada producto el precio de lista y aplicarlo, más un campo interno de "costo mayorista" para calcular margen por SKU. Sin esa separación no vas a detectar los productos que vendés a pérdida.
- **Cero comisión por venta:** con margen mayorista, un 2% extra de plataforma duele. Shopify en Basic suma 2% **además** de la comisión de uPay/Bancard (aprox. 4,9% total en crédito).
- **Integraciones locales:** uPay publica explícitamente "integración simple con API o plugins para WooCommerce, PrestaShop, Shopify y Wix" ([upay.com.py](https://upay.com.py/)); AEX tiene integración documentada con Shopify vía API ([AEX — Shopify](https://www.aex.com.py/web/shopify/configuracion.php)) y API genérica ([AEX API](https://www.aex.com.py/web/documentacion-api.php)), que también se puede consumir desde WooCommerce.

**Contras honestos de WooCommerce:** la responsabilidad técnica es tuya (actualizaciones, backups, seguridad, velocidad). Con 3.700 SKU y muchas imágenes pesadas, el hosting de USD 4–9/mes puede quedar corto: prever **USD 11–15/mes** o un VPS **a cotizar**. Además, **el desarrollo de la sincronización es el costo real del proyecto y no está publicado por nadie: hay que cotizarlo con un desarrollador.**

### 1.3 Por qué Shopify queda segunda

- **A favor:** hosting, CDN, seguridad y panel resueltos; AEX ya tiene guía de integración oficial; no te ocupás de la infraestructura.
- **En contra:** suscripción en USD + **recargo de 2% (Basic) / 1% (Grow) por pasarela externa** porque Shopify Payments no opera en Paraguay; cada app suma (importación masiva, idioma, etc. — **a cotizar**).
- **Cuándo conviene:** si preferís pagar por no mantener nada y tu volumen es bajo. Con volumen alto, el 2% se vuelve más caro que el hosting.

### 1.4 Verificación del catálogo (dato duro)

El sitemap de Ciclovía tiene **3.922 URLs, de las cuales 3.778 terminan en `.html`** (mayoritariamente fichas de producto; incluye además páginas de categoría) — [sitemap.xml](https://www.ciclovia.com.py/sitemap.xml) —, lo que confirma el orden de magnitud de ~3.700 SKU. Detalle técnico relevante: Ciclovía corre sobre **Magento 2** (tema `Chacomer/ciclovia`), muestra disponibilidad ("En stock") y tiene botón **"Cuotas"** en la ficha de producto. El catálogo incluye marcas de terceros (SCOTT, CANNONDALE, BEST) y marcas propias/distribuidas (BRAVO, RUSH, ATHLETIC, ENA, LIFE BALANCE, ENACCION, MAGNUM, DYNAMIC).

**Implicancia:** el sync no es solo "precio". Necesitás también **stock y variantes** (talle/color: la ficha de bici declara atributos `tamaño` y `color` con SKU por combinación). Un sync que ignore variantes te va a generar ventas de productos que no tenés.

---

## 2. Medios de pago en Paraguay

### 2.1 Costos verificados (fuente oficial)

| Proveedor / producto | Costo publicado | Qué incluye | Fuente |
|---|---|---|---|
| **Bancard vPOS** (botón de pago web) | **Gs 74.900 IVA incl.** | Iframe embebido; tarjetas de crédito, débito, Zimple y **cuotas**; PCI DSS y 3D Secure; ventas 24/7 | [bancard.com.py/vpos](https://www.bancard.com.py/vpos) |
| **Bancard TPago** (links de pago) | **Gs 22.900 IVA incl.** | Links de pago por WhatsApp/Instagram/Facebook; débito, crédito **con cuotas**, QR; API | [bancard.com.py/tpago](https://www.bancard.com.py/tpago) |
| **uPay — plan Base** | **Gs 0/mes** | QR Paraguay e internacional y link de pago desde la app ueno; **topes de cobro para cuentas sin RUC** | [upay.com.py](https://upay.com.py/) |
| **uPay — plan Pro** | **Gs 45.000/mes** (bonificado 6 meses, ahorro Gs 270.000) | Solo para negocios **con RUC**; link de pago web, uPOS sin impresora, QR, división de cobros | [upay.com.py](https://upay.com.py/) |
| **uPay — Enterprise** | **a cotizar** (con ueno empresas) | Caja uPOS, QR dinámicos, más terminales | [upay.com.py](https://upay.com.py/) |
| **uPay — comisiones** | **2%** débito · **2%** QR · **2,9%** crédito · **2,9%** prepaga · **3%** crédito/prepaga internacional · **2,9%** QR Pix/Argentina | Acreditación **24 h hábiles** (débito/QR) y **48 h hábiles** (crédito/prepaga/Pix) | [upay.com.py](https://upay.com.py/) (sección Tarifas) |
| **Tigo Money (perfil de negocio)** | **Sin costo publicado** (a cotizar si hay comisión) | Alta desde la app como "perfil de negocio", QR propio, demora ~24 h hábiles | [Ayuda Tigo](https://ayuda.tigo.com.py/hc/centro-de-ayuda/articles/2386174965809711-como-crear-un-perfil-a-mi-negocio) |
| **WEPA / giros en efectivo** | Comisión **a cotizar** | Red de +3.300 puntos: cobranzas, giros nacionales e internacionales, **master agente Western Union** | [wepa.com.py](https://www.wepa.com.py/) |
| **Transferencia bancaria** | **Gs 0 de comisión** (costo: tiempo de conciliación) | Requiere verificación manual del comprobante | Práctica de mercado; ver también [uPay](https://upay.com.py/) |
| **Cuotas** | **A cotizar** (Bancard anuncia cuotas disponibles, pero no publica el costo/descuento que asume el comercio) | vPOS y TPago permiten cobrar en cuotas | [vPOS](https://www.bancard.com.py/vpos), [TPago](https://www.bancard.com.py/tpago) |

> ⚠️ **A confirmar con Bancard:** las páginas publican "Gs 74.900" y "Gs 22.900" sin aclarar si es **alta única, abono mensual o costo de habilitación**. Preguntalo antes de firmar: cambia el cálculo si es mensual.

### 2.2 Contexto del mercado de cobros

- **Bancard** es la procesadora dominante: +100.000 comercios, +100 millones de transacciones mensuales, acepta Visa, Mastercard, Maestro, Amex, Diners, Discover, Cabal, Panal, Credicard y billeteras locales ([bancard.com.py](https://www.bancard.com.py/)). También ofrece **facturación electrónica** como servicio ([bancard.com.py/factura-electronica](https://www.bancard.com.py/factura-electronica)).
- **Pagopar pasó a ser uPay** (ecosistema ueno bank). La marca vieja redirige: [upay.com.py/pagopar/](https://upay.com.py/pagopar/). Si alguien te dice "Pagopar", hoy es uPay.
- **Bocas de cobranza / efectivo:** además de WEPA, Bancard tiene **Infonet Cobranzas** (pago de servicios en bocas) — vía [bancard.com.py](https://www.bancard.com.py/). Para e-commerce, el cobro en efectivo suele entrar por red de bocas de la pasarela: **a cotizar** según proveedor.
- **Referencia regional:** las pasarelas paraguayas publican tarifas poco; uPay es la excepción. Cualquier otro proveedor que no las publique debe cotizarse por escrito.

### 2.3 Requisitos de alta como comercio

Lo que las fuentes oficiales permiten afirmar:

| Requisito | Evidencia |
|---|---|
| **RUC** (o CI para persona física en algunos formularios) | uPay: el plan Pro es "solo para negocios con RUC" y el plan Base tiene "topes de cobro para cuentas sin RUC" ([upay.com.py](https://upay.com.py/)); el formulario de solicitud de vPOS/TPago pide "C.I. / R.U.C." y "R.U.C. de la Empresa" ([vPOS](https://www.bancard.com.py/vpos), [TPago](https://www.bancard.com.py/tpago)) |
| **Datos del negocio y de contacto** | Mismos formularios de solicitud de Bancard |
| **Cuenta bancaria** para acreditar | Acreditaciones de uPay caen en cuenta ueno o en "otros bancos o billeteras" ([upay.com.py](https://upay.com.py/)) — cuenta a nombre del titular del comercio: confirmar con cada proveedor |
| **Facturación electrónica** | Obligación tributaria independiente de la pasarela (ver §4) |

**Camino recomendado de alta (mínimo costo):** RUC → alta en uPay plan Base (Gs 0, sin papeles, alta inmediata) → link de pago/QR para vender. Si necesitás tarjeta con cuotas en la web, sumar Bancard vPOS. Si necesitás que el cobro esté integrado al carrito, uPay Pro o vPOS según el plugin que use tu plataforma.

---

## 3. Logística y envíos

### 3.1 AEX (Asunción Express) — la opción más preparada para e-commerce

Verificado en su sitio:

- **Puerta a puerta a todo el país**, con **pick up sin costo** en domicilio u oficina, **pago en destino**, **seguro sobre valor declarado**, packaging, seguimiento online y **logística inversa** (clave para devoluciones y garantías) — [aex.com.py](https://www.aex.com.py/web/).
- **AEX E-Locker:** lockers inteligentes; plazos AM/PM; integrable a la plataforma web. Útil para bici/accesorios de bajo volumen — [aex.com.py](https://www.aex.com.py/web/).
- **Bumer Delivery Express:** envíos rápidos (entrega urbana) — **a cotizar**, se pide por formulario de contacto ([contacto](https://www.aex.com.py/web/contactenos.php)).
- **Integración técnica:** API de envíos ([documentación ES](https://www.aex.com.py/web/documentacion-api.php)), API de Puntos AEX y **guía oficial de integración con Shopify** ([configuración Shopify](https://www.aex.com.py/web/shopify/configuracion.php)). Para esa integración hay que **ser cliente de AEX con cuenta corriente** y tener plan Shopify activo; permite cotizar en tiempo real o usar reglas de envío.
- **Cotizador público** para calcular costo por origen/destino/peso: [calcular-envios.php](https://www.aex.com.py/web/calcular-envios.php). **Las tarifas no están publicadas como tabla: se obtienen del cotizador o con el ejecutivo comercial.**

> **Costo de envío: a cotizar.** No hay tarifa pública por kg/tramo. Pedí la lista de precios por zona (Asunción, Gran Asunción, interior) y el costo de "pago en destino" vs "cuenta corriente".

### 3.2 Dinacopa (Correo Paraguayo)

Sitio oficial: [correoparaguayo.gov.py](https://www.correoparaguayo.gov.py/).

Servicios disponibles según el sitio: **cotizador de envíos** ("Cotizar Envío"), **seguimiento** nacional e internacional, **Dinacopa Box** ([clubdinacopabox.com.py](https://clubdinacopabox.com.py/)), **Exporta Fácil** y agencias en todo el país.

- **Fortaleza:** cobertura nacional y precio estatal, útil para interior y localidades sin courier privado.
- **Debilidad:** plazos y experiencia de e-commerce menos aceitados que AEX.
- **Costos: a cotizar** mediante el cotizador del sitio.

### 3.3 Mirtrans

No se pudo verificar sitio oficial: `mirtrans.com.py`, `www.mirtrans.com.py` y `mirtrans.com` no resuelven/fueron accesibles en esta investigación (TLS inválido). **Estado: a verificar.** Si te la ofrecen como courier, pedí RUC, cobertura, plazos, seguro, API y condiciones de logística inversa por escrito.

### 3.4 Moto-delivery en Asunción

Alternativa real para entregas same-day en Asunción (bicis, accesorios, cascos). **Precios no publicados por los operadores: a cotizar.** Variables a pedir: tarifa base por zona, costo por km, franja horaria, seguro de la carga y comprobante de entrega.

### 3.5 Retiro en local

La opción más barata y la que más conviene fomentar al inicio: costo logístico ≈ 0, cero riesgo de rotura en tránsito y oportunidad de venta cruzada (casco, luces, cámara). Además, la Ley 4868/2013 exige informar "el modo, plazo, las condiciones y la responsabilidad por la entrega" (art. 7 inc. f), así que conviene publicar retiro y envío como opciones explícitas.

### 3.6 Qué conviene para bicicletas (producto voluminoso)

- Una bici armada **no entra en courier de paquetería estándar**: requiere embalaje tipo caja de fábrica o envío especial. Pedí a AEX la **cotización por "AEX Cargo"** para bultos de gran volumen ([aex-cargo](https://www.aex.com.py/web/servicios/aex-cargo.php)).
- Alternativa comercial: **bici se retira en local o se entrega con flete propio**, y el e-commerce se concentra en accesorios/suplementos/indumentaria (donde el envío es rentable).
- **Publicá el costo de flete en la ficha** (art. 7 inc. j de la Ley 4868/2013 exige informar el costo del flete).

---

## 4. Obligaciones fiscales y facturación electrónica

### 4.1 Impuestos

- **IVA:** en Paraguay el IVA tiene **tasas del 5% y 10%**, es **mensual** y se declara bajo la obligación **211 – IVA GENERAL** ([DNIT — IVA](https://www.dnit.gov.py/web/portal-institucional/iva)). Para bicicletas, repuestos, indumentaria y suplementos la tasa aplicable es **10%**; la mayoría de los precios de góndola en Paraguay se publican **con IVA incluido**.
- **RUC:** la inscripción se hace ante la DNIT ([Inscripción al RUC](https://www.dnit.gov.py/web/portal-institucional/inscripcion-al-ruc)). Guías paso a paso para personas físicas están en el mismo portal.
- **Régimen:** si tu volumen es chico, evaluá **IRE RESIMPLE** ([DNIT — IRE RESIMPLE](https://www.dnit.gov.py/web/portal-institucional/ire-resimple)). La decisión régimen general vs. simple **debe tomarla un contador**: depende de facturación proyectada y de si vas a necesitar crédito fiscal.

### 4.2 Facturación electrónica (SIFEN)

La DNIT implementa el **SIFEN** y ofrece **dos vías** ([DNIT — Factura Electrónica](https://www.dnit.gov.py/web/portal-institucional/factura-electronica)):

| Vía | Para quién | Requisitos |
|---|---|---|
| **E-kuatia'i** | Pequeños facturadores | **Un solo establecimiento y un solo punto de expedición** + **Certificado Cualificado de Firma Electrónica**, que la DNIT otorga **gratis** |
| **E-kuatia** | Medianas y grandes empresas | Desarrollo propio de software conforme a especificaciones técnicas de la DNIT |

Documentación y trámites: [e-Kuatia](https://ekuatia.set.gov.py/web/e-kuatia/), [sección e-Kuatia'i](https://www.dnit.gov.py/web/e-kuatia/ekuatia-i).

**Implicancia para tu tienda:** si vendés desde **un solo local** con un punto de expedición, **E-kuatia'i alcanza y es gratis**. Si tenés depósito + local (dos puntos) o si emitís desde el sistema de la tienda, necesitás **E-kuatia** (integrar un facturador electrónico habilitado o desarrollar). Hay **facturadores electrónicos designados por la DNIT** ([noticia DNIT](https://www.dnit.gov.py/en/web/portal-institucional/w/dnit-designa-nuevos-facturadores-electr%C3%B3nicos)) y Bancard ofrece facturación electrónica como servicio ([bancard.com.py/factura-electronica](https://www.bancard.com.py/factura-electronica)).

### 4.3 Qué pasa si ya tenés RUC de reventa

Es la situación más común y la más conveniente:

1. **Comprás a Ciclovía/Chacomer con factura** → ese IVA es **crédito fiscal**.
2. **Vendés al consumidor final con factura** → ese IVA es **débito fiscal**. Pagás al fisco la diferencia.
3. **Si el precio mayorista ya incluye IVA** y vendés al mismo PVP que Ciclovía, tu margen real es **menor que el descuento nominal**. Pedí siempre: *"¿el precio mayorista incluye o excluye IVA?"*.
4. **Factura al consumidor final:** se emite con **RUC del comprador = "sin nombre"/consumidor final** según el formato del facturador. La Ley 4868/2013 (art. 32–33) exige factura electrónica a quien compre por vía electrónica, con **misma validez contable y tributaria** que la convencional ([Ley 4868/2013](https://www.bacn.gov.py/leyes-paraguayas/961/ley-n-4868-comercio-electronico)).
5. **Ojo con el régimen del proveedor:** si te vende en **régimen de turismo** o como **importador**, los comprobantes y el crédito fiscal pueden cambiar. Validá con tu contador.

---

## 5. Marco legal y comercial del modelo "revendedor"

### 5.1 Normativa aplicable

| Norma | Qué regula | Relevancia para vos |
|---|---|---|
| **Ley 4868/2013 — Comercio Electrónico** | Contratación electrónica, información obligatoria, retracto, factura electrónica, PI | **La norma central de tu tienda** ([texto](https://www.bacn.gov.py/leyes-paraguayas/961/ley-n-4868-comercio-electronico)) |
| **Ley 1334/1998 — Defensa del Consumidor** | Garantía, información, responsabilidad | Base de las obligaciones frente al comprador ([BACN](https://www.bacn.gov.py/leyes-paraguayas/897/ley-n-1334-de-defensa-del-consumidor-y-del-usuario)) |
| **Ley 4956/2013 — Defensa de la Competencia** | Prohíbe prácticas concertadas, abuso de posición dominante y precios predatorios | Marco a considerar si acordás precios con el fabricante ([BACN](https://www.bacn.gov.py/leyes-paraguayas/4775/defensa-de-la-competencia)) |
| **Ley 1294/1998 — Derecho de Autor** | Protección de obras (fotos, textos, catálogos) | Uso de material de Ciclovía ([DINAPI](https://www.dinapi.gov.py/) es la autoridad) |
| **Autoridades:** [SEDECO](https://sedeco.gov.py/) (consumidor) y [DNIT](https://www.dnit.gov.py/) (tributario) | Fiscalización y sanciones | Ver sanciones abajo |

### 5.2 Información obligatoria en tu tienda (Ley 4868/2013, art. 7)

Tu sitio **debe** publicar de forma permanente, fácil, directa y gratuita:

- Denominación social, domicilio, nombre del/los propietarios, **dirección electrónica y teléfonos**.
- **Política de privacidad** y nivel de seguridad de los datos.
- Copia electrónica del contrato y **procedimiento de cancelación** antes de confirmar la compra.
- Características del producto; **modo, plazo, condiciones y responsabilidad de la entrega**.
- **Plazo, extensión y condiciones de la garantía**.
- **Procedimiento de devolución, cambio y reembolso** con plazos.
- **Precio, moneda, medios de pago, valor final, costo del flete** y cualquier otro costo.
- **Legislación de defensa del consumidor aplicable y dirección electrónica de la autoridad de aplicación** (SEDECO).
- Mecanismo para **identificar y corregir errores** antes de la transacción y **confirmación expresa** (el silencio no vale como consentimiento).

**Sanciones:** hasta **1.000 jornales mínimos** por infracciones muy graves, **500** graves y **200** leves (art. 38). La autoridad de aplicación es el **MIC** (art. 41), con SEDECO en la práctica.

### 5.3 Uso de fotos, textos y catálogo del fabricante

Este es **el punto legal más expuesto** del modelo revendedor:

1. **Las fotos y descripciones de Ciclovía son obras protegidas** (derecho de autor y, según el caso, bases de datos) — [DINAPI](https://www.dinapi.gov.py/). Tomarlas sin permiso es uso no autorizado, aunque el producto sea legítimo.
2. **La Ley 4868/2013 (art. 16)** obliga a los proveedores a tener un **mecanismo público de retiro de contenidos** que violen derechos de autor o de propiedad industrial. Un reclamo del fabricante puede hacer bajar tu catálogo.
3. **Además** puede haber condiciones contractuales en tu acuerdo de reventa (que hoy, por lo que sabemos, es verbal/comercial).
4. **Qué hacer:** pedir a Ciclovía/Chacomer **autorización escrita** para usar imágenes, fichas técnicas, logos y marcas en tu tienda, con alcance (web, redes, Mercado Libre, publicidad paga) y plazo. Si te la niegan, usá **fotos propias** o material del **proveedor oficial de marca** con licencia.
5. **Marca:** usar "Ciclovía" o "Chacomer" en tu dominio o nombre de tienda puede generar confusión de origen. Usalo solo en la descripción ("revendedor autorizado de…") y **nunca como marca de tu tienda**.

### 5.4 Precio mínimo (MAP), competencia desleal y canibalización

- **MAP (Minimum Advertised Price):** es una **política comercial**, no una ley paraguaya. En Paraguay **la Ley 4956/2013 no tipifica expresamente la fijación de precios de reventa (RPM)** como infracción; sí prohíbe prácticas concertadas que restrinjan la competencia y el abuso de posición dominante ([Ley 4956/2013](https://www.bacn.gov.py/leyes-paraguayas/4775/defensa-de-la-competencia)). Es decir: **es una zona gris que conviene pactar por escrito y validar con abogado**, no resolver por intuición.
- **El problema práctico del "mismo precio":** si tu precio es idéntico al de Ciclovía, no competís por precio sino por **servicio** (entrega, asesoría, cuotas, stock inmediato, postventa). Y si Ciclovía baja el precio online y vos no sincronizás a tiempo, **quedás más caro**; si sincronizás y Ciclovía tiene una promo exclusiva online, **te comés el margen**.
- **Verificá esto antes de fijar la política:** Ciclovía marca productos con **"Precio EXCLUSIVO Online"** (ej. [SCOTT Contrail 40](https://www.ciclovia.com.py/bicicleta-mtb-scott-contrail-40.html)). Si replicás ese precio, estás igualando la promo del fabricante con tu margen mayorista. Preguntá si esas promos **te aplican** en el costo mayorista.
- **Canibalización / SEO:** publicar 3.700 fichas idénticas a las de Ciclovía te posiciona peor (contenido duplicado) y refuerza la marca del fabricante, no la tuya. Estrategia: **títulos y descripciones propias**, fotos propias o autorizadas, y contenido de valor (guías de talle, comparativas, armado, mantenimiento). Para productos de bajo margen, considerar `noindex` y concentrar el esfuerzo SEO en categorías rentables.
- **Competencia desleal:** no hagas publicidad comparativa engañosa ni te presentes como "tienda oficial" si no lo sos.

### 5.5 Qué conviene acordar por escrito con Ciclovía/Chacomer (checklist)

1. **Condición de revendedor autorizado** (y si podés usar ese término en la web).
2. **Precio mayorista**: lista vigente, **¿incluye IVA?**, descuento por volumen, y **si las promociones online ("Precio Exclusivo Online") se trasladan al costo**.
3. **Suministro de datos**: ¿te dan **feed/API/CSV** de catálogo, precios y stock? ¿Con qué frecuencia? (Esto define la viabilidad técnica del sync.)
4. **Autorización de uso de imágenes, fichas, logos y marcas**, con alcance y plazo.
5. **Política de precios de venta** (sugerido / mínimo / libre) y qué pasa si publicás más barato.
6. **Stock y abastecimiento**: quién es dueño del stock, plazos de reposición, qué pasa si vendés algo sin stock.
7. **Garantía**: quién la atiende, dónde se recibe el producto, plazos, quién paga el flete de ida y vuelta.
8. **Devoluciones y cambios**: qué acepta el fabricante y en qué condiciones.
9. **Canal**: ¿podés vender en Mercado Libre y en tu web? ¿hay exclusividades territoriales o de canal?
10. **Qué pasa si terminás la relación**: liquidación de stock y retiro de material de marca.

---

## 6. Garantía cuando el revendedor no es el vendedor oficial

### 6.1 Frente al consumidor, el responsable sos vos

- **Vos emitís la factura**, entonces **vos sos el proveedor** ante el consumidor. No podés decirle "arreglá con Chacomer": la Ley 1334/1998 te obliga como proveedor, y la Ley 4868/2013 (art. 7 inc. g) exige **informar plazo, extensión y condiciones de la garantía** en el sitio.
- **Derecho de retracto** (Ley 4868/2013, art. 30 inc. b): el consumidor puede **retractarse dentro de 5 días hábiles** desde la recepción, con simple notificación electrónica, y se le devuelve lo pagado (si el producto no fue usado ni deteriorado). Los costos de retorno los cubre el consumidor.
- **Reembolso por variación** (art. 17): si lo entregado no coincide en **tiempo, cantidad y calidad** con lo publicitado, el consumidor puede reclamar dentro de **5 días hábiles** de recibido.
- **Excepciones al retracto** (art. 31): productos personalizados, perecederos, grabaciones/software abiertos, etc. **Una bici armada a medida por el cliente cae en la excepción.**
- **Sanción real y visible:** SEDECO sanciona por incumplir garantía (ver caso [Tecnolandia](https://sedeco.gov.py/sedeco-sanciona-a-tecnolandia-por-incumplir-con-la-garantia-de-un-televisor-defectuoso/)).

### 6.2 Frente al fabricante, depende de lo que firmes

Como revendedor, tu reclamo a Ciclovía/Chacomer es **comercial, no legal automático**. Lo que necesitás por escrito:

- **Quién es el responsable de la garantía** técnica (Ciclovía/Chacomer o un service autorizado de la marca: SCOTT, Cannondale, etc.).
- **Dónde se entrega** el producto defectuoso y **quién paga el flete**.
- **Plazo de reparación/reemplazo** y qué pasa si se excede.
- **Cómo se repone** el producto vendido en garantía (¿te lo reponen a costo? ¿te lo acreditan?).

**Plazos legales concretos de garantía:** la Ley 1334/1998 y el Código Civil rigen la materia, pero **los plazos varían por producto y por marca** y no están fijados en una tabla única. **No inventar plazos: preguntá a Chacomer/Ciclovía por marca** y publicá lo que te confirmen.

### 6.3 Recomendación operativa

1. Publicá una **"Política de garantía y devoluciones"** con: plazo, cómo iniciar el reclamo, dirección de recepción, quién paga el envío, y plazos de respuesta.
2. Definí un **canal único** de reclamos (WhatsApp + formulario + email) y registralo.
3. Antes de vender productos caros (bicis > Gs 3.000.000), confirmá por escrito el circuito de garantía de **esa** marca. Es la venta más riesgosa: un cambio de cuadro mal gestionado se come el margen de varias ventas.

---

## 7. "Vitrina + checkout por WhatsApp" vs. "carrito con pago online"

### 7.1 Comparación

| Dimensión | Vitrina + WhatsApp (link de pago/transferencia) | Carrito con pago online |
|---|---|---|
| **Costo de entrada** | **Gs 22.900** (Bancard TPago) o **Gs 0** (uPay Base) | Hosting + desarrollo/plugin + **Gs 74.900** (vPOS) o comisión uPay |
| **Costo por venta** | 0% si es transferencia; 2–2,9% si es link de pago | 2–2,9% (uPay) + costo fijo mensual |
| **Conversión** | Buena con audiencia tibia (redes, conocidos); **mala con tráfico frío** | Mejor con tráfico frío: el cliente compra sin hablar con nadie |
| **Carga operativa** | Alta: respondés 1 a 1, cotizás envío manual, conciliás el pago | Baja: el pedido entra armado |
| **Escalabilidad** | Se rompe rápido con 3.700 SKU y varios pedidos/día | Escala |
| **Datos y remarketing** | Casi nulos (el chat no te da carrito abandonado) | Carrito abandonado, píxel, audiencias |
| **Riesgo** | Errores de precio/stock en el chat | Exige check-out bien hecho y facturación integrada |
| **Mejor para** | Arrancar en 2 semanas, validar demanda, ticket alto con asesoría | Escalar y competir con tráfico pago |

### 7.2 Cuándo conviene cada una

- **Empezá con vitrina + WhatsApp/link de pago si:** todavía no tenés RUC al día, o no tenés quién mantenga la web, o querés validar qué categorías se venden. Con uPay Base (Gs 0) y un catálogo publicado ya estás operando.
- **Pasá a carrito con pago online cuando:** tengas tráfico frío (publicidad), más de ~5–10 pedidos/día, o cuando el costo de responder consultas supere el costo del checkout.
- **El híbrido es lo más sano:** carrito con pago online + **botón de WhatsApp** para consultas de talle/stock + **retiro en local**. Es exactamente lo que hace el mercado paraguayo.
- **Ojo con el marco de "a distancia":** si vendés por WhatsApp/redes, seguís siendo "proveedor por vía electrónica a distancia" bajo la Ley 4868/2013 y te aplican las mismas obligaciones de información, retracto y factura electrónica. **Vender por chat no te saca del régimen.**

### 7.3 Ejemplo ilustrativo de unit economics (números de ejemplo, NO verificados)

> Los siguientes valores son **hipotéticos** para mostrar el mecanismo de cálculo. Reemplazalos con tu lista mayorista real.

Supuestos de ejemplo: PVP = Gs 1.000.000; costo mayorista = Gs 720.000 (28% de descuento); envío gratis al cliente con costo real Gs 40.000; comisión de cobro 2,9% (crédito).

| Concepto | Monto (ejemplo) |
|---|---|
| Ingreso | Gs 1.000.000 |
| − Costo mayorista | − Gs 720.000 |
| − Comisión de cobro (2,9%) | − Gs 29.000 |
| − Envío absorbido | − Gs 40.000 |
| − IVA a pagar sobre la diferencia (10%, simplificado) | depende del crédito fiscal — calcular con contador |
| **Margen antes de IVA/impuestos y publicidad** | **≈ Gs 211.000 (21%)** |

Con un envío gratis más caro (bici, Gs 150.000) **el margen se vuelve negativo**. Conclusión: **el envío gratis solo es viable en accesorios livianos**, y el descuento mayorista real define todo el negocio.

---

## 8. Programas de revendedores / distribuidores de Chacomer o Ciclovía

**Lo que se pudo verificar:**

- **Chacomer S.A.E.** opera un sitio corporativo con **"Tienda mayorista"** en el encabezado (teléfono de contacto **+595 21 5191500**) y declara venta de hogar, herramientas, deportes (bicicletas, fitness, accesorios, suplementos, repuestos), auto, moto, indumentaria y máquinas ([chacomer.com.py](https://www.chacomer.com.py/)). Es decir: **existe un canal mayorista**, pero **no hay una página pública de "programa de revendedores" con requisitos y beneficios**.
- **Ciclovía** es la marca/tienda de bicis y fitness de Chacomer ([ciclovia.com.py](https://www.ciclovia.com.py/)); su sitio **no publica** un formulario de alta de revendedores ni condiciones de distribución.
- **No se encontró** un programa formal de distribuidores/revendedores publicado por Chacomer o Ciclovía (ni "sé distribuidor", ni condiciones, ni requisitos).

**Conclusión:** el acceso mayorista que ya tenés **es la relación comercial con el ejecutivo de Chacomer**, no un programa público. Por eso el checklist de la §5.5 es todavía más importante: **lo que no esté por escrito, no existe**. Preguntá explícitamente: *"¿Tienen un programa formal de revendedores con contrato, feed de precios y condiciones de garantía?"* si la respuesta es no, pedí al menos un **acuerdo marco escrito** con los 10 puntos del checklist.

---

## 9. Recomendación final y plan de acción

### 9.1 La recomendación en una línea

> **WooCommerce auto-hospedado** (alternativa: PrestaShop) + **uPay** como pasarela + **Bancard TPago** para links de pago por WhatsApp + **AEX** para envíos + **E-kuatia'i** para facturación, arrancando en modo **vitrina con checkout por WhatsApp** y activando el carrito con pago online cuando haya volumen.

### 9.2 Plan por fases

**Fase 0 — Antes de tocar la web (semana 1).** Confirmar con Ciclovía/Chacomer: descuento mayorista exacto, si incluye IVA, si las promos online trasladan al costo, y si hay **feed/API/CSV** de catálogo y stock. Sin esto, cualquier plataforma es una apuesta.

**Fase 1 — Legal y cobros (semanas 1–2).** RUC al día → alta en uPay Base (Gs 0) → alta en E-kuatia'i si es un solo punto de expedición → abrir cuenta corriente en AEX. Costo directo: prácticamente cero; el costo es tiempo.

**Fase 2 — Vitrina (semanas 2–4).** Publicar catálogo con sync (aunque sea semi-automático) en WooCommerce. Foco en accesorios, suplementos e indumentaria (envío rentable). Bicis: retiro en local o flete cotizado. Costo: hosting USD 8,81–14,09/mes + dominio (~USD 12–15/año) + desarrollo del sync (**a cotizar**).

**Fase 3 — Checkout online (mes 2–3).** Activar uPay Pro (Gs 45.000/mes) o Bancard vPOS (Gs 74.900) sobre el carrito. Medir conversión vs. WhatsApp.

**Fase 4 — Escala (mes 3+).** Mercado Libre como canal complementario, AEX con API integrada, logística inversa para garantías, y contenido SEO propio para no depender del duplicado.

### 9.3 Riesgos a vigilar

| Riesgo | Impacto | Mitigación |
|---|---|---|
| El descuento mayorista es menor al supuesto | Margen negativo | Confirmar por escrito antes de invertir |
| Promos online de Ciclovía no trasladan al costo | Vendés a pérdida | Cláusula de paridad de promociones |
| Scraping sin autorización del catálogo | Legal + bloqueo técnico | Pedir feed/API oficial; si no, autorización escrita |
| Copiar fotos/textos | Reclamo de PI, baja de catálogo | Autorización escrita o material propio |
| Envío gratis en bici | Pérdida por venta | Flete cotizado y visible en la ficha |
| Facturación electrónica mal integrada | Multas DNIT | E-kuatia'i o facturador designado desde el día 1 |
| Reventa no autorizada / conflicto de canal | Pérdida de la cuenta mayorista | Acuerdo marco con condiciones de canal |

### 9.4 Preguntas para enviar hoy a Chacomer/Ciclovía

1. ¿Cuál es el **descuento mayorista** por línea y a partir de qué volumen?
2. El precio mayorista, **¿incluye IVA?**
3. ¿Me pasan **feed/API/CSV** diario de **precio, stock y variantes**?
4. Las promociones "**Precio Exclusivo Online**", ¿se trasladan al costo mayorista?
5. ¿Tengo **autorización escrita** para usar fotos, fichas técnicas y logos?
6. ¿Puedo **vender online y en Mercado Libre**? ¿Hay restricciones de canal o territorio?
7. **Garantía:** ¿quién la atiende, dónde entrego, quién paga el flete, en qué plazo?
8. ¿Existe un **contrato marco de reventa**? ¿Me lo pueden enviar?
9. ¿Qué pasa con el **stock** si vendo un producto que no tienen?
10. ¿Hay **precio sugerido** de venta al público y qué pasa si publico distinto?

---

## 10. Anexo: datos verificados vs. a cotizar

### Verificados en fuente oficial (con URL)

| Dato | Valor | Fuente |
|---|---|---|
| Cantidad de productos en catálogo Ciclovía | 3.778 URLs `.html` (3.922 URLs en sitemap, incluye categorías) | [sitemap.xml](https://www.ciclovia.com.py/sitemap.xml) |
| Bancard vPOS | Gs 74.900 IVA incl. | [vPOS](https://www.bancard.com.py/vpos) |
| Bancard TPago | Gs 22.900 IVA incl. | [TPago](https://www.bancard.com.py/tpago) |
| uPay comisiones | 2% débito/QR · 2,9% crédito · 3% internacional | [upay.com.py](https://upay.com.py/) |
| uPay planes | Gs 0 · Gs 45.000/mes (solo RUC) · personalizado | [upay.com.py](https://upay.com.py/) |
| acreditación uPay | 24 h hábiles débito/QR · 48 h crédito | [upay.com.py](https://upay.com.py/) |
| Shopify precios | USD 19/25 · 49/65 · 299/399 · Plus 2.300 | [shopify.com/pricing](https://www.shopify.com/pricing) |
| Shopify recargo pasarela externa | 2% Basic · 1% Grow | [shopify.com/pricing](https://www.shopify.com/pricing) |
| Hosting PY | desde USD 4,15/mes (anual) | [IDEIHOSTING](https://ideihosting.com/py/hosting-compartido/) |
| Tiendli PY | ₲ 0 / 75.000 / 150.000 / 225.000 al mes | [tiendli.com/py](https://tiendli.com/py) |
| IVA Paraguay | 5% y 10%, mensual, obligación 211 | [DNIT — IVA](https://www.dnit.gov.py/web/portal-institucional/iva) |
| SIFEN | E-kuatia'i (1 punto, firma gratis) vs E-kuatia | [DNIT — Factura electrónica](https://www.dnit.gov.py/web/portal-institucional/factura-electronica) |
| Retracto consumidor | 5 días hábiles | [Ley 4868/2013, art. 30](https://www.bacn.gov.py/leyes-paraguayas/961/ley-n-4868-comercio-electronico) |
| Reembolso por variación | 5 días hábiles | [Ley 4868/2013, art. 17](https://www.bacn.gov.py/leyes-paraguayas/961/ley-n-4868-comercio-electronico) |
| Sanciones Ley 4868 | hasta 1.000 jornales mínimos | [Ley 4868/2013, art. 38](https://www.bacn.gov.py/leyes-paraguayas/961/ley-n-4868-comercio-electronico) |
| AEX | pick up sin costo, puerta a puerta, pago en destino, logística inversa, e-Locker | [aex.com.py](https://www.aex.com.py/web/) |
| AEX + Shopify | integración documentada (requiere cuenta corriente AEX) | [AEX Shopify](https://www.aex.com.py/web/shopify/configuracion.php) |

### A cotizar (no publicado, no inventar)

- Tarifas de envío AEX por zona/peso (usar [cotizador](https://www.aex.com.py/web/calcular-envios.php) o ejecutivo).
- Tarifas de Dinacopa / Dinacopa Box.
- Moto-delivery en Asunción (tarifa base, por km, seguro).
- Mirtrans: existencia/condiciones del servicio (dominio no accesible).
- Comisiones de Mercado Libre Paraguay por categoría.
- Comisiones de Tigo Money para comercios.
- Costo de WEPA como punto de cobranza para e-commerce.
- Si los Gs 74.900 (vPOS) y Gs 22.900 (TPago) son alta única o abono mensual.
- Costo de desarrollo de la sincronización de catálogo.
- Costo de apps/extensions de Shopify para importación masiva.
- Descuento mayorista real de Ciclovía/Chacomer y si incluye IVA.
- Plazos de garantía por marca.

---

## 11. Fuentes consultadas

**Plataformas:** [WooCommerce](https://woocommerce.com/pricing/) · [PrestaShop](https://www.prestashop-project.org/) · [Shopify](https://www.shopify.com/pricing) · [Tiendli PY](https://tiendli.com/py) · [Tiendanube](https://www.tiendanube.com/) · [Empretienda](https://empretienda.com/) · [Bsale Chile](https://www.bsale.cl/) · [Bsale Perú](https://www.bsale.com.pe/) · [Bsale México](https://www.bsale.com.mx/) · [Bsale Colombia](https://www.bsale.co/) · [Mercado Libre PY](https://www.mercadolibre.com.py/) · [Mercado Shops PY (redirige a ML)](https://www.mercadoshops.com.py/) · [Hosting PY](https://ideihosting.com/py/hosting-compartido/)

**Pagos:** [Bancard](https://www.bancard.com.py/) · [Bancard vPOS](https://www.bancard.com.py/vpos) · [Bancard TPago](https://www.bancard.com.py/tpago) · [Bancard factura electrónica](https://www.bancard.com.py/factura-electronica) · [uPay](https://upay.com.py/) · [uPay/Pagopar](https://upay.com.py/pagopar/) · [Tigo Money negocio](https://ayuda.tigo.com.py/hc/centro-de-ayuda/articles/2386174965809711-como-crear-un-perfil-a-mi-negocio) · [WEPA](https://www.wepa.com.py/)

**Logística:** [AEX](https://www.aex.com.py/web/) · [AEX API](https://www.aex.com.py/web/documentacion-api.php) · [AEX Shopify](https://www.aex.com.py/web/shopify/configuracion.php) · [AEX cotizador](https://www.aex.com.py/web/calcular-envios.php) · [AEX Cargo](https://www.aex.com.py/web/servicios/aex-cargo.php) · [Dinacopa](https://www.correoparaguayo.gov.py/) · [Dinacopa Box](https://clubdinacopabox.com.py/)

**Fiscal:** [DNIT](https://www.dnit.gov.py/) · [Factura electrónica](https://www.dnit.gov.py/web/portal-institucional/factura-electronica) · [e-Kuatia](https://ekuatia.set.gov.py/web/e-kuatia/) · [IVA](https://www.dnit.gov.py/web/portal-institucional/iva) · [Inscripción RUC](https://www.dnit.gov.py/web/portal-institucional/inscripcion-al-ruc) · [IRE RESIMPLE](https://www.dnit.gov.py/web/portal-institucional/ire-resimple)

**Legal:** [Ley 4868/2013 Comercio Electrónico](https://www.bacn.gov.py/leyes-paraguayas/961/ley-n-4868-comercio-electronico) · [Ley 1334/1998 Defensa del Consumidor](https://www.bacn.gov.py/leyes-paraguayas/897/ley-n-1334-de-defensa-del-consumidor-y-del-usuario) · [Ley 4956/2013 Defensa de la Competencia](https://www.bacn.gov.py/leyes-paraguayas/4775/defensa-de-la-competencia) · [SEDECO](https://sedeco.gov.py/) · [DINAPI](https://www.dinapi.gov.py/)

**Catálogo:** [Ciclovía](https://www.ciclovia.com.py/) · [Sitemap](https://www.ciclovia.com.py/sitemap.xml) · [Chacomer](https://www.chacomer.com.py/)

---

*Documento elaborado con fuentes públicas consultadas el 21/10/2026. Los precios y comisiones cambian: reconfirmar antes de firmar cualquier contrato. Este documento no constituye asesoría legal ni contable; las secciones 4, 5 y 6 deben validarse con un contador y un abogado paraguayos.*
