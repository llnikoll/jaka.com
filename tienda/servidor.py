#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Servidor local de la tienda, con compresión gzip y caché.
Se usa para probar en la PC o para compartir por túnel; en un hosting
real (Netlify, Vercel, cPanel) la compresión la hace el servidor.

    python tienda/servidor.py            # http://127.0.0.1:8080
    python tienda/servidor.py 9000       # otro puerto
"""

from __future__ import annotations

import gzip
import os
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

RAIZ = os.path.dirname(os.path.abspath(__file__))
COMPRIMIBLES = (".html", ".css", ".js", ".json", ".svg", ".txt", ".xml")


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=RAIZ, **kwargs)

    def do_GET(self):  # noqa: N802
        acepta_gzip = "gzip" in self.headers.get("Accept-Encoding", "").lower()
        ruta = self.translate_path(self.path)
        if os.path.isdir(ruta):
            ruta = os.path.join(ruta, "index.html")

        if acepta_gzip and os.path.isfile(ruta) and ruta.lower().endswith(COMPRIMIBLES):
            try:
                with open(ruta, "rb") as fh:
                    datos = fh.read()
            except OSError:
                return super().do_GET()

            comprimido = gzip.compress(datos, 6)
            if ruta.lower().endswith((".json", ".js")):
                cache = "public, max-age=60"
            elif ruta.lower().endswith(".html"):
                cache = "public, max-age=300"
            else:
                cache = "public, max-age=3600"
            self.send_response(200)
            self.send_header("Content-Type", self.guess_type(ruta))
            self.send_header("Content-Encoding", "gzip")
            self.send_header("Content-Length", str(len(comprimido)))
            self.send_header("Vary", "Accept-Encoding")
            self.send_header("Cache-Control", cache)
            self.send_header("Last-Modified", self.date_time_string(int(os.path.getmtime(ruta))))
            self.end_headers()
            self.wfile.write(comprimido)
            return

        return super().do_GET()

    def log_message(self, fmt, *args):  # noqa: A003
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))


def main() -> None:
    puerto = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    servidor = ThreadingHTTPServer(("0.0.0.0", puerto), Handler)
    print(f"Tienda disponible en http://127.0.0.1:{puerto}")
    print("Gzip activado para HTML, CSS, JS y JSON. Ctrl+C para cortar.")
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor detenido.")
    finally:
        servidor.server_close()


if __name__ == "__main__":
    main()
