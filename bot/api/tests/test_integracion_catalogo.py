# -*- coding: utf-8 -*-
"""Tests de integración de la API de catálogo contra el catálogo real del repositorio.

A diferencia de test_server.py (que prueba funciones sueltas), esto valida la API
completa: que cargue los JSON publicados, que el precio de venta sea EXACTAMENTE el
mismo que muestra la tienda, que los estados de stock coincidan con el índice y que
las rutas HTTP respondan lo que dice la especificación.

El precio se compara contra el código real de tienda/assets/app.js, ejecutado con Node
(unidad de paridad entre el frontend y la API). Si Node no está instalado, esa prueba
se saltea en vez de fallar: la API igual tiene que poder validarse en otros equipos.

Se corre desde la raíz del repositorio:

    python -m unittest bot.api.tests.test_integracion_catalogo -v
"""
from __future__ import annotations

import json
import shutil
import subprocess
import threading
import unittest
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path

from bot.api.server import (
    DATA,
    Handler,
    ThreadingHTTPServer,
    load_config,
    load_products,
    sale_price,
)

RAIZ = Path(__file__).resolve().parents[3]
BIKES = DATA / "v" / "todos.json"
MOTOS = DATA / "motos" / "v" / "todos.json"
INDICE = DATA / "indice.json"
SCRIPT_PRECIOS = Path(__file__).resolve().parent / "precios_app_js.mjs"

# Producto real y estable del catálogo de Ciclovía, usado como canario.
PRODUCTO_CANARIO = "442397"


def leer_json(ruta: Path):
    return json.loads(ruta.read_text(encoding="utf-8"))


class CatalogoRealTest(unittest.TestCase):
    """Contra los archivos que el repositorio publica hoy."""

    @classmethod
    def setUpClass(cls):
        cls.productos, cls.indice = load_products()
        cls.cfg = load_config()

    def test_carga_todo_el_catalogo(self):
        self.assertGreater(len(self.productos), 15000, "el catálogo se cargó incompleto")
        kinds = Counter(p["kind"] for p in self.productos)
        self.assertGreater(kinds["bicicletas"], 2000)
        self.assertGreater(kinds["motos"], 12000)

    def test_el_total_coincide_con_el_indice(self):
        # El índice es lo que la tienda usa para decir cuántos productos hay.
        esperado = self.indice.get("meta", {}).get("total")
        if esperado:
            self.assertEqual(
                len(self.productos), esperado, "la API y el índice no coinciden en el total"
            )

    def test_estados_de_stock_coinciden_con_el_indice(self):
        bikes = leer_json(BIKES)
        por_codigo = Counter(p.get("e") for p in bikes)
        por_estado = self.indice.get("meta", {}).get("por_estado") or {}
        if not por_estado:
            self.skipTest("el índice no trae por_estado")
        self.assertEqual(por_codigo.get(0, 0), por_estado.get("con_precio"))
        self.assertEqual(por_codigo.get(1, 0), por_estado.get("agotado"))
        self.assertEqual(por_codigo.get(2, 0), por_estado.get("solo_catalogo"))
        self.assertEqual(por_codigo.get(3, 0), por_estado.get("sin_dato"))

    def test_ningun_producto_sin_id_ni_duplicado(self):
        ids = [p["id"] for p in self.productos]
        self.assertEqual(len(ids), len(set(ids)), "hay ids repetidos entre bicis y motos")
        self.assertTrue(all(pid.strip() for pid in ids))

    def test_motos_siempre_requieren_confirmacion(self):
        motos = [p for p in self.productos if p["kind"] == "motos"]
        self.assertTrue(motos, "no se cargaron motos")
        for p in motos:
            self.assertTrue(p["stock_confirm_required"], f"{p['id']} no pide confirmación")
            self.assertEqual(p["source"], "Chacomer")

    def test_bicicletas_ids_y_fuente(self):
        bikes = [p for p in self.productos if p["kind"] == "bicicletas"]
        self.assertTrue(bikes)
        for p in bikes[:200]:
            self.assertEqual(p["source"], "Ciclovía")
            self.assertTrue(p["product_url"].startswith("https://"))

    def test_servicios_coinciden_con_config_js(self):
        self.assertEqual(len(self.cfg["servicios"]), 3)
        precios = [s["precio"] for s in self.cfg["servicios"]]
        self.assertEqual(precios, [80000, 120000, 150000])
        # El recargo tiene que salir del config.js, no de los valores por defecto.
        self.assertEqual(self.cfg["recargoPct"], 15.0)

    def test_producto_canario(self):
        product = next((p for p in self.productos if p["id"] == PRODUCTO_CANARIO), None)
        self.assertIsNotNone(product, f"el producto canario {PRODUCTO_CANARIO} no está")

    def test_producto_sin_precio_no_inventa_precio(self):
        # Los productos "solo catálogo" tienen p=null; el precio debe quedar null.
        sin_precio = [p for p in self.productos if p["source_price"] is None]
        self.assertTrue(sin_precio, "el catálogo debería tener productos sin precio")
        for p in sin_precio[:50]:
            self.assertIsNone(sale_price(p["source_price"], self.cfg))


class ParidadDePrecioTest(unittest.TestCase):
    """El precio de la API tiene que ser el mismo que el de la tienda, siempre."""

    @classmethod
    def setUpClass(cls):
        if not shutil.which("node"):
            raise unittest.SkipTest("Node no está instalado: no se puede comparar con app.js")
        if not SCRIPT_PRECIOS.exists():
            raise unittest.SkipTest("falta el script de precios de referencia")

    def test_precio_igual_al_de_app_js_en_todo_el_catalogo(self):
        resultado = subprocess.run(
            ["node", str(SCRIPT_PRECIOS), str(RAIZ)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=300,
            check=False,
        )
        if resultado.returncode != 0:
            self.fail(
                "el script que evalúa app.js falló (¿cambió la forma de las funciones de "
                f"precio?): {resultado.stderr[-800:]}"
            )
        datos = json.loads(resultado.stdout)
        precios_js = datos["precios"]
        self.assertGreater(len(precios_js), 15000, "app.js no devolvió todo el catálogo")

        cfg = load_config()
        distintos = []
        for pid, d in precios_js.items():
            calculado = sale_price(d["p"], cfg)
            if calculado != d["precio"]:
                distintos.append((pid, d["p"], d["precio"], calculado))

        self.assertEqual(
            distintos,
            [],
            f"{len(distintos)} precios no coinciden con la tienda; primeros: {distintos[:5]}",
        )


class HttpTest(unittest.TestCase):
    """Las rutas, sobre un servidor real escuchando en un puerto libre."""

    @classmethod
    def setUpClass(cls):
        cls.servidor = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.puerto = cls.servidor.server_address[1]
        cls.hilo = threading.Thread(target=cls.servidor.serve_forever, daemon=True)
        cls.hilo.start()

    @classmethod
    def tearDownClass(cls):
        cls.servidor.shutdown()
        cls.servidor.server_close()

    def pedir(self, ruta):
        url = f"http://127.0.0.1:{self.puerto}{ruta}"
        try:
            with urllib.request.urlopen(url, timeout=30) as r:
                return r.status, json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            cuerpo = e.read().decode("utf-8")
            return e.code, json.loads(cuerpo) if cuerpo else None

    def test_health(self):
        estado, datos = self.pedir("/health")
        self.assertEqual(estado, 200)
        self.assertTrue(datos["ok"])

    def test_status(self):
        estado, datos = self.pedir("/catalog/status")
        self.assertEqual(estado, 200)
        self.assertGreater(datos["total"], 15000)
        self.assertEqual(datos["by_type"]["bicicletas"] + datos["by_type"]["motos"], datos["total"])

    def test_busqueda_sin_acentos(self):
        estado, datos = self.pedir("/catalog/search?q=camara%2026&limit=5")
        self.assertEqual(estado, 200)
        self.assertGreater(datos["total"], 0)
        self.assertLessEqual(len(datos["items"]), 5)

    def test_busqueda_por_marca(self):
        estado, datos = self.pedir("/catalog/search?q=scott&limit=3")
        self.assertEqual(estado, 200)
        self.assertGreater(datos["total"], 0)
        for item in datos["items"]:
            self.assertIn("SCOTT", json.dumps(item, ensure_ascii=False).upper())

    def test_busqueda_filtra_por_tipo(self):
        estado, datos = self.pedir("/catalog/search?q=scott&type=motos&limit=5")
        self.assertEqual(estado, 200)
        for item in datos["items"]:
            self.assertEqual(item["kind"], "motos")

    def test_producto_canario_por_http(self):
        estado, datos = self.pedir(f"/catalog/product/{PRODUCTO_CANARIO}")
        self.assertEqual(estado, 200)
        item = datos["item"]
        self.assertEqual(item["id"], PRODUCTO_CANARIO)
        self.assertIn("price", item)
        self.assertIn("availability", item)
        self.assertIn("availability_label", item)

    def test_producto_inexistente_404(self):
        estado, datos = self.pedir("/catalog/product/no-existe-999")
        self.assertEqual(estado, 404)
        self.assertIn("error", datos)

    def test_parametros_invalidos_400(self):
        self.assertEqual(self.pedir("/catalog/search")[0], 400)
        self.assertEqual(self.pedir("/catalog/search?q=scott&type=autos")[0], 400)
        self.assertEqual(self.pedir("/catalog/search?q=scott&limit=abc")[0], 400)

    def test_categorias_y_servicios(self):
        estado, datos = self.pedir("/catalog/categories")
        self.assertEqual(estado, 200)
        self.assertGreater(datos["count"], 10)
        slugs = {c["slug"] for c in datos["items"]}
        self.assertIn("bicicletas", slugs)
        self.assertIn("motos", slugs)

        estado, datos = self.pedir("/services")
        self.assertEqual(estado, 200)
        self.assertEqual([s["precio"] for s in datos["items"]], [80000, 120000, 150000])

    def test_ruta_inexistente_404(self):
        self.assertEqual(self.pedir("/no-existe")[0], 404)


if __name__ == "__main__":
    unittest.main()
