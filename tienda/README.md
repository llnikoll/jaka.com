# Jaka Bicicletería — tienda con pedidos por WhatsApp

**En línea:** https://llnikoll.github.io/jaka.com/

Tienda estática con las **2.681 productos** de bicicletas, accesorios, repuestos, fitness e indumentaria,
**recargo de margen configurable (+15 % por defecto)** y una **canasta que envía el pedido completo a tu WhatsApp**
(detalle, cantidades, total, datos y ubicación del cliente).

No necesita base de datos, ni servidor propio, ni pasarela de pago: es HTML + CSS + JavaScript.

- WhatsApp: **+595 993 539 237**
- Ubicación (Google Maps): https://maps.app.goo.gl/fmhizu2Qwd3aCJEZ9
- Logo: `assets/jaka-logo.webp` (original) → iconos y favicons generados con `assets/procesar-logo.py`

---

## 1. Ver la tienda

**Para probar en la PC** (servidor local con compresión gzip):

```powershell
cd C:\Users\jakao\Proyectos\bicitienda
python tienda\servidor.py 8080
# abrir http://127.0.0.1:8080
```

**Para compartirla online** (servidor + túnel de Cloudflare, un solo comando):

```powershell
.\tienda\lanzar.ps1            # levanta todo, muestra la URL y abre el navegador
.\tienda\lanzar.ps1 -Detener   # apaga servidor y túnel
```

Te imprime una URL `https://….trycloudflare.com` y la copia al portapapeles. **Esa URL cambia cada vez
que lanzás el túnel** y no tiene garantía de uptime: sirve para mostrar la tienda y tomar pedidos un rato.
Para una dirección fija hay que publicar en un hosting (§3).

El servidor sirve HTML, CSS, JS y JSON **comprimidos** (gzip): la vista inicial de Accesorios pesa
**55 KB** en lugar de 287 KB.

**Opción rápida (sin servidor):** abrí `tienda/index.html` con doble clic. Funciona, pero carga el catálogo
completo de una vez (más lento) porque el respaldo está en `data/catalogo.js`.

## 2. Cómo se usa (flujo del cliente)

1. Entra al catálogo (abre en **Accesorios**), filtra por categoría o busca.
2. Toca **Agregar a la canasta** (productos con precio publicado).
3. Abre la **canasta**, ajusta cantidades y toca **Finalizar pedido**.
4. Completa nombre, teléfono, entrega (envío o retiro), dirección y —opcional— **Compartir mi ubicación exacta**.
5. Toca **Enviar pedido por WhatsApp**: se abre WhatsApp con el mensaje ya armado y el número cargado.

El mensaje que te llega tiene este formato:

```
🛒 NUEVO PEDIDO — Jaka Bicicletería
Fecha: 21/10/2026 15:42

Productos:
1. BICICLETA MTB SCOTT SCALE 960
    1 x Gs. 8.108.100 = Gs. 8.108.100

Total productos: Gs. 8.108.100
Envío: a coordinar (no incluido en el total)

Datos de entrega:
Nombre: ...
Teléfono: ...
Tipo: Envío a domicilio
Dirección: Av. España 1234, Villa Morra, Asunción
Referencia: Portón negro
Ubicación: https://www.google.com/maps?q=-25.286600,-57.610600

Pedido generado desde la web.
```

Si el navegador bloquea la ventana, queda un enlace directo y el botón **Copiar pedido** como respaldo.

## 3. Publicarla

La carpeta `tienda/` es el sitio completo. Cualquier hosting estático sirve:

| Opción | Cómo |
|---|---|
| **Netlify** | Arrastrar la carpeta `tienda` en [app.netlify.com/drop](https://app.netlify.com/drop) |
| **Vercel** | `vercel --prod` dentro de `tienda/` |
| **GitHub Pages** | Subir el contenido de `tienda/` a la rama `gh-pages` |
| **Hosting cPanel / compartido** | Subir el contenido por FTP a `public_html` |

Recomendado al publicar: **HTTPS** (necesario para el GPS del cliente) y **gzip** (el catálogo pesa 994 KB → ~164 KB comprimido).

## 4. Actualizar los precios

Cuando cambian los precios en Ciclovía:

```powershell
.\tienda\actualizar.ps1
```

Ese único comando hace las dos cosas: **lee el sitio** (`poc/scraper_ciclovia.py`) y **regenera el catálogo**
(`build_catalogo.py`). Tarda 3–5 minutos, imprime cuántos precios cambiaron y deja el detalle en
`tienda/data/ultimos_cambios.json`.

Después subí al hosting **la carpeta `tienda/data/`** (o solo lo que cambió):

```
tienda/data/indice.json
tienda/data/indice.js
tienda/data/v/*.json        (una por vista: accesorios, bicicletas, fitness, …)
```

No hace falta tocar el HTML ni redeployar nada más: la tienda toma los precios nuevos en la siguiente visita.
`data/catalogo.json` y `data/catalogo.js` son solo respaldo local (para abrir sin servidor) y no hace falta subirlos.

> Atajo sin red: `.\tienda\actualizar.ps1 -SinRed` regenera desde la caché local (0 requests, útil para probar).

### ¿Se actualiza sola? Sí — en la nube

El workflow **`.github/workflows/actualizar-catalogo.yml`** corre en GitHub **todos los días a las 06:00 de
Paraguay** (09:00 UTC): lee el sitio, regenera el catálogo, hace commit + push y GitHub Pages republica.
No depende de que la PC esté encendida.

- **Ver corridas / forzar una:** https://github.com/llnikoll/jaka.com/actions → “Actualizar catalogo y publicar”.
- **Cambiar la hora:** editar el `cron` del workflow (está en UTC; Paraguay = UTC-3).
- **Si la actualización falla:** la tienda sigue online con la última versión publicada.

La tarea de Windows (`programar.ps1`) quedó **desactivada** para que no haya dos publicadores. Si algún día
querés volver a actualizar desde tu PC: `.\tienda\actualizar.ps1` (lee, regenera y publica por git).

### Publicación automática en el hosting

La tarea puede subir sola los datos. Elegí un modo:

1. Copiá `tienda\publicar.config.ejemplo.ps1` como **`tienda\publicar.config.ps1`**.
2. Descomentá **un** modo y completá los datos:

```powershell
# Modo FTP (hosting compartido / cPanel)
$Publicacion = @{
  Modo          = 'ftp'
  Host          = 'ftp.tudominio.com.py'
  Usuario       = 'usuario'
  Clave         = 'contraseña'
  CarpetaRemota = '/public_html/'
}
```

```powershell
# Modo git (Netlify, Vercel o GitHub Pages conectados al repo)
$Publicacion = @{ Modo = 'git' }
```

3. Probá sin tocar nada: `.\tienda\publicar.ps1 -SoloVerificar`.

> `publicar.config.ps1` tiene contraseñas: no lo compartas ni lo subas a un repositorio público.

**Qué se refleja y qué no:**

| Se refleja | No se refleja |
|---|---|
| Precio final (con +15 % incluido) | Cantidades exactas de stock (el sitio solo dice “En stock / Sin stock”) |
| % de descuento | Textos de promociones (“Precio EXCLUSIVO Online”, cuotas) |
| Stock (“En stock” / “Sin stock”) | Costo mayorista (viene de tu lista) |
| Nombre, marca, categoría, imagen | Precio por variante: se publica el mínimo y el talle se confirma por WhatsApp |
| Altas y bajas de productos | Descripciones largas y especificaciones (no se muestran en la tienda) |

La página muestra siempre **“Catálogo actualizado: dd/mm/aaaa hh:mm”** y ese mismo dato viaja en el mensaje del
pedido, para que sepas si el cliente vio un precio viejo.

## 5. Configuración (sin tocar código)

Todo lo editable está en **`assets/config.js`**:

| Campo | Para qué |
|---|---|
| `marca` | Nombre de la tienda (`Jaka Bicicletería`) |
| `whatsapp` / `whatsappVisible` | Número que recibe los pedidos y cómo se muestra |
| `ubicacion` | Link de Google Maps del local (encabezado, franja y pie) |
| `moneda` | Prefijo de precios (`Gs.`) |
| `envio` / `retiro` | Etiquetas y notas de entrega |
| `porPagina` | Productos que se muestran por tanda |
| `categoriaInicial` | Vista al abrir (`accesorios` por defecto; también `bicicletas`, `fitness`, `todos`…) |
| `imagenBase` / `imagenParams` / `imagenParamsGrande` | De dónde salen las fotos y en qué tamaño |
| `enlaceBase` | Base del link “ver ficha original” |

## 6. Reglas que ya están implementadas

- **Precio limpio:** un solo precio por producto, con el **+15 % ya incluido**. No se muestra el precio anterior
  tachado, ni el % de descuento, ni ningún enlace a la página original (`mostrarPrecioAnterior` y
  `mostrarDescuento` en `config.js`, ambos en `false`).
- **Sin stock:** se puede pedir igual, pero el pedido llega marcado `⚠️ SIN STOCK (confirmar)`.
- **Sin precio** (productos “a consultar”): no se agregan a la canasta; el botón abre WhatsApp para consultar.
- **Variantes:** en las bicis el precio depende del talle/color; por eso la tarjeta muestra el precio mínimo publicado
  y el detalle se confirma por WhatsApp antes de facturar.
- **Envío:** no se cobra en la web; se coordina por WhatsApp (el total del pedido no incluye envío).
- **Canasta persistente:** sobrevive al cerrar el navegador (localStorage).
- **Validación:** nombre, teléfono y dirección obligatorios para envío.

### Margen de ganancia (cómo cambiarlo)

Todo se controla en `assets/config.js`:

```js
recargoPct: 15,          // +15 % a todo el catálogo · 0 = precio original
recargoBajoPct: 20,      // +20 % extra para los productos baratos
umbralBajo: 300000,      // Gs: si el precio ORIGINAL no supera este monto, se aplica el extra
redondeoPrecio: true,    // Gs 10 / 100 / 1.000 / 10.000 según el monto
```

**Cómo se calcula (dos tramos, sumados):**

- Productos con **precio original > Gs 300.000**: original × **1,15**.
- Productos con **precio original ≤ Gs 300.000**: original × **1,35** (el 15 % + el 20 % extra **se suman**).

En ambos casos el resultado se redondea hacia arriba (Gs 10 / 100 / 1.000 / 10.000 según el monto).

Ejemplos reales del catálogo:

| Original | ¿Aplica extra? | Cálculo | Precio final |
|---:|---|---:|---:|
| Gs 50.000 | sí (≤ 300.000) | × 1,35 | **67.500** |
| Gs 100.000 | sí | × 1,35 | **135.000** |
| Gs 150.000 | sí | × 1,35 | **203.000** |
| Gs 251.500 | sí | × 1,35 | **340.000** |
| Gs 266.305 | sí | × 1,35 | **360.000** |
| Gs 301.800 | no (> 300.000) | × 1,15 | **348.000** |
| Gs 1.000.000 | no | × 1,15 | **1.150.000** |

Hoy: **1.339 productos** llevan el +35 % total (15 + 20) y **926** quedan solo con el 15 %.

Se aplica en el momento: la tarjeta, la ficha, la canasta, el total y el mensaje de WhatsApp usan el mismo precio.
No hay que regenerar el catálogo ni esperar la actualización diaria; alcanza con recargar la página
(Ctrl+F5 por la caché del navegador). **El feed de Meta se regenera con la corrida diaria**, para que los precios
del catálogo coincidan con la web.

**Antes de cambiar el porcentaje tené en cuenta:**

- Deja de ser “mismo precio que Ciclovía”: quien compare con la página original va a ver la diferencia. Podés
  compensarlo con servicio (entrega local, asesoramiento, cuotas, garantía).
- Si tu acuerdo de reventa fija precios sugeridos (MAP), el recargo en general es válido porque estás **por encima**
  del mínimo; confirmalo igual con ellos.
- El recargo no reemplaza el control de margen contra tu **costo mayorista**: si una promo de Ciclovía deja el
  precio original por debajo de tu costo, el +15 % puede no alcanzar. Pasame la lista mayorista y agrego la alerta
  automática de “producto a pérdida”.
- Podés usar un porcentaje distinto por rubro si después hace falta (hoy es global).

## 7. Pruebas hechas

Prueba automatizada de punta a punta (navegador real, 9 verificaciones): catálogo renderizado, agregar 2 productos,
contador, apertura de canasta, suma de unidades, apertura de checkout, validación de campos, generación del enlace
de WhatsApp, subtotal = total del checkout y vaciado de canasta. **9/9 OK.**

Segunda prueba (catalogación por vistas): **10/10 OK** — abre en Accesorios (752), cambia a Bicicletas cargando
bajo demanda (1.302), muestra 7 chips de subcategoría, la búsqueda global encuentra 44 productos con “casco”,
y el flujo canasta → checkout → WhatsApp sigue funcionando.

Tarea programada: corrida real disparada desde el Programador de tareas → **resultado 0**, catálogo regenerado y
publicación omitida por falta de `publicar.config.ps1` (comportamiento esperado).

## 8. Rendimiento

Antes la tienda cargaba **994 KB** de catálogo para mostrar la primera pantalla. Ahora:

| Recurso | Antes | Ahora |
|---|---:|---:|
| Índice (categorías y conteos) | — | **1 KB** (gzip) |
| Vista inicial (Accesorios, 752 productos) | 994 KB | **55 KB** (gzip) |
| Catálogo completo | 994 KB | solo se carga si buscás o entrás a “Todos” (~160 KB gzip) |
| Imagen de tarjeta | 500×500 | **300×300** (la ficha usa 800×800) |
| Productos por tanda | 48 | **24** |

Además el servidor local (`tienda/servidor.py`) comprime y manda `Cache-Control` para que la segunda visita sea
instantánea. En un hosting real (Netlify, Vercel, cPanel) la compresión viene activada.

## 9. Notas

- **Imágenes:** hoy se muestran desde el CDN de Ciclovía solo como referencia. Para producción conviene
  rehospedarlas (cambiando `imagenBase` a `img/`) y **contar con autorización de uso** de las fotos y textos.
- **Datos de productos:** los precios y la disponibilidad vienen del catálogo público de Ciclovía; el catálogo se
  actualiza desde `poc/`. Si cambian el diseño del sitio, hay que revisar el parser (ver `recon/ANALISIS_TECNICO.md` §12).
- **Modo QA:** `index.html?demo=1` carga una canasta y un checkout de ejemplo. No lo uses en producción.
