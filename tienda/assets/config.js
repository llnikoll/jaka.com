/* =====================================================================
   Configuración de la tienda
   Cambiá acá el WhatsApp, el nombre y los textos. No hace falta tocar
   el resto del código.
   ===================================================================== */
window.TIENDA_CONFIG = {
  // Nombre que aparece en el encabezado y en el mensaje del pedido
  marca: "Jaka Bicicletería",
  // WhatsApp que recibe los pedidos: solo números, con código de país (Paraguay = 595)
  whatsapp: "595993539237",
  whatsappVisible: "+595 993 539 237",
  // Ubicación del local (Google Maps) — se usa en el encabezado, la franja y el pie
  ubicacion: "https://maps.app.goo.gl/fmhizu2Qwd3aCJEZ9",
  // Formato de moneda
  moneda: "Gs.",
  // Entrega
  envio: {
    habilitado: true,
    etiqueta: "Envío a domicilio",
    nota: "El costo del envío se coordina por WhatsApp según la zona."
  },
  retiro: {
    habilitado: true,
    etiqueta: "Retiro en local",
    nota: "Te confirmamos la dirección del local por WhatsApp."
  },
  // Cantidad de productos que se muestran por tanda
  porPagina: 24,
  // Precio limpio: un solo precio, sin tachado ni % de descuento
  // (poné true si algún día querés mostrar el precio anterior y el descuento)
  mostrarPrecioAnterior: false,
  mostrarDescuento: false,
  // ------------------- Margen de ganancia -------------------
  // Recargo que se suma a los precios del catálogo original.
  // 15 = +15 % · 0 = precio original · 22.5 = +22,5 %
  recargoPct: 15,
  // Segundo tramo: si el precio de venta no supera `umbralBajo`, se le suma
  // un recargo extra de `recargoBajoPct` % (productos baratos).
  // Ejemplo: Gs 100.000 -> 115.000 (+15%) -> 138.000 (+20% extra)
  recargoBajoPct: 20,
  umbralBajo: 300000,
  // Redondeo del precio de venta: true = a Gs 10 / 100 / 1.000 / 10.000 según el monto
  // (false = número exacto, puede quedar Gs 9.324.315)
  redondeoPrecio: true,
  // Vista que se muestra al abrir la tienda ("accesorios", "bicicletas", "todos"…)
  categoriaInicial: "accesorios",
  // Base de las imágenes. Para rehospedar fotos, cambiá esto por "img/" y
  // poné las imágenes en la carpeta img/ de la tienda.
  imagenBase: "https://www.ciclovia.com.py/media/catalog/product/",
  // Tamaño chico para la grilla (rápido) y grande para la ficha
  imagenParams: "?quality=80&fit=bounds&height=300&width=300&canvas=300:300",
  imagenParamsGrande: "?quality=85&fit=bounds&height=800&width=800&canvas=800:800"
};
