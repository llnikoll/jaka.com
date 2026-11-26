/* =====================================================================
   Bici Tienda — lógica de la tienda
   Catálogo por vistas (carga bajo demanda) + canasta + pedido por WhatsApp.
   Sin dependencias: se puede subir a cualquier hosting.
   ===================================================================== */
'use strict';

(() => {
  const CONFIG = Object.assign({
    marca: 'Bici Tienda',
    whatsapp: '595993539237',
    whatsappVisible: '',
    moneda: 'Gs.',
    envio: { habilitado: true, etiqueta: 'Envío a domicilio', nota: '' },
    retiro: { habilitado: true, etiqueta: 'Retiro en local', nota: '' },
    porPagina: 24,
    // Mostrar precio anterior tachado y el % de descuento en la tienda
    mostrarPrecioAnterior: false,
    mostrarDescuento: false,
    categoriaInicial: 'accesorios',
    imagenBase: 'https://www.ciclovia.com.py/media/catalog/product/',
    imagenParams: '?quality=80&fit=bounds&height=300&width=300&canvas=300:300',
    imagenParamsGrande: '?quality=85&fit=bounds&height=800&width=800&canvas=800:800'
  }, window.TIENDA_CONFIG || {});

  const CLAVE_CARRITO = 'bicitienda_canasta_v1';
  const MAX_POR_ITEM = 99;
  const PLACEHOLDER = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(
    '<svg xmlns="http://www.w3.org/2000/svg" width="300" height="300"><rect width="300" height="300" fill="#f1f5f9"/><path d="M95 185h110l-14-45H109l-14 45Zm22 0a12 12 0 1 0 0 24 12 12 0 0 0 0-24Zm66 0a12 12 0 1 0 0 24 12 12 0 0 0 0-24Z" fill="none" stroke="#cbd5e1" stroke-width="7" stroke-linejoin="round"/></svg>'
  );

  const ESTADOS = {
    0: { texto: 'En stock', clase: 'ok', comprable: true },
    1: { texto: 'Sin stock', clase: 'agotado', comprable: true },
    2: { texto: 'A consultar', clase: 'consultar', comprable: false },
    3: { texto: 'A consultar', clase: 'consultar', comprable: false }
  };

  /* ------------------------------------------------------------------ */
  /* Estado                                                              */
  /* ------------------------------------------------------------------ */
  const estado = {
    indice: null,
    vistas: {},            // slug -> array de productos ya cargados
    completo: null,        // catálogo completo (solo si el modo dividido no está disponible)
    vistaActual: null,
    cargando: null,
    tokenCarga: 0,
    categoria: CONFIG.categoriaInicial,
    subcategoria: null,
    busqueda: '',
    orden: 'relevancia',
    soloDisponibles: false,
    mostrados: CONFIG.porPagina,
    canasta: [],
    ubicacion: null,
    productoAbierto: null,
    demo: new URLSearchParams(location.search).has('demo')
  };

  /* ------------------------------------------------------------------ */
  /* Utilidades                                                          */
  /* ------------------------------------------------------------------ */
  const $ = (sel, raiz = document) => raiz.querySelector(sel);
  const $$ = (sel, raiz = document) => Array.from(raiz.querySelectorAll(sel));
  const esc = (txt) => String(txt ?? '').replace(/[&<>"']/g, (c) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[c]));

  const normalizar = (txt) => String(txt ?? '')
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '');

  const fmt = (n) => {
    if (n === null || n === undefined) return '';
    return `${CONFIG.moneda} ${Number(n).toLocaleString('es-PY')}`;
  };

  const fechaHora = (iso) => {
    if (!iso) return '';
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return '';
    const dos = (n) => String(n).padStart(2, '0');
    return `${dos(d.getDate())}/${dos(d.getMonth() + 1)}/${d.getFullYear()} ${dos(d.getHours())}:${dos(d.getMinutes())}`;
  };

  const sinStock = (p) => p.e === 1;
  const conPrecio = (p) => p.p !== null && p.p !== undefined;
  const urlImagen = (p, grande = false) => {
    if (!p.img) return '';
    if (p.img.startsWith('http')) return p.img;
    const base = p.ch ? (CONFIG.imagenBaseMotos || CONFIG.imagenBase) : CONFIG.imagenBase;
    return base + p.img + (grande ? CONFIG.imagenParamsGrande : CONFIG.imagenParams);
  };

  // ------------------- Recargo comercial (margen) -------------------
  // Se aplica sobre el precio publicado del catálogo de origen.
  // - Precio original > umbralBajo  -> recargoPct (15 %)
  // - Precio original <= umbralBajo -> recargoBajoPct (25 %), NO se suman
  const redondearVenta = (valor) => {
    if (CONFIG.redondeoPrecio === false || Number(CONFIG.redondeoPrecio) === 0) return Math.round(valor);
    // Redondeo hacia arriba para no perder margen nunca (Gs 10 / 100 / 1.000 / 10.000)
    const paso = valor < 1000 ? 10 : valor < 100000 ? 100 : valor < 1000000 ? 1000 : 10000;
    return Math.ceil(valor / paso) * paso;
  };

  const aplicarRecargo = (valor) => {
    if (valor === null || valor === undefined) return valor;
    const original = Number(valor);
    const general = Number(CONFIG.recargoPct) || 0;
    const bajo = Number(CONFIG.recargoBajoPct) || 0;
    const umbral = Number(CONFIG.umbralBajo) || 0;
    // El umbral se compara contra el precio ORIGINAL
    const esBarato = bajo > 0 && umbral > 0 && original <= umbral;
    const porcentaje = esBarato ? bajo : general;
    return porcentaje ? redondearVenta(original * (1 + porcentaje / 100)) : Math.round(original);
  };
  const precioVenta = (p) => aplicarRecargo(p.p);
  const precioListaVenta = (p) => aplicarRecargo(p.o);
  const descuentoVenta = (p) => {
    const lista = precioListaVenta(p);
    const venta = precioVenta(p);
    return lista && venta && lista > venta ? Math.round((1 - venta / lista) * 100) : 0;
  };

  // ------------------- Meta Pixel -------------------
  // Eventos de intención para públicos de remarketing. Si el pixel no carga
  // (bloqueador de anuncios), la tienda funciona igual.
  function medir(evento, params) {
    if (typeof window.fbq === 'function') window.fbq('track', evento, params);
  }

  function medirProducto(evento, p) {
    medir(evento, {
      content_type: 'product',
      content_ids: [String(p.i)],
      content_name: p.n,
      currency: 'PYG',
      value: conPrecio(p) ? precioVenta(p) : 0
    });
  }

  const totalCanasta = () => estado.canasta
    .reduce((acc, l) => acc + (precioVenta(productoDeLinea(l)) ?? 0) * l.q, 0);

  let temporizadorToast = null;
  function toast(mensaje) {
    const el = $('#toast');
    el.textContent = mensaje;
    el.classList.add('visible');
    clearTimeout(temporizadorToast);
    temporizadorToast = setTimeout(() => el.classList.remove('visible'), 2600);
  }

  function guardarCanasta() {
    try { localStorage.setItem(CLAVE_CARRITO, JSON.stringify(estado.canasta)); } catch (_) { }
  }

  function cargarCanasta() {
    try {
      const crudo = localStorage.getItem(CLAVE_CARRITO);
      if (!crudo) return;
      const datos = JSON.parse(crudo);
      if (!Array.isArray(datos)) return;
      estado.canasta = datos
        .filter((l) => l && l.id)
        .map((l) => {
          const linea = {
            id: String(l.id),
            q: Math.min(MAX_POR_ITEM, Math.max(1, parseInt(l.q, 10) || 1))
          };
          if (l.snap && l.snap.n) linea.snap = l.snap;
          return linea;
        });
    } catch (_) { estado.canasta = []; }
  }

  /* ------------------------------------------------------------------ */
  /* Carga de datos                                                      */
  /* ------------------------------------------------------------------ */
  async function obtenerJSON(ruta) {
    const resp = await fetch(ruta, { cache: 'no-cache' });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    return resp.json();
  }

  function cargarScript(ruta, variable) {
    return new Promise((resolve, reject) => {
      if (window[variable]) return resolve(window[variable]);
      const s = document.createElement('script');
      s.src = ruta;
      s.onload = () => resolve(window[variable] || null);
      s.onerror = () => reject(new Error(`No se pudo cargar ${ruta}`));
      document.head.appendChild(s);
    });
  }

  async function cargarIndice() {
    try {
      return await obtenerJSON('data/indice.json');
    } catch (_) {
      // Respaldo para abrir con doble clic (file://) o si falta el índice
      const indice = await cargarScript('data/indice.js', 'INDICE_JSON');
      if (!indice) throw new Error('No se pudo cargar el índice del catálogo');
      return indice;
    }
  }

  function coincideVista(producto, vista) {
    if (!vista) return true;
    if (vista.slug === 'todos') return true;
    if (vista.slug === 'ofertas') return !!producto.of;
    const cats = vista.categorias || [];
    if (cats.length && producto.c.some((c) => cats.includes(c))) return true;
    return producto.c.some((c) => c === vista.slug || c.startsWith(`${vista.slug}/`));
  }

  async function asegurarCatalogoCompleto() {
    if (estado.completo) return estado.completo;
    const datos = await cargarScript('data/catalogo.js', 'CATALOGO_JSON');
    if (!datos) throw new Error('No se pudo cargar el catálogo completo');
    estado.completo = datos;
    return datos;
  }

  async function cargarVista(slug) {
    if (estado.vistas[slug]) return estado.vistas[slug];
    if (estado.cargando && estado.cargando.slug === slug) return estado.cargando.promesa;

    const vista = (estado.indice.vistas || []).find((v) => v.slug === slug);
    const promesa = (async () => {
      try {
        const datos = await obtenerJSON(vista && vista.archivo ? `data/${vista.archivo}` : `data/v/${slug}.json`);
        estado.vistas[slug] = datos;
        return datos;
      } catch (_) {
        const completo = await asegurarCatalogoCompleto();
        const lista = completo.productos.filter((p) => coincideVista(p, vista));
        estado.vistas[slug] = lista;
        return lista;
      }
    })();

    estado.cargando = { slug, promesa };
    try { return await promesa; }
    finally { if (estado.cargando && estado.cargando.slug === slug) estado.cargando = null; }
  }

  /* ------------------------------------------------------------------ */
  /* Arranque                                                            */
  /* ------------------------------------------------------------------ */
  async function iniciar() {
    mostrarCargando('Cargando catálogo…');
    try {
      estado.indice = await cargarIndice();
      cargarCanasta();
      const predeterminada = estado.indice.predeterminada || 'accesorios';
      // Desde la landing: tienda.html?seccion=bicis | ?seccion=motos
      const seccion = new URLSearchParams(location.search).get('seccion');
      if (seccion === 'motos' && (estado.indice.vistas || []).some((v) => v.slug === 'motos')) {
        estado.categoria = 'motos';
      } else if (seccion === 'bicis' && (estado.indice.vistas || []).some((v) => v.slug === 'bicicletas')) {
        estado.categoria = 'bicicletas';
      } else {
        estado.categoria = predeterminada;
      }

      await cargarVista(estado.categoria);
      inicializarInterfaz();
      actualizarContadorCanasta();
      aplicarFiltros(true);
      await abrirDesdeLink();
      if (estado.demo) prepararDemo();
    } catch (err) {
      $('#estado-carga').innerHTML = `
        <p style="font-size:34px;margin:0">⚠️</p>
        <p><strong>No se pudo cargar el catálogo.</strong></p>
        <p class="ayuda">Revisá tu conexión y volvé a intentar. (${esc(err.message)})</p>
        <button class="btn btn--secundario" onclick="location.reload()">Reintentar</button>`;
      console.error(err);
    }
  }

  /** Link directo a un producto: ?p=<id>&v=<vista> (se usa en los anuncios) */
  async function abrirDesdeLink() {
    const params = new URLSearchParams(location.search);
    const pid = params.get('p');
    if (!pid) return;
    const vistaPedida = params.get('v');
    let producto = null;

    if (vistaPedida && (estado.indice.vistas || []).some((v) => v.slug === vistaPedida)) {
      await cargarVista(vistaPedida);
      estado.categoria = vistaPedida;
      renderizarNav();
      aplicarFiltros(true);
      producto = buscarProducto(pid);
    }
    if (!producto) {
      await cargarVista('todos');
      estado.categoria = 'todos';
      renderizarNav();
      aplicarFiltros(true);
      producto = buscarProducto(pid);
    }
    if (producto) {
      document.title = `${producto.n} — ${CONFIG.marca}`;
      abrirProducto(producto.i);
    } else {
      toast('Ese producto ya no está disponible');
    }
  }

  function mostrarCargando(texto) {
    const caja = $('#estado-carga');
    if (caja) {
      caja.classList.remove('oculto');
      caja.innerHTML = `<div class="spinner" aria-hidden="true"></div><p>${esc(texto)}</p>`;
    }
    const sk = $('#skeleton-view');
    if (sk) sk.classList.remove('oculto');
    const grilla = $('#grilla');
    if (grilla) grilla.classList.add('oculto');
  }

  function ocultarCargando() {
    const caja = $('#estado-carga');
    if (caja) caja.classList.add('oculto');
    const sk = $('#skeleton-view');
    if (sk) sk.classList.add('oculto');
    const grilla = $('#grilla');
    if (grilla) grilla.classList.remove('oculto');
  }

  /* ------------------------------------------------------------------ */
  /* Interfaz                                                            */
  /* ------------------------------------------------------------------ */
  function inicializarInterfaz() {
    const meta = estado.indice.meta || {};
    const marcaEl = $('#marca-texto');
    if (marcaEl) {
      marcaEl.innerHTML = `<strong>${esc(CONFIG.marca)}</strong><span class="marca__sub">Capiatá · Central</span>`;
    }
    $('#pie-marca').textContent = CONFIG.marca;
    // El <title> SEO se mantiene estático (definido en index.html); solo se cambia
    // cuando se abre un producto por link directo (?p=...).
    $('#pie-numero').textContent = CONFIG.whatsappVisible || `+${CONFIG.whatsapp}`;
    $('#opcion-envio').textContent = CONFIG.envio.etiqueta;
    $('#opcion-retiro').textContent = CONFIG.retiro.etiqueta;
    $('#tira-texto').textContent = `${(meta.total || 0).toLocaleString('es-PY')} productos · Catálogo actualizado: ${fechaHora(meta.generado) || 'sin fecha'} · Pedidos por WhatsApp`;

    const general = linkWhatsApp('Hola! Quiero hacer una consulta.');
    $('#link-whatsapp-general').href = general;
    $('#pie-whatsapp').href = general;

    // Ubicación del local
    const ubicacion = CONFIG.ubicacion || '';
    ['#link-ubicacion', '#tira-ubicacion', '#pie-ubicacion'].forEach((sel) => {
      const el = $(sel);
      if (!el) return;
      if (ubicacion) el.href = ubicacion;
      else el.classList.add('oculto');
    });

    renderizarNav();

    // Segmentado Bicicletas vs Motos
    $('#modo-segmentado')?.addEventListener('click', (ev) => {
      const btn = ev.target.closest('[data-modo]');
      if (!btn) return;
      cambiarModo(btn.dataset.modo);
      cerrarMenuCategorias();
    });

    $('#categorias').addEventListener('click', (ev) => {
      const modo = ev.target.closest('[data-modo]');
      if (modo) { cambiarModo(modo.dataset.modo); return; }
      const btn = ev.target.closest('[data-cat]');
      if (!btn) return;
      cerrarMenuCategorias();
      btn.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'center' });
      if (btn.dataset.cat === 'motos') {
        const sub = btn.dataset.sub || null;
        if (estado.categoria !== 'motos') cambiarModo('motos', sub);
        else {
          estado.subcategoria = sub;
          estado.mostrados = CONFIG.porPagina;
          aplicarFiltros(true);
          renderizarNav();
        }
        return;
      }
      seleccionarCategoria(btn.dataset.cat);
    });

    $('#subcategorias').addEventListener('click', (ev) => {
      const btn = ev.target.closest('[data-sub]');
      if (!btn) return;
      cerrarMenuCategorias();
      btn.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'center' });
      estado.subcategoria = btn.dataset.sub || null;
      estado.mostrados = CONFIG.porPagina;
      aplicarFiltros(true);
    });

    // Búsquedas sugeridas
    $('#chips-busqueda')?.addEventListener('click', async (ev) => {
      const chip = ev.target.closest('.chip-busqueda');
      if (!chip) return;
      const q = chip.dataset.busqueda || chip.textContent.trim();
      const input = $('#buscador');
      if (input) input.value = q;
      estado.busqueda = q;
      $('#buscador-limpiar').classList.remove('oculto');
      estado.mostrados = CONFIG.porPagina;
      if (!estado.vistas.todos) {
        mostrarCargando('Buscando en catálogo…');
        try { await cargarVista('todos'); } catch (_) { }
      }
      aplicarFiltros(true);
    });

    // Filtros activos interactivos
    $('#filtros-activos')?.addEventListener('click', (ev) => {
      if (ev.target.id === 'btn-limpiar-activos') {
        limpiarFiltros();
        return;
      }
      const btn = ev.target.closest('[data-quitar]');
      if (!btn) return;
      const tipo = btn.dataset.quitar;
      if (tipo === 'busqueda') {
        $('#buscador').value = '';
        estado.busqueda = '';
        $('#buscador-limpiar').classList.add('oculto');
      } else if (tipo === 'subcategoria') {
        estado.subcategoria = null;
      } else if (tipo === 'disponibles') {
        estado.soloDisponibles = false;
        const check = $('#solo-disponibles');
        if (check) check.checked = false;
      }
      estado.mostrados = CONFIG.porPagina;
      aplicarFiltros(true);
    });

    $('#buscador').addEventListener('input', debounce(async (ev) => {
      estado.busqueda = ev.target.value.trim();
      $('#buscador-limpiar').classList.toggle('oculto', !estado.busqueda);
      estado.mostrados = CONFIG.porPagina;
      if (estado.busqueda.length >= 2 && !estado.vistas.todos) {
        mostrarCargando('Buscando en todo el catálogo…');
        try { await cargarVista('todos'); } catch (_) { }
      }
      aplicarFiltros(true);
    }, 260));

    $('#buscador-limpiar').addEventListener('click', () => {
      $('#buscador').value = '';
      estado.busqueda = '';
      $('#buscador-limpiar').classList.add('oculto');
      estado.mostrados = CONFIG.porPagina;
      aplicarFiltros(true);
    });

    $('#orden').addEventListener('change', (ev) => { estado.orden = ev.target.value; aplicarFiltros(true); });
    $('#solo-disponibles').addEventListener('change', (ev) => {
      estado.soloDisponibles = ev.target.checked;
      estado.mostrados = CONFIG.porPagina;
      aplicarFiltros(true);
    });

    $('#btn-mas').addEventListener('click', () => { estado.mostrados += CONFIG.porPagina; renderizarGrilla(); });
    $('#btn-limpiar-filtros').addEventListener('click', limpiarFiltros);
    $('#btn-menu-categorias').addEventListener('click', (ev) => {
      const abierto = $('.cabecera').classList.toggle('menu-abierto');
      ev.currentTarget.setAttribute('aria-expanded', String(abierto));
      if (abierto) $('#categorias').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    });

    $('#btn-carrito').addEventListener('click', () => abrirPanel(true));
    $('#barra-canasta-btn')?.addEventListener('click', () => abrirPanel(true));
    $('#cerrar-carrito').addEventListener('click', () => abrirPanel(false));
    $('#btn-finalizar').addEventListener('click', abrirCheckout);
    $('#btn-vaciar-canasta').addEventListener('click', () => {
      if (!estado.canasta.length) return;
      estado.canasta = [];
      guardarCanasta();
      actualizarContadorCanasta();
      renderizarCanasta();
      aplicarFiltros(false);
      toast('Canasta vaciada');
    });

    // Botón flotante para subir
    window.addEventListener('scroll', () => {
      const btn = $('#btn-subir');
      if (btn) btn.classList.toggle('visible', window.scrollY > 320);
    }, { passive: true });
    $('#btn-subir')?.addEventListener('click', () => {
      window.scrollTo({ top: 0, behavior: 'smooth' });
    });

    $('#cerrar-checkout').addEventListener('click', () => cerrarModal('#modal-checkout'));
    $('#cerrar-producto').addEventListener('click', () => cerrarModal('#modal-producto'));
    $('#velo').addEventListener('click', () => abrirPanel(false));
    $$('.modal').forEach((m) => m.addEventListener('click', (ev) => {
      if (ev.target === m) cerrarModal(`#${m.id}`);
    }));
    document.addEventListener('keydown', (ev) => {
      if (ev.key !== 'Escape') return;
      if ($('#modal-checkout').classList.contains('abierto')) cerrarModal('#modal-checkout');
      else if ($('#modal-producto').classList.contains('abierto')) cerrarModal('#modal-producto');
      else if ($('#panel-carrito').classList.contains('abierto')) abrirPanel(false);
    });

    $('#form-pedido').addEventListener('submit', (ev) => ev.preventDefault());
    $$('input[name="entrega"]').forEach((r) => r.addEventListener('change', actualizarTipoEntrega));
    $('#btn-ubicacion').addEventListener('click', pedirUbicacion);
    $('#btn-enviar-pedido').addEventListener('click', enviarPedido);
    $('#btn-copiar-pedido').addEventListener('click', copiarPedido);

    $('#grilla').addEventListener('click', manejarClicGrilla);
    $('#producto-contenido').addEventListener('click', manejarClicProducto);

    renderizarServicios();
  }

  /* ------------------------------------------------------------------ */
  /* Servicio técnico                                                    */
  /* ------------------------------------------------------------------ */
  function renderizarServicios() {
    const planes = Array.isArray(CONFIG.servicios) ? CONFIG.servicios : [];
    const contenedor = $('#servicio-planes');
    if (!contenedor || !planes.length) return;

    contenedor.innerHTML = planes.map((plan) => `
      <article class="plan">
        <header class="plan__cabecera">
          <h3 class="plan__nombre">Servicio ${esc(plan.nombre)}</h3>
          <p class="plan__precio">${fmt(plan.precio)}</p>
        </header>
        <ul class="plan__lista">
          ${(plan.items || []).map((item) => `<li>${esc(item)}</li>`).join('')}
        </ul>
        <a class="btn btn--wa plan__cta" target="_blank" rel="noopener noreferrer"
           href="${esc(linkWhatsApp(`Hola! Quiero reservar un turno de *Servicio ${plan.nombre}* (${fmt(plan.precio)}). ¿Qué días tienen disponibles?`))}">
          Reservar por WhatsApp
        </a>
      </article>`).join('');

    const nota = $('#servicio-nota');
    if (nota) nota.textContent = CONFIG.serviciosNota || '';
  }

  function debounce(fn, ms) {
    let t = null;
    return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), ms); };
  }

  function vistaActual() {
    return (estado.indice.vistas || []).find((v) => v.slug === estado.categoria) || null;
  }

  function nombreCategoria(slug) {
    if (!slug) return '';
    if (slug.startsWith('kw:')) {
      const mapa = {
        'kw:casco': 'Cascos',
        'kw:cubierta|camara|cámara': 'Cubiertas y Cámaras',
        'kw:luz|faro|reflector': 'Luces y Faros',
        'kw:freno|disco|pastilla': 'Frenos',
        'kw:asiento|sillin|sillín': 'Asientos',
        'kw:cadena|cambio|descarrilador': 'Cadenas y Cambios',
        'kw:pedal': 'Pedales',
        'kw:inflador|bomba': 'Infladores',
        'kw:portabici|porta bici|hangon|rack|gate': 'Portabicicletas',
        'kw:botella|caramañola': 'Caramañolas'
      };
      return mapa[slug] || slug.replace('kw:', '');
    }
    const c = (estado.indice.categorias || []).find((x) => x.slug === slug);
    return c ? c.nombre : slug.split('/').pop().replace(/-/g, ' ');
  }

  /* ------------------------------------------------------------------ */
  /* Navegación: Bicicletas | Motos                                     */
  /* ------------------------------------------------------------------ */
  function cerrarMenuCategorias() {
    const cabecera = $('.cabecera');
    const boton = $('#btn-menu-categorias');
    if (!cabecera || !boton) return;
    cabecera.classList.remove('menu-abierto');
    boton.setAttribute('aria-expanded', 'false');
  }

  function renderizarNav() {
    const indice = estado.indice || {};
    const vistas = indice.vistas || [];
    const categorias = indice.categorias || [];
    const enMotos = estado.categoria === 'motos';
    const motos = vistas.find((v) => v.slug === 'motos');

    // Segmentado principal (Bicis vs Motos)
    const seg = $('#modo-segmentado');
    if (seg) {
      seg.innerHTML = `
        <button class="modo-segmentado__btn ${!enMotos ? 'activo' : ''}" data-modo="bicis" role="tab" aria-selected="${!enMotos}">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="5.5" cy="17.5" r="3.5"/><circle cx="18.5" cy="17.5" r="3.5"/><path d="M15 6a1 1 0 1 0 0-2 1 1 0 0 0 0 2zm-3 11.5L8.5 9h4l2.5 4.5M12 9l3-4h3"/></svg>
          <span class="modo__largo">Bicicletas y Accesorios</span><span class="modo__corto">Bicicletas</span>
        </button>
        <button class="modo-segmentado__btn ${enMotos ? 'activo' : ''}" data-modo="motos" role="tab" aria-selected="${enMotos}">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="5" cy="16" r="3"/><circle cx="19" cy="16" r="3"/><path d="M12 16h-3l2-7h4l2 4h2M14 9l1-3h3M9 12h5"/></svg>
          <span class="modo__largo">Motos y Repuestos</span><span class="modo__corto">Motos</span>
        </button>`;
    }

    let opciones = '';
    if (enMotos && motos) {
      const activo = estado.subcategoria;
      opciones = `<button class="cat-btn" data-cat="motos" data-sub="" aria-pressed="${String(!activo)}">Todas <span class="cat-btn__n">${motos.total.toLocaleString('es-PY')}</span></button>`;
      opciones += (motos.subcategorias || []).map((slug) => {
        const c = categorias.find((x) => x.slug === slug);
        const activoSub = activo === slug;
        return `<button class="cat-btn" data-cat="motos" data-sub="${esc(slug)}" aria-pressed="${String(activoSub)}">${esc(c ? c.nombre : slug)}${c ? ` <span class="cat-btn__n">${c.total.toLocaleString('es-PY')}</span>` : ''}</button>`;
      }).join('');
    } else {
      opciones = vistas.filter((v) => v.slug !== 'motos').map((v) => `
        <button class="cat-btn ${v.slug === 'ofertas' ? 'cat-btn--oferta' : ''}"
                data-cat="${v.slug}" aria-pressed="${String(v.slug === estado.categoria)}">
          ${v.slug === 'ofertas' ? '🔥 ' : ''}${esc(v.nombre)}${v.slug !== 'todos' ? ` <span class="cat-btn__n">${v.total.toLocaleString('es-PY')}</span>` : ''}
        </button>`).join('');
    }

    const catEl = $('#categorias');
    if (catEl) catEl.innerHTML = opciones;
  }

  async function cambiarModo(modo, subcategoria = null) {
    // 'bicis' -> vista 'bicicletas', 'motos' -> vista 'motos'
    estado.categoria = modo === 'motos' ? 'motos' : 'bicicletas';
    estado.subcategoria = modo === 'motos' ? subcategoria : null;
    estado.busqueda = '';
    estado.mostrados = CONFIG.porPagina;
    const buscador = $('#buscador');
    if (buscador) buscador.value = '';
    $('#buscador-limpiar').classList.add('oculto');
    if (!estado.vistas[estado.categoria]) {
      mostrarCargando('Cargando catálogo…');
      $('#grilla').innerHTML = '';
    }
    try { await cargarVista(estado.categoria); } catch (_) { }
    renderizarNav();
    aplicarFiltros(true);
  }

  async function seleccionarCategoria(slug) {
    if (slug === estado.categoria) return;
    const token = ++estado.tokenCarga;
    estado.categoria = slug;
    estado.subcategoria = null;
    estado.busqueda = '';
    estado.mostrados = CONFIG.porPagina;
    $('#buscador').value = '';
    $('#buscador-limpiar').classList.add('oculto');
    $$('#categorias [data-cat]').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.cat === slug)));

    if (!estado.vistas[slug]) {
      mostrarCargando(`Cargando ${vistaActual() ? vistaActual().nombre : slug}…`);
      $('#grilla').innerHTML = '';
    }
    try { await cargarVista(slug); } catch (_) { }
    if (token !== estado.tokenCarga) return;
    renderizarNav();
    aplicarFiltros(true);
  }

  function limpiarFiltros() {
    estado.busqueda = '';
    estado.subcategoria = null;
    estado.orden = 'relevancia';
    estado.soloDisponibles = false;
    estado.mostrados = CONFIG.porPagina;
    $('#buscador').value = '';
    $('#buscador-limpiar').classList.add('oculto');
    $('#orden').value = 'relevancia';
    $('#solo-disponibles').checked = false;
    const predeterminada = (estado.indice.vistas || [])[0]?.slug || 'accesorios';
    seleccionarCategoria(predeterminada);
  }

  /* ------------------------------------------------------------------ */
  /* Filtros y render                                                    */
  /* ------------------------------------------------------------------ */
  function productosBase() {
    const vista = vistaActual();
    if (estado.busqueda.length >= 2) {
      // Motos: busca dentro del catálogo de motos (no en el de bicicletas)
      if (vista && vista.motos) return estado.vistas[estado.categoria] || [];
      return estado.vistas.todos || estado.vistas[estado.categoria] || [];
    }
    return estado.vistas[estado.categoria] || [];
  }

  function coincideBusqueda(p, tokens) {
    if (!tokens.length) return true;
    const texto = normalizar(`${p.n} ${p.m} ${p.s || ''} ${p.c.join(' ')}`);
    return tokens.every((t) => texto.includes(t));
  }

  function filtrar() {
    const tokens = normalizar(estado.busqueda).split(/\s+/).filter(Boolean);
    let lista = productosBase();
    if (tokens.length) lista = lista.filter((p) => coincideBusqueda(p, tokens));
    if (estado.subcategoria) {
      if (estado.subcategoria.startsWith('kw:')) {
        const rx = new RegExp(estado.subcategoria.slice(3), 'i');
        lista = lista.filter((p) => rx.test(p.n));
      } else {
        lista = lista.filter((p) => p.c.includes(estado.subcategoria));
      }
    }
    if (estado.soloDisponibles) lista = lista.filter((p) => p.e !== 1);
    return lista;
  }

  function ordenar(lista) {
    const copia = lista.slice();
    const descuento = (p) => descuentoVenta(p) / 100;
    const pilarDe = (p) => p.c.find((c) => !c.includes('/')) || p.c[0] || '';
    const ORDEN_PILAR = { bicicletas: 0, fitness: 1, indumentaria: 2, autoaccesorios: 3 };
    const CLAVES_TIPO = {
      bicicletas: ['BICICLETA', 'CUADRO'],
      accesorios: ['BICICLETA'],
      fitness: ['CINTA', 'ELIPTICA', 'SPINNING', 'BICICLETA', 'REMOS', 'ESCALADORA',
        'MULTIGIMNASIO', 'ABDOMINALERA', 'MANCUERNA', 'PESO LIBRE', 'BANCO']
    };
    const peso = (p) => {
      const cat = estado.busqueda ? '' : estado.categoria;
      let base = 0;
      if (cat === 'todos') base = (ORDEN_PILAR[pilarDe(p)] ?? 4) * 10;
      const claves = CLAVES_TIPO[cat];
      if (claves) {
        const nombre = normalizar(p.n);
        if (!claves.some((k) => nombre.includes(normalizar(k)))) base += 3;
      }
      if (!conPrecio(p)) base += 6;
      else if (sinStock(p)) base += 2;
      return base;
    };

    switch (estado.orden) {
      case 'precio-asc': return copia.sort((a, b) => (precioVenta(a) ?? Infinity) - (precioVenta(b) ?? Infinity));
      case 'precio-desc': return copia.sort((a, b) => (precioVenta(b) ?? -1) - (precioVenta(a) ?? -1));
      case 'descuento': return copia.sort((a, b) => descuento(b) - descuento(a));
      case 'nombre': return copia.sort((a, b) => a.n.localeCompare(b.n, 'es'));
      default:
        return copia.sort((a, b) =>
          peso(a) - peso(b) || descuento(b) - descuento(a) || (precioVenta(b) ?? 0) - (precioVenta(a) ?? 0));
    }
  }

  function aplicarFiltros(reset) {
    const lista = ordenar(filtrar());
    estado.resultados = lista;
    if (reset) {
      estado.mostrados = CONFIG.porPagina;
    }
    actualizarTitulo(lista.length);
    actualizarSubcategorias();
    actualizarFiltrosActivos();
    renderizarGrilla();
    refrescarSnapshots();
  }

  function actualizarTitulo(total) {
    const vista = vistaActual();
    let titulo;
    if (estado.busqueda.length >= 2) titulo = 'Resultados de búsqueda';
    else if (vista) titulo = vista.nombre;
    else titulo = 'Catálogo';

    $('#titulo-seccion').textContent = titulo;
    const partes = [`${total.toLocaleString('es-PY')} productos`];
    const hayFiltros = !!(estado.subcategoria || estado.soloDisponibles || estado.busqueda);
    if (vista && !estado.busqueda && hayFiltros) {
      partes[0] = `${total.toLocaleString('es-PY')} de ${vista.total.toLocaleString('es-PY')} productos`;
    }
    if (estado.busqueda) partes.push(`para “${estado.busqueda}”`);
    if (estado.subcategoria) partes.push(nombreCategoria(estado.subcategoria));
    if (estado.soloDisponibles) partes.push('solo con stock');
    $('#subtitulo-seccion').textContent = partes.join(' · ');
  }

  function actualizarFiltrosActivos() {
    const cont = $('#filtros-activos');
    if (!cont) return;
    const chips = [];
    if (estado.busqueda) {
      chips.push(`
        <span class="filtro-tag">
          <span>Búsqueda: <strong>“${esc(estado.busqueda)}”</strong></span>
          <button class="filtro-tag__quitar" data-quitar="busqueda" aria-label="Quitar filtro de búsqueda">×</button>
        </span>`);
    }
    if (estado.subcategoria) {
      chips.push(`
        <span class="filtro-tag">
          <span>Subcategoría: <strong>${esc(nombreCategoria(estado.subcategoria))}</strong></span>
          <button class="filtro-tag__quitar" data-quitar="subcategoria" aria-label="Quitar subcategoría">×</button>
        </span>`);
    }
    if (estado.soloDisponibles) {
      chips.push(`
        <span class="filtro-tag">
          <span>Solo con stock</span>
          <button class="filtro-tag__quitar" data-quitar="disponibles" aria-label="Quitar filtro de solo disponibles">×</button>
        </span>`);
    }

    if (chips.length > 0) {
      cont.classList.add('visible');
      cont.innerHTML = `
        <span class="filtros-activos__etiqueta">
          <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M22 3H2l8 9.46V19l4 2v-8.54L22 3z"/></svg>
          Filtros:
        </span>
        ${chips.join('')}
        <button class="filtros-activos__limpiar" id="btn-limpiar-activos" type="button">Limpiar todos</button>`;
    } else {
      cont.classList.remove('visible');
      cont.innerHTML = '';
    }
  }

  const ACCESORIOS_SUBCATS = [
    { slug: 'kw:casco', nombre: 'Cascos' },
    { slug: 'kw:cubierta|camara|cámara', nombre: 'Cubiertas y Cámaras' },
    { slug: 'kw:luz|faro|reflector', nombre: 'Luces' },
    { slug: 'kw:freno|disco|pastilla', nombre: 'Frenos' },
    { slug: 'kw:asiento|sillin|sillín', nombre: 'Asientos' },
    { slug: 'kw:cadena|cambio|descarrilador', nombre: 'Cadenas y Cambios' },
    { slug: 'kw:pedal', nombre: 'Pedales' },
    { slug: 'kw:inflador|bomba', nombre: 'Infladores' },
    { slug: 'kw:portabici|porta bici|hangon|rack|gate', nombre: 'Portabicicletas' },
    { slug: 'kw:botella|caramañola', nombre: 'Caramañolas' },
  ];

  function actualizarSubcategorias() {
    const cont = $('#subcategorias');
    if (!cont) return;
    const vista = vistaActual();
    if (estado.categoria === 'motos') {
      cont.classList.remove('visible');
      cont.innerHTML = '';
      return;
    }

    let items = [];
    if (estado.categoria === 'accesorios') {
      const prods = estado.vistas.accesorios || [];
      items = ACCESORIOS_SUBCATS.map((sub) => {
        const rx = new RegExp(sub.slug.slice(3), 'i');
        const count = prods.filter((p) => rx.test(p.n)).length;
        return { slug: sub.slug, nombre: sub.nombre, total: count };
      }).filter((x) => x.total > 0);
    } else {
      const hijas = (vista && vista.subcategorias) ? vista.subcategorias : [];
      if (hijas.length <= 1) {
        cont.classList.remove('visible');
        cont.innerHTML = '';
        return;
      }
      items = hijas.map((slug) => {
        const c = (estado.indice.categorias || []).find((x) => x.slug === slug);
        return {
          slug,
          nombre: c ? c.nombre : slug.split('/').pop().replace(/-/g, ' '),
          total: c ? c.total : ''
        };
      });
    }

    if (items.length <= 0) {
      cont.classList.remove('visible');
      cont.innerHTML = '';
      return;
    }

    cont.classList.add('visible');
    cont.innerHTML = `
      <button class="sub-btn" data-sub="" aria-pressed="${String(estado.subcategoria === null)}">Todas</button>
      ${items.map((sub) => `
        <button class="sub-btn" data-sub="${esc(sub.slug)}" aria-pressed="${String(estado.subcategoria === sub.slug)}">
          ${esc(sub.nombre)}${sub.total ? ` <span class="n">${sub.total}</span>` : ''}
        </button>
      `).join('')}`;
  }

  function renderizarGrilla() {
    const lista = estado.resultados || [];
    const visibles = lista.slice(0, estado.mostrados);
    ocultarCargando();

    const grilla = $('#grilla');
    const masContenedor = $('#mas-contenedor');

    $('#vacio').classList.toggle('oculto', lista.length > 0);

    // Modo "ver más"
    grilla.innerHTML = visibles.map(tarjetaHTML).join('');
    masContenedor.classList.toggle('oculto', visibles.length >= lista.length);
    const restantes = Math.max(0, lista.length - visibles.length);
    $('#btn-mas').textContent = `Ver más productos (${Math.min(CONFIG.porPagina, restantes)})`;

    // Progreso
    const progresoTexto = $('#progreso-texto');
    const progresoRelleno = $('#barra-progreso-relleno');
    if (progresoTexto && progresoRelleno) {
      progresoTexto.innerHTML = `Mostrando <strong>${visibles.length}</strong> de <strong>${lista.length.toLocaleString('es-PY')}</strong> productos`;
      const pct = Math.min(100, Math.round((visibles.length / Math.max(1, lista.length)) * 100));
      progresoRelleno.style.width = `${pct}%`;
    }
  }

  function tarjetaHTML(p) {
    const est = ESTADOS[p.e] || ESTADOS[3];
    const enCanasta = lineaDe(p.i);
    const desc = descuentoVenta(p);
    const img = esc(urlImagen(p));
    const acciones = conPrecio(p)
      ? (enCanasta
        ? `<div class="stepper" data-id="${esc(p.i)}">
             <button data-accion="restar" aria-label="Quitar uno">−</button>
             <span>${enCanasta.q}</span>
             <button data-accion="sumar" aria-label="Agregar uno">+</button>
           </div>`
        : `<button class="card__btn" data-accion="agregar"><span class="largo">Agregar a la canasta</span><span class="corto">Agregar</span></button>`)
      : `<button class="card__btn card__btn--consultar" data-accion="consultar">Consultar precio</button>`;

    return `
      <article class="card ${enCanasta ? 'card--en-canasta' : ''}" data-id="${esc(p.i)}">
        ${enCanasta ? `<span class="card__badge-canasta" aria-label="En tu canasta">✓ En canasta (${enCanasta.q})</span>` : ''}
        <div class="card__foto" data-accion="ver">
          <img src="${img}" alt="${esc(p.n)}${p.m ? ' — ' + esc(p.m) : ''} · Jaka Bicicletería, Capiatá" loading="lazy" decoding="async" width="300" height="300" onerror="this.onerror=null;this.src='${PLACEHOLDER}'">
          ${CONFIG.mostrarDescuento && desc >= 5 ? `<span class="card__off">-${desc}%</span>` : ''}
          ${p.e === 1
            ? '<span class="card__estado card__estado--agotado">Sin stock</span>'
            : (p.sc
              ? '<span class="card__estado card__estado--consultar">Stock a confirmar</span>'
              : (conPrecio(p) ? '<span class="card__estado">✓ En stock</span>' : `<span class="card__estado card__estado--consultar">${est.texto}</span>`))}
        </div>
        <div class="card__info">
          <span class="card__marca">${esc(p.m) || '&nbsp;'}</span>
          <h3 class="card__nombre" data-accion="ver" title="${esc(p.n)}">${esc(p.n)}</h3>
          <div class="card__precios">
            ${CONFIG.mostrarPrecioAnterior && p.o && p.p ? `<span class="card__antes">${fmt(precioListaVenta(p))}</span>` : ''}
            ${conPrecio(p) ? `<span class="card__ahora">${fmt(precioVenta(p))}</span>` : '<span class="card__sinprecio">Precio a consultar</span>'}
          </div>
          <div class="card__acciones">
            ${acciones}
            <button class="card__btn card__btn--wa" data-accion="consultar" aria-label="Consultar por WhatsApp" title="Consultar por WhatsApp">
              <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 2a10 10 0 0 0-8.6 15L2 22l5.2-1.4A10 10 0 1 0 12 2Z" fill="none" stroke="currentColor" stroke-width="1.8"/><path d="M8.5 8.7c.3-.7.6-.7.9-.7h.7c.2 0 .5 0 .7.6s.7 1.7.8 1.8c0 .2.1.3 0 .5l-.4.6c-.1.2-.3.4-.1.7.2.3.7 1.1 1.5 1.8 1 .9 1.8 1.1 2 1.2.2.1.4.1.6-.1l.7-.8c.2-.2.4-.2.6-.1l1.6.8c.2.1.4.2.4.3.1.2.1.8-.2 1.5-.3.7-1.6 1.4-2.2 1.4-.6 0-2.4-.2-4.5-2.2-1.7-1.6-2.6-3.3-2.9-3.9-.3-.6-1-1.9-.7-3Z" fill="currentColor"/></svg>
            </button>
          </div>
        </div>
      </article>`;
  }

  function manejarClicGrilla(ev) {
    const accionEl = ev.target.closest('[data-accion]');
    if (!accionEl) return;
    const card = ev.target.closest('.card');
    if (!card) return;
    const id = card.dataset.id;
    const accion = accionEl.dataset.accion;
    const producto = buscarProducto(id);
    if (!producto) return;
    if (accion === 'ver') return abrirProducto(id);
    if (accion === 'consultar') return consultarProducto(producto);
    if (accion === 'agregar' || accion === 'sumar') return agregar(id, 1);
    if (accion === 'restar') return agregar(id, -1);
  }

  function buscarProducto(id) {
    for (const clave in estado.vistas) {
      const encontrado = estado.vistas[clave].find((p) => String(p.i) === String(id));
      if (encontrado) return encontrado;
    }
    if (estado.completo) return estado.completo.productos.find((p) => String(p.i) === String(id));
    return null;
  }

  /* Guardamos una copia mínima del producto en la canasta para que no se pierda
     al recargar o cambiar de sección (aunque su vista no esté cargada). */
  const CAMPOS_SNAPSHOT = ['i', 'n', 'm', 'c', 'p', 'o', 'e', 'img', 'ch', 'sc', 's', 'of'];
  function snapshotProducto(p) {
    const copia = {};
    CAMPOS_SNAPSHOT.forEach((k) => { if (p[k] !== undefined) copia[k] = p[k]; });
    return copia;
  }
  function productoDeLinea(linea) {
    const vivo = buscarProducto(linea.id);
    if (vivo) {
      linea.snap = snapshotProducto(vivo);
      return vivo;
    }
    return (linea.snap && linea.snap.n) ? linea.snap : null;
  }
  function refrescarSnapshots() {
    let cambio = false;
    estado.canasta.forEach((l) => {
      if (!l.snap || !l.snap.n) {
        const p = buscarProducto(l.id);
        if (p) { l.snap = snapshotProducto(p); cambio = true; }
      }
    });
    if (cambio) guardarCanasta();
  }
  async function asegurarProductosCarrito() {
    const pendientes = () => estado.canasta.filter((l) => !buscarProducto(l.id) && !(l.snap && l.snap.n));
    if (!pendientes().length) return;
    try { await cargarVista('todos'); } catch (_) { }
    if (pendientes().length && (estado.indice.vistas || []).some((v) => v.slug === 'motos')) {
      try { await cargarVista('motos'); } catch (_) { }
    }
    refrescarSnapshots();
    actualizarContadorCanasta();
    if ($('#panel-carrito')?.classList.contains('abierto')) renderizarCanasta();
  }

  /* ------------------------------------------------------------------ */
  /* Canasta                                                             */
  /* ------------------------------------------------------------------ */
  function lineaDe(id) {
    return estado.canasta.find((l) => String(l.id) === String(id));
  }

  function agregar(id, delta) {
    const producto = buscarProducto(id);
    if (!producto) return;
    if (!conPrecio(producto)) { consultarProducto(producto); return; }
    if (delta > 0) medirProducto('AddToCart', producto);
    const linea = lineaDe(id);
    const snap = snapshotProducto(producto);
    if (linea) {
      linea.q = Math.min(MAX_POR_ITEM, Math.max(0, linea.q + delta));
      linea.snap = snap;
      if (linea.q === 0) estado.canasta = estado.canasta.filter((l) => l !== linea);
    } else if (delta > 0) {
      estado.canasta.push({ id: String(id), q: 1, snap });
      toast('✓ Agregado a la canasta');
    }
    guardarCanasta();
    actualizarContadorCanasta();
    actualizarTarjeta(id);
    if ($('#panel-carrito').classList.contains('abierto')) renderizarCanasta();
    if ($('#modal-checkout').classList.contains('abierto')) renderizarCheckout();
    if ($('#modal-producto').classList.contains('abierto')) renderizarBotonProducto(id);
  }

  function actualizarTarjeta(id) {
    const card = $(`.card[data-id="${CSS.escape(String(id))}"]`);
    if (!card) return;
    const producto = buscarProducto(id);
    const cont = $('.card__acciones', card);
    const linea = lineaDe(id);
    if (!cont || !producto) return;

    card.classList.toggle('card--en-canasta', !!linea);
    let badge = $('.card__badge-canasta', card);
    if (linea) {
      if (!badge) {
        badge = document.createElement('span');
        badge.className = 'card__badge-canasta';
        badge.setAttribute('aria-label', 'En tu canasta');
        card.insertBefore(badge, card.firstChild);
      }
      badge.textContent = `✓ En canasta (${linea.q})`;
    } else if (badge) {
      badge.remove();
    }

    const waBtn = cont.querySelector('.card__btn--wa');
    const nuevo = document.createElement('div');
    nuevo.innerHTML = linea
      ? `<div class="stepper" data-id="${esc(producto.i)}">
           <button data-accion="restar" aria-label="Quitar uno">−</button>
           <span>${linea.q}</span>
           <button data-accion="sumar" aria-label="Agregar uno">+</button>
         </div>`
      : `<button class="card__btn" data-accion="agregar"><span class="largo">Agregar a la canasta</span><span class="corto">Agregar</span></button>`;
    cont.replaceChild(nuevo.firstElementChild, cont.firstElementChild);
    if (waBtn) cont.appendChild(waBtn);
  }

  function actualizarContadorCanasta() {
    const total = estado.canasta.reduce((acc, l) => acc + l.q, 0);
    const el = $('#carrito-contador');
    if (el) {
      el.textContent = total;
      el.style.background = total > 0 ? 'var(--verde)' : '#94a3b8';
    }

    const barraMovil = $('#barra-canasta-movil');
    if (barraMovil) {
      if (total > 0) {
        barraMovil.classList.add('visible');
        const cantEl = $('#barra-canasta-cant');
        const montoEl = $('#barra-canasta-monto');
        if (cantEl) cantEl.textContent = `${total} ${total === 1 ? 'producto' : 'productos'}`;
        if (montoEl) montoEl.textContent = fmt(totalCanasta());
      } else {
        barraMovil.classList.remove('visible');
      }
    }
  }

  function renderizarCanasta() {
    const cont = $('#carrito-lineas');
    if (!estado.canasta.length) {
      cont.innerHTML = `
        <div class="carrito-vacio">
          <p class="carrito-vacio__emoji">🧺</p>
          <p>Tu canasta está vacía.</p>
          <button class="btn btn--secundario" id="btn-seguir-comprando">Ver productos</button>
        </div>`;
      $('#btn-seguir-comprando')?.addEventListener('click', () => abrirPanel(false));
      $('#carrito-subtotal').textContent = fmt(0);
      $('#carrito-total').textContent = fmt(0);
      return;
    }

    cont.innerHTML = estado.canasta.map((linea) => {
      const p = productoDeLinea(linea);
      if (!p) {
        return `<div class="linea linea--pendiente" data-linea="${esc(linea.id)}">
          <div class="linea__foto"></div>
          <div class="linea__info">
            <p class="linea__nombre">Producto no disponible</p>
            <span class="linea__precio">—</span>
            <div class="linea__fila"><button class="linea__quitar" data-quitar="${esc(linea.id)}">Quitar</button></div>
          </div>
        </div>`;
      }
      const desc = descuentoVenta(p);
      return `
        <div class="linea" data-linea="${esc(p.i)}">
          <div class="linea__foto"><img src="${esc(urlImagen(p))}" alt="" loading="lazy" onerror="this.onerror=null;this.src='${PLACEHOLDER}'"></div>
          <div class="linea__info">
            <p class="linea__nombre">${esc(p.n)}</p>
            <span class="linea__precio">${fmt(precioVenta(p))}${CONFIG.mostrarPrecioAnterior && p.o ? ` <span class="linea__antes">${fmt(precioListaVenta(p))}</span>` : ''}</span>
            ${CONFIG.mostrarDescuento && desc >= 5 ? `<span class="linea__aviso">-${desc}% de descuento</span>` : ''}
            ${p.e === 1 ? '<span class="linea__aviso">Sin stock — te confirmamos</span>' : ''}
            <div class="linea__fila">
              <div class="stepper" data-id="${esc(p.i)}">
                <button data-accion="restar" aria-label="Quitar uno">−</button>
                <span>${linea.q}</span>
                <button data-accion="sumar" aria-label="Agregar uno">+</button>
              </div>
              <button class="linea__quitar" data-quitar="${esc(p.i)}">Quitar</button>
            </div>
          </div>
        </div>`;
    }).join('');

    const subtotal = estado.canasta.reduce((acc, l) => {
      const p = productoDeLinea(l);
      const precio = p ? precioVenta(p) : null;
      return acc + (precio ? precio * l.q : 0);
    }, 0);
    $('#carrito-subtotal').textContent = fmt(subtotal);
    $('#carrito-total').textContent = fmt(subtotal);
    $('#carrito-envio').textContent = 'a coordinar';
    refrescarSnapshots();

    cont.querySelectorAll('.stepper').forEach((st) => {
      const id = st.dataset.id;
      st.addEventListener('click', (ev) => {
        const b = ev.target.closest('[data-accion]');
        if (!b) return;
        agregar(id, b.dataset.accion === 'sumar' ? 1 : -1);
      });
    });
    cont.querySelectorAll('[data-quitar]').forEach((b) => {
      b.addEventListener('click', () => {
        estado.canasta = estado.canasta.filter((l) => String(l.id) !== String(b.dataset.quitar));
        guardarCanasta();
        actualizarContadorCanasta();
        renderizarCanasta();
        actualizarTarjeta(b.dataset.quitar);
        if ($('#modal-checkout').classList.contains('abierto')) renderizarCheckout();
      });
    });
  }

  function abrirPanel(abrir) {
    const panel = $('#panel-carrito');
    const velo = $('#velo');
    if (abrir) {
      renderizarCanasta();
      asegurarProductosCarrito();
      panel.classList.add('abierto');
      panel.setAttribute('aria-hidden', 'false');
      velo.hidden = false;
      document.body.classList.add('sin-scroll');
    } else {
      panel.classList.remove('abierto');
      panel.setAttribute('aria-hidden', 'true');
      velo.hidden = true;
      document.body.classList.remove('sin-scroll');
    }
  }

  /* ------------------------------------------------------------------ */
  /* Checkout                                                            */
  /* ------------------------------------------------------------------ */
  async function abrirCheckout() {
    if (!estado.canasta.length) { toast('Tu canasta está vacía'); return; }
    await asegurarProductosCarrito();
    medir('InitiateCheckout', {
      content_type: 'product',
      content_ids: estado.canasta.map((l) => String(l.id)),
      num_items: estado.canasta.reduce((acc, l) => acc + l.q, 0),
      currency: 'PYG',
      value: totalCanasta()
    });
    abrirPanel(false);
    renderizarCheckout();
    actualizarTipoEntrega();
    const modal = $('#modal-checkout');
    modal.classList.add('abierto');
    modal.setAttribute('aria-hidden', 'false');
    document.body.classList.add('sin-scroll');
    // Focus trap
    setTimeout(() => activarFocusTrap(modal), 120);
    setTimeout(() => $('#nombre').focus(), 200);
  }

  function cerrarModal(sel) {
    const modal = $(sel);
    modal.classList.remove('abierto');
    modal.setAttribute('aria-hidden', 'true');
    desactivarFocusTrap(modal);
    if (!$$('.modal.abierto').length && !$('#panel-carrito').classList.contains('abierto')) {
      document.body.classList.remove('sin-scroll');
    }
  }

  /* ------------------------------------------------------------------ */
  /* Focus trap para modales (accesibilidad)                           */
  /* ------------------------------------------------------------------ */
  function activarFocusTrap(modal) {
    if (!modal) return;
    modal.dataset.focusTrapped = 'true';
    // Guardar el elemento que tenía foco
    const trigger = modal.closest('[data-trigger], [aria-controls]')?.closest('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])');
    if (trigger) {
      modal.dataset.previousFocus = trigger.id || 'trigger-' + Math.random().toString(36).substr(2, 9);
    }
  }

  function desactivarFocusTrap(modal) {
    if (!modal) return;
    delete modal.dataset.focusTrapped;
    const previousId = modal.dataset.previousFocus;
    if (previousId) {
      const prev = document.getElementById(previousId.replace('trigger-', ''));
      prev?.focus();
    }
  }

  /* ------------------------------------------------------------------ */
  /* Keyboard navigation para focus trap                                */
  /* ------------------------------------------------------------------ */
  document.addEventListener('keydown', function(ev) {
    if (ev.key === 'Tab') {
      // Detectar tab en modal abierto
      const modalAbierto = $('.modal.abierto');
      if (!modalAbierto) return;

      const focusable = modalAbierto.querySelectorAll('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])');
      if (focusable.length === 0) return;

      const primerElemento = focusable[0];
      const ultimoElemento = focusable[focusable.length - 1];

      if (ev.shiftKey) {
        // Shift + Tab
        if (document.activeElement === primerElemento) {
          ev.preventDefault();
          primerElemento.focus();
        }
      } else {
        // Tab normal
        if (document.activeElement === ultimoElemento) {
          ev.preventDefault();
          ultimoElemento.focus();
        }
      }
    }
  });

  function renderizarCheckout() {
    const cont = $('#checkout-lineas');
    if (!estado.canasta.length) {
      cont.innerHTML = '<p class="ayuda">Tu canasta está vacía.</p>';
      $('#checkout-total').textContent = fmt(0);
      return;
    }
    cont.innerHTML = estado.canasta.map((l) => {
      const p = productoDeLinea(l);
      if (!p) return '';
      return `<div class="resumen__linea">
        <span>${l.q} × ${esc(p.n)}</span>
        <span>${fmt((precioVenta(p) || 0) * l.q)}</span>
      </div>`;
    }).join('');
    const total = estado.canasta.reduce((acc, l) => {
      const p = productoDeLinea(l);
      const precio = p ? precioVenta(p) : null;
      return acc + (precio ? precio * l.q : 0);
    }, 0);
    $('#checkout-total').textContent = fmt(total);
    $('#checkout-nota').textContent = CONFIG.envio.nota || '';
  }

  function actualizarTipoEntrega() {
    const tipo = $('input[name="entrega"]:checked')?.value || 'envio';
    const esEnvio = tipo === 'envio';
    $('#bloque-envio').classList.toggle('oculto', !esEnvio);
    $('#checkout-nota').textContent = esEnvio ? (CONFIG.envio.nota || '') : (CONFIG.retiro.nota || '');
    if (!esEnvio) {
      $('#direccion').value = '';
      $('#referencia').value = '';
      limpiarError('direccion');
    }
    if (!CONFIG.retiro.habilitado) {
      $('input[name="entrega"][value="retiro"]').closest('.opcion').classList.add('oculto');
    }
  }

  function limpiarError(nombre) {
    const campo = $(`#${nombre}`)?.closest('.campo');
    if (campo) campo.classList.remove('invalido');
    const err = $(`[data-error="${nombre}"]`);
    if (err) err.textContent = '';
  }

  function marcarError(nombre, mensaje) {
    const campo = $(`#${nombre}`)?.closest('.campo');
    if (campo) campo.classList.add('invalido');
    const err = $(`[data-error="${nombre}"]`);
    if (err) err.textContent = mensaje;
  }

  function validarFormulario() {
    let ok = true;
    ['nombre', 'telefono', 'direccion'].forEach(limpiarError);
    const nombre = $('#nombre').value.trim();
    const telefono = $('#telefono').value.trim();
    const tipo = $('input[name="entrega"]:checked')?.value || 'envio';
    const direccion = $('#direccion').value.trim();
    if (nombre.length < 3) { marcarError('nombre', 'Ingresá tu nombre y apellido.'); ok = false; }
    if (telefono.replace(/\D/g, '').length < 6) { marcarError('telefono', 'Ingresá un teléfono válido.'); ok = false; }
    if (tipo === 'envio' && direccion.length < 6) { marcarError('direccion', 'Necesitamos la dirección para entregar.'); ok = false; }
    return ok;
  }

  function datosPedido() {
    const tipo = $('input[name="entrega"]:checked')?.value || 'envio';
    return {
      nombre: $('#nombre').value.trim(),
      telefono: $('#telefono').value.trim(),
      tipo,
      direccion: $('#direccion').value.trim(),
      referencia: $('#referencia').value.trim(),
      notas: $('#notas').value.trim(),
      ubicacion: estado.ubicacion
    };
  }

  function construirMensaje() {
    const datos = datosPedido();
    const ahora = new Date();
    const dos = (n) => String(n).padStart(2, '0');
    const fecha = `${dos(ahora.getDate())}/${dos(ahora.getMonth() + 1)}/${ahora.getFullYear()} ${dos(ahora.getHours())}:${dos(ahora.getMinutes())}`;
    const lineas = [];
    let total = 0;
    let n = 0;

    estado.canasta.forEach((l) => {
      const p = productoDeLinea(l);
      if (!p) return;
      n += 1;
      const precio = precioVenta(p) || 0;
      const sub = precio * l.q;
      total += sub;
      const sinStockTxt = p.e === 1 ? ' ⚠️ SIN STOCK (confirmar)' : '';
      lineas.push(`${n}. ${p.n}${sinStockTxt}\n    ${l.q} x ${fmt(precio)} = ${fmt(sub)}`);
    });

    const partes = [
      `🛒 *NUEVO PEDIDO — ${CONFIG.marca}*`,
      `Fecha: ${fecha}`,
      '',
      '*Productos:*',
      ...lineas,
      '',
      `*Total productos: ${fmt(total)}*`,
      datos.tipo === 'envio' ? 'Envío: a coordinar (no incluido en el total)' : 'Entrega: retiro en local',
      '',
      '*Datos de entrega:*',
      `Nombre: ${datos.nombre}`,
      `Teléfono: ${datos.telefono}`,
      `Tipo: ${datos.tipo === 'envio' ? CONFIG.envio.etiqueta : CONFIG.retiro.etiqueta}`
    ];

    if (datos.tipo === 'envio') {
      if (datos.direccion) partes.push(`Dirección: ${datos.direccion}`);
      if (datos.referencia) partes.push(`Referencia: ${datos.referencia}`);
      if (datos.ubicacion) partes.push(`Ubicación: https://www.google.com/maps?q=${datos.ubicacion.lat},${datos.ubicacion.lng}`);
    }
    if (datos.notas) partes.push(`Notas: ${datos.notas}`);
    partes.push('', `Precios según catálogo actualizado el ${fechaHora(estado.indice?.meta?.generado) || '—'}.`);
    partes.push('Pedido generado desde la web.');
    return partes.join('\n');
  }

  function linkWhatsApp(texto, numero = CONFIG.whatsapp) {
    return `https://wa.me/${String(numero).replace(/\D/g, '')}?text=${encodeURIComponent(texto)}`;
  }

  function enviarPedido() {
    if (!estado.canasta.length) { toast('Tu canasta está vacía'); return; }
    if (!validarFormulario()) {
      const primero = $('.campo.invalido input, .campo.invalido textarea');
      primero?.focus();
      $('#checkout-estado').textContent = 'Revisá los campos marcados.';
      return;
    }
    const mensaje = construirMensaje();
    medir('Contact', {
      content_type: 'product',
      content_ids: estado.canasta.map((l) => String(l.id)),
      num_items: estado.canasta.reduce((acc, l) => acc + l.q, 0),
      currency: 'PYG',
      value: totalCanasta()
    });
    const url = linkWhatsApp(mensaje);
    const estadoEl = $('#checkout-estado');
    const ventana = window.open(url, '_blank');
    if (!ventana) {
      estadoEl.innerHTML = `Se bloqueó la ventana de WhatsApp. <a href="${esc(url)}" target="_blank" rel="noopener noreferrer"><strong>Tocá acá para abrir el pedido</strong></a> o usá "Copiar pedido".`;
    } else {
      estadoEl.textContent = 'Se abrió WhatsApp con tu pedido. Enviá el mensaje para confirmarlo.';
    }
    navigator.clipboard?.writeText(mensaje).catch(() => { });
    toast('Pedido listo para enviar por WhatsApp');
  }

  function copiarPedido() {
    if (!validarFormulario()) { toast('Completá tus datos primero'); return; }
    const mensaje = construirMensaje();
    navigator.clipboard?.writeText(mensaje)
      .then(() => toast('Pedido copiado. Pegalo en WhatsApp.'))
      .catch(() => {
        const area = document.createElement('textarea');
        area.value = mensaje;
        document.body.appendChild(area);
        area.select();
        document.execCommand('copy');
        area.remove();
        toast('Pedido copiado.');
      });
  }

  /* ------------------------------------------------------------------ */
  /* Geolocalización                                                     */
  /* ------------------------------------------------------------------ */
  async function reverseGeocodificar(lat, lng) {
    try {
      const resp = await fetch(
        `https://photon.komoot.io/reverse?lat=${encodeURIComponent(lat)}&lon=${encodeURIComponent(lng)}`,
        { cache: "no-store" }
      );
      if (!resp.ok) return "";
      const datos = await resp.json();
      const props = (datos && datos.features && datos.features[0] && datos.features[0].properties) || {};
      const calle = [props.street || props.name, props.housenumber].filter(Boolean).join(" ");
      const zona = props.district || props.locality || props.suburb || props.county || "";
      const ciudad = props.city || props.town || props.village || "";
      const vistos = new Set();
      const partes = [calle, zona, ciudad]
        .map((x) => (x || "").trim())
        .filter((x) => {
          const clave = x.toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/[^a-z0-9]/g, "");
          if (!x || vistos.has(clave)) return false;
          vistos.add(clave);
          return true;
        });
      return partes.join(", ");
    } catch (_) {
      return "";
    }
  }

  function pedirUbicacion() {
    if (!navigator.geolocation) {
      $('#ubicacion-estado').textContent = 'Tu navegador no permite compartir la ubicación. Escribí la dirección con referencias.';
      return;
    }
    const boton = $('#btn-ubicacion');
    boton.disabled = true;
    const original = boton.innerHTML;
    boton.innerHTML = 'Obteniendo ubicación…';
    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        const lat = pos.coords.latitude.toFixed(6);
        const lng = pos.coords.longitude.toFixed(6);
        estado.ubicacion = { lat, lng };
        const mapa = `https://www.google.com/maps?q=${lat},${lng}`;
        boton.innerHTML = 'Buscando la dirección…';
        const direccion = await reverseGeocodificar(lat, lng);
        const campo = $('#direccion');
        if (direccion && campo && !campo.value.trim()) {
          campo.value = direccion;
          campo.dispatchEvent(new Event('input', { bubbles: true }));
        }
        estado.ubicacion.direccion = direccion || '';
        $('#ubicacion-estado').innerHTML = direccion
          ? `Ubicación lista: <strong>${esc(direccion)}</strong> · <a href="${mapa}" target="_blank" rel="noopener noreferrer">ver en el mapa</a>`
          : `Ubicación lista · <a href="${mapa}" target="_blank" rel="noopener noreferrer">ver en el mapa</a>. No pudimos obtener la dirección: escribila para la entrega.`;
        boton.disabled = false;
        boton.innerHTML = direccion ? '✓ Ubicación y dirección agregadas' : '✓ Ubicación agregada';
        toast(direccion ? 'Ubicación y dirección agregadas' : 'Ubicación agregada');
      },
      (err) => {
        boton.disabled = false;
        boton.innerHTML = original;
        const mensajes = {
          1: 'No diste permiso de ubicación. Activá “Ubicación” para este sitio en el navegador y volvé a intentar, o escribí la dirección.',
          2: 'El GPS no está disponible en este momento. Escribí la dirección con una referencia.',
          3: 'La ubicación tardó demasiado. Probá de nuevo o escribí la dirección.'
        };
        $('#ubicacion-estado').textContent = mensajes[err.code] || 'No pudimos obtener la ubicación. Escribí la dirección con referencias.';
      },
      { enableHighAccuracy: true, timeout: 15000, maximumAge: 0 }
    );
  }

  /* ------------------------------------------------------------------ */
  /* Ficha de producto                                                   */
  /* ------------------------------------------------------------------ */
  function abrirProducto(id) {
    const p = buscarProducto(id);
    if (!p) return;
    medirProducto('ViewContent', p);
    estado.productoAbierto = p;
    $('#producto-titulo').textContent = 'Detalle del producto';
    $('#producto-contenido').innerHTML = productoHTML(p);
    renderizarBotonProducto(p.i);

    $('#btn-compartir-producto')?.addEventListener('click', () => {
      const enlace = `${location.origin}${location.pathname}?p=${encodeURIComponent(p.s || p.i)}`;
      if (navigator.clipboard) {
        navigator.clipboard.writeText(enlace).then(() => {
          toast('¡Enlace del producto copiado!');
        }).catch(() => {
          toast('Enlace: ' + enlace);
        });
      } else {
        toast('Enlace: ' + enlace);
      }
    });

    const modal = $('#modal-producto');
    modal.classList.add('abierto');
    modal.setAttribute('aria-hidden', 'false');
    document.body.classList.add('sin-scroll');
    document.querySelector('#modal-producto .modal__caja').scrollTop = 0;
  }

  function productoHTML(p) {
    const est = ESTADOS[p.e] || ESTADOS[3];
    const desc = descuentoVenta(p);
    return `
      <div class="producto-foto">
        <img src="${esc(urlImagen(p, true))}" alt="${esc(p.n)}${p.m ? ' — ' + esc(p.m) : ''} · Jaka Bicicletería, Capiatá" width="800" height="800" decoding="async" onerror="this.onerror=null;this.src='${PLACEHOLDER}'">
      </div>
      <div>
        <p class="producto-marca">${esc(p.m) || '&nbsp;'}</p>
        <h3 class="producto-nombre">${esc(p.n)}</h3>
        <div class="producto-precios">
          ${conPrecio(p) ? `<span class="ahora">${fmt(precioVenta(p))}</span>` : '<span class="ahora" style="font-size:19px;color:var(--ambar)">Precio a consultar</span>'}
          ${CONFIG.mostrarPrecioAnterior && p.o && p.p ? `<span class="antes">${fmt(precioListaVenta(p))}</span>` : ''}
          ${CONFIG.mostrarDescuento && desc >= 5 ? `<span class="off">-${desc}%</span>` : ''}
        </div>
        <div class="producto-meta">
          <span class="pill ${p.e === 1 ? 'pill--no' : (conPrecio(p) ? 'pill--ok' : 'pill--consultar')}">${est.texto}</span>
          ${p.s ? `<span class="pill">SKU: ${esc(p.s)}</span>` : ''}
          ${p.c && p.c[0] ? `<span class="pill">${esc(nombreCategoria(p.c[0]))}</span>` : ''}
        </div>
        <div class="producto-confianza">
          <div class="producto-confianza__item"><span>🚚</span> <span>Envíos a todo el país coordinados por WhatsApp</span></div>
          <div class="producto-confianza__item"><span>🏪</span> <span>Retiro disponible en nuestro local en Capiatá</span></div>
          <div class="producto-confianza__item"><span>💬</span> <span>Asesoramiento y soporte técnico directo</span></div>
        </div>
        <div class="producto-acciones" id="producto-acciones"></div>
        <button type="button" class="producto-compartir" id="btn-compartir-producto">
          <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><line x1="8.59" y1="13.51" x2="15.42" y2="17.49"/><line x1="15.41" y1="6.51" x2="8.59" y2="10.49"/></svg>
          Copiar y compartir enlace
        </button>
      </div>`;
  }

  function renderizarBotonProducto(id) {
    const cont = $('#producto-acciones');
    if (!cont) return;
    const p = buscarProducto(id);
    if (!p) return;
    const linea = lineaDe(id);
    if (!conPrecio(p)) {
      cont.innerHTML = `<button class="btn btn--wa" data-accion="consultar">Consultar precio por WhatsApp</button>`;
      return;
    }
    cont.innerHTML = `
      ${linea
        ? `<div class="stepper" data-id="${esc(p.i)}" style="max-width:160px">
             <button data-accion="restar" aria-label="Quitar uno">−</button>
             <span>${linea.q}</span>
             <button data-accion="sumar" aria-label="Agregar uno">+</button>
           </div>`
        : `<button class="btn" data-accion="agregar">Agregar a la canasta</button>`}
      <button class="btn btn--wa" data-accion="consultar">Consultar</button>`;
  }

  function manejarClicProducto(ev) {
    const boton = ev.target.closest('[data-accion]');
    if (!boton) return;
    const p = estado.productoAbierto;
    if (!p) return;
    if (boton.dataset.accion === 'agregar' || boton.dataset.accion === 'sumar') agregar(p.i, 1);
    else if (boton.dataset.accion === 'restar') agregar(p.i, -1);
    else if (boton.dataset.accion === 'consultar') consultarProducto(p);
    else if (boton.dataset.accion === 'cerrar') cerrarModal('#modal-producto');
  }

  function consultarProducto(p) {
    medirProducto('Contact', p);
    const texto = `Hola! Me interesa este producto:\n\n*${p.n}*${p.s ? `\nSKU: ${p.s}` : ''}${conPrecio(p) ? `\nPrecio: ${fmt(precioVenta(p))}` : '\n(Precio a consultar)'}\n\n¿Está disponible?`;
    window.open(linkWhatsApp(texto), '_blank', 'noopener');
  }

  /* ------------------------------------------------------------------ */
  /* Modo demo (para pruebas visuales): /?demo=1                         */
  /* ------------------------------------------------------------------ */
  async function prepararDemo() {
    try {
      let base = estado.vistas[estado.categoria] || [];
      if (!base.some((p) => conPrecio(p) && p.e === 0)) base = await cargarVista('bicicletas');
      const conP = base.filter((p) => conPrecio(p) && p.e === 0).slice(0, 3);
      if (!conP.length) return;
      conP.forEach((p) => { estado.canasta.push({ id: String(p.i), q: p.i.charCodeAt(0) % 2 ? 1 : 2 }); });
      guardarCanasta();
      actualizarContadorCanasta();
      renderizarCanasta();
      setTimeout(() => {
        abrirCheckout();
        $('#nombre').value = 'Cliente de prueba';
        $('#telefono').value = '0981 123 456';
        $('#direccion').value = 'Av. España 1234, Villa Morra, Asunción';
        $('#referencia').value = 'Portón negro';
        estado.ubicacion = { lat: '-25.286600', lng: '-57.610600' };
        $('#ubicacion-estado').innerHTML = `Ubicación lista: <a href="https://www.google.com/maps?q=${estado.ubicacion.lat},${estado.ubicacion.lng}" target="_blank" rel="noopener noreferrer">ver en el mapa</a>`;
        const mensaje = construirMensaje();
        const depuracion = document.createElement('div');
        depuracion.id = 'debug-pedido';
        depuracion.hidden = true;
        depuracion.dataset.url = linkWhatsApp(mensaje);
        depuracion.textContent = mensaje;
        document.body.appendChild(depuracion);
      }, 450);
    } catch (_) { }
  }

  document.addEventListener('DOMContentLoaded', iniciar);
})();
