# bot/service/server.py
"""Servidor local del chatbot: una página para chatear y un endpoint para probar.

Se levanta con:

    python -m bot.service.server

y queda en http://127.0.0.1:8790 — sólo escucha en loopback, no se expone a la red.

No es el webhook de WhatsApp todavía: es el banco de pruebas. Sirve para ver si el
agente contesta bien antes de meter a Meta, n8n y los tokens en el medio.
"""
from __future__ import annotations

import json
import logging
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from bot.service import asistente, catalogo, config, memoria

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("jaka")

TELEFONO_PRUEBA = "local-prueba"


class Handler(BaseHTTPRequestHandler):
    server_version = "JakaChatbotLocal/1.0"

    # ── respuestas ───────────────────────────────────────────────────

    def _json(self, estado: int, payload: dict) -> None:
        cuerpo = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(estado)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(cuerpo)

    def _html(self, cuerpo: str) -> None:
        datos = cuerpo.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(datos)))
        self.end_headers()
        self.wfile.write(datos)

    # ── rutas ────────────────────────────────────────────────────────

    def do_GET(self):  # noqa: N802
        ruta = self.path.split("?", 1)[0].rstrip("/") or "/"

        if ruta == "/":
            return self._html(PAGINA)
        if ruta == "/health":
            return self._json(200, estado_servicio())
        return self._json(404, {"error": "Ruta no encontrada"})

    def do_POST(self):  # noqa: N802
        ruta = self.path.split("?", 1)[0].rstrip("/")

        if ruta == "/limpiar":
            memoria.limpiar(TELEFONO_PRUEBA)
            return self._json(200, {"ok": True})

        if ruta != "/mensaje":
            return self._json(404, {"error": "Ruta no encontrada"})

        try:
            largo = int(self.headers.get("Content-Length") or 0)
            datos = json.loads(self.rfile.read(largo).decode("utf-8") or "{}")
        except (ValueError, UnicodeDecodeError):
            return self._json(400, {"error": "El cuerpo tiene que ser JSON válido"})

        texto = (datos.get("texto") or "").strip()
        if not texto:
            return self._json(400, {"error": "Falta el campo 'texto'"})

        telefono = (datos.get("telefono") or TELEFONO_PRUEBA).strip()
        historial = memoria.contexto(telefono, config.MAX_HISTORIAL)
        resultado = asistente.responder(
            texto,
            historial,
            crear_pedido=lambda lineas: memoria.crear_pedido(telefono, lineas),
            crear_turno=lambda servicio, fecha: memoria.crear_turno(telefono, servicio, fecha),
            marcar_humano=lambda: memoria.marcar_humano(telefono),
        )

        # Los avisos técnicos no se guardan como si fueran una respuesta del agente.
        if not resultado.get("error"):
            memoria.guardar(telefono, texto, resultado["respuesta"])

        logger.info(
            f"[{telefono}] {texto!r} -> {resultado['intencion']} "
            f"({resultado['ms']} ms) {resultado['respuesta']!r}"
        )
        resultado["texto"] = texto
        resultado["telefono"] = telefono
        return self._json(200, resultado)

    def log_message(self, fmt, *args):
        # Se silencia el log por request: ya se loguea la conversación completa.
        return


def estado_servicio() -> dict:
    """Diagnóstico: qué piezas están arriba."""
    detalle: dict = {
        "ok": True,
        "service": "jaka-chatbot-local",
        "modelo": config.GEMINI_MODEL,
        "ia": "configurada" if config.hay_ia() else "falta GEMINI_API_KEY",
        "base_de_datos": "postgresql" if memoria.hay_base() else f"memoria ({memoria.motivo_sin_base()})",
    }
    try:
        estado = catalogo.estado()
        detalle["catalogo"] = {"ok": True, "productos": estado.get("total")}
    except catalogo.ErrorCatalogo as e:
        detalle["catalogo"] = {"ok": False, "detalle": str(e)}
        detalle["ok"] = False
    return detalle


def main() -> int:
    if not config.hay_ia():
        print(
            "ERROR: falta GEMINI_API_KEY.\n"
            "Ponela en bot/service/.env o exportala en el entorno.",
            file=sys.stderr,
        )
        return 1

    print()
    print("=" * 58)
    print("  Jaka — chatbot local")
    print("=" * 58)
    print(f"  Abrí en el navegador:  http://{config.SERVICE_HOST}:{config.SERVICE_PORT}")
    print(f"  Modelo:                {config.GEMINI_MODEL}")
    print(f"  Catálogo:              {config.CATALOG_API_URL}")
    print(f"  Historial:             {'PostgreSQL' if memoria.hay_base() else 'memoria'}")
    print("  Ctrl+C para detener.")
    print()

    try:
        catalogo.estado()
    except catalogo.ErrorCatalogo as e:
        print(f"  AVISO: {e}", file=sys.stderr)
        print("  El chat arranca igual, pero sin catálogo no puede dar precios.\n", file=sys.stderr)

    servidor = ThreadingHTTPServer((config.SERVICE_HOST, config.SERVICE_PORT), Handler)
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\nHasta luego.")
    finally:
        servidor.server_close()
    return 0


PAGINA = """<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Jaka — prueba local</title>
<style>
  :root { color-scheme: dark; }
  * { box-sizing: border-box; }
  body { margin: 0; font: 15px/1.5 system-ui, -apple-system, Segoe UI, sans-serif;
         background: #0f1115; color: #e7e9ee; display: flex; flex-direction: column;
         height: 100dvh; }
  header { padding: 12px 16px; background: #161a22; border-bottom: 1px solid #242a35;
           display: flex; justify-content: space-between; align-items: center; gap: 12px; }
  header strong { font-size: 15px; }
  header span { font-size: 12px; color: #8b93a4; }
  button { font: inherit; border: 0; border-radius: 10px; padding: 10px 14px;
           background: #25d366; color: #04120a; font-weight: 600; cursor: pointer; }
  button.sec { background: #242a35; color: #cfd4dd; font-weight: 500; padding: 7px 11px; }
  button:disabled { opacity: .5; cursor: default; }
  #chat { flex: 1; overflow-y: auto; padding: 16px; display: flex;
          flex-direction: column; gap: 10px; }
  .msg { max-width: 78%; padding: 10px 13px; border-radius: 14px; white-space: pre-wrap;
         word-wrap: break-word; }
  .msg img { display: block; max-width: 100%; margin-top: 8px; border-radius: 10px;
             background: #0f1115; }
  .msg .foto-pie { font-size: 11px; color: #8b93a4; margin-top: 4px; }
  .user { align-self: flex-end; background: #2b5d3f; border-bottom-right-radius: 4px; }
  .bot { align-self: flex-start; background: #1c222c; border-bottom-left-radius: 4px; }
  .meta { font-size: 11px; color: #7d8597; margin-top: 4px; }
  form { display: flex; gap: 8px; padding: 12px; background: #161a22;
         border-top: 1px solid #242a35; }
  input { flex: 1; font: inherit; padding: 12px 14px; border-radius: 12px;
          border: 1px solid #2b3341; background: #0f1115; color: inherit; }
  input:focus { outline: 2px solid #25d36644; border-color: #25d366; }
  .typing { color: #8b93a4; font-size: 13px; align-self: flex-start; }
</style>
</head>
<body>
<header>
  <div><strong>Jaka Bicicletería</strong><br><span>prueba local — sin WhatsApp</span></div>
  <button class="sec" id="limpiar">Limpiar</button>
</header>
<div id="chat">
  <div class="bot msg">Hola! Soy Jaka. Preguntame por precios, stock o service.</div>
</div>
<form id="form">
  <input id="texto" placeholder="Escribí como si fueras un cliente…" autocomplete="off" autofocus>
  <button id="enviar" type="submit">Enviar</button>
</form>
<script>
const chat = document.getElementById('chat');
const form = document.getElementById('form');
const input = document.getElementById('texto');
const boton = document.getElementById('enviar');

function burbuja(texto, clase, meta) {
  const div = document.createElement('div');
  div.className = 'msg ' + clase;
  div.textContent = texto;
  if (meta) {
    const m = document.createElement('div');
    m.className = 'meta';
    m.textContent = meta;
    div.appendChild(m);
  }
  chat.appendChild(div);
  chat.scrollTop = chat.scrollHeight;
  return div;
}

form.addEventListener('submit', async (e) => {
  e.preventDefault();
  const texto = input.value.trim();
  if (!texto) return;
  burbuja(texto, 'user');
  input.value = '';
  input.disabled = true; boton.disabled = true;
  const esperando = document.createElement('div');
  esperando.className = 'typing';
  esperando.textContent = 'Jaka está escribiendo…';
  chat.appendChild(esperando);
  chat.scrollTop = chat.scrollHeight;

  try {
    const r = await fetch('/mensaje', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ texto })
    });
    const datos = await r.json();
    esperando.remove();
    if (datos.error && !datos.respuesta) {
      burbuja('Error: ' + (datos.error || 'no se pudo responder'), 'bot');
    } else {
      const meta = [datos.intencion, datos.ms ? datos.ms + ' ms' : null].filter(Boolean).join(' · ');
      const globo = burbuja(datos.respuesta, 'bot', meta);

      // La foto del producto: en WhatsApp va como mensaje aparte, acá se muestra
      // pegada a la respuesta para que se vea tal cual la recibiría el cliente.
      if (datos.imagen && datos.imagen.url) {
        const img = document.createElement('img');
        img.src = datos.imagen.url;
        img.alt = datos.imagen.producto || 'producto';
        img.loading = 'lazy';
        img.referrerPolicy = 'no-referrer';
        img.addEventListener('error', () => img.remove());
        globo.appendChild(img);
        if (datos.imagen.producto) {
          const pie = document.createElement('div');
          pie.className = 'foto-pie';
          pie.textContent = 'foto: ' + datos.imagen.producto;
          globo.appendChild(pie);
        }
      }
    }
  } catch (err) {
    esperando.remove();
    burbuja('No se pudo conectar con el servidor.', 'bot');
  } finally {
    input.disabled = false; boton.disabled = false; input.focus();
  }
});

document.getElementById('limpiar').addEventListener('click', async () => {
  await fetch('/limpiar', { method: 'POST' });
  chat.innerHTML = '';
  burbuja('Hola! Soy Jaka. Preguntame por precios, stock o service.', 'bot');
});
</script>
</body>
</html>
"""


if __name__ == "__main__":
    sys.exit(main())
