# Publicidad en Facebook / Instagram

Esta carpeta genera el **feed de productos para Meta** (Commerce Manager) a partir del catálogo de la tienda.

## El archivo que se sube

`tienda/publicidad/catalogo-meta.csv` — se publica automáticamente en:

```
https://llnikoll.github.io/jaka.com/publicidad/catalogo-meta.csv
```

Ese CSV ya tiene el formato que pide Meta: `id, title, description, availability, condition, price, link, image_link, brand, google_product_category` + etiquetas propias (`custom_label_0/1/2`) para armar conjuntos de productos.

- **2.266 productos** con precio (el resto está “a consultar” y no entra).
- Precio con el **+15 %** incluido, redondeado igual que la tienda.
- `availability` respeta el stock: 950 productos figuran como `out of stock`.
- Cada `link` abre la ficha del producto en la tienda: `https://llnikoll.github.io/jaka.com/?p=<id>&v=<vista>`.

## Cómo cargarlo en Meta (una sola vez)

1. Entrá a **https://business.facebook.com/commerce** → **Crear catálogo** → tipo **Comercio electrónico**.
2. En el catálogo: **Origen de datos → Agregar productos → Carga programada** (scheduled feed).
3. Pegá esta URL:
   ```
   https://llnikoll.github.io/jaka.com/publicidad/catalogo-meta.csv
   ```
4. Frecuencia: **diaria**. Zona horaria: la que prefieras.
5. Guardá y esperá el primer procesamiento (10–30 min). Meta te muestra errores fila por fila si algo no le gusta.

> También podés descargar el CSV y subirlo manualmente con “Carga de archivo”, pero con la URL se
> actualiza solo todos los días junto con los precios.

## Vincular el catálogo

- **Página de Facebook** → Configuración → Cuentas vinculadas → catálogo.
- **Cuenta publicitaria** → se elige al crear la campaña.
- **Pixel** → `tienda/assets/config.js` (`pixelId`) y Business Settings → Orígenes de datos.
- **Instagram** (opcional) → misma configuración del catálogo.

## Conjuntos de productos recomendados (en Commerce Manager)

| Nombre | Filtro |
|---|---|
| `ticket-alto` | `custom_label_2` es `ticket-alto` |
| `en-stock` | `custom_label_1` es `stock` |
| `bicicletas` | `custom_label_0` es `bicicletas` |
| `ofertas` | precio con descuento (requiere campo `sale_price`, no incluido) |

Para anuncios de venta directa empezá por **`ticket-alto` + `en-stock`**: son los que soportan el costo publicitario con un margen del 15 %.

## Regenerar a mano

```powershell
python publicidad/generar_feed.py
python publicidad/generar_feed.py --min-precio 800000 --solo-stock   # solo los que conviene anunciar
```

Si cambiás el recargo en `tienda/assets/config.js`, volvé a generar el feed (o esperá la corrida diaria)
para que los precios del catálogo coincidan con la web.

## Aviso importante

- Meta exige que el **precio del catálogo coincida con el de la página**. Si no coincide, rechaza los anuncios.
- Las **imágenes** se sirven desde el CDN de Ciclovía; si Meta las rechaza, hay que rehospedarlas (ver `PLAN.md`).
- Los anuncios de catálogo **no necesitan** una tienda dentro de Facebook; se usan con la cuenta publicitaria y el pixel.
