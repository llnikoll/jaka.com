# bot/service/tests/test_catalogo.py
"""Pruebas del armado de la URL de la imagen del producto.

La foto se manda por WhatsApp y el CDN de Ciclovía respeta los parámetros de tamaño:
la original pesa hasta 350 KB y con `?quality=85&fit=bounds&height=800&width=800`
queda en ~60 KB. Estos tests fijan esa lógica, que es fácil de romper sin darse cuenta
(por ejemplo, agregando los parámetros dos veces o pisando los que ya trae la URL).
"""
from __future__ import annotations

import unittest

from bot.service import catalogo


class UrlConMedidaTest(unittest.TestCase):
    def test_agrega_los_params_a_una_url_sin_query(self):
        url = catalogo._url_con_medida("https://cdn.test/foto.jpg")
        self.assertIn("https://cdn.test/foto.jpg?", url)
        self.assertIn("quality=85", url)

    def test_usa_ampersand_si_ya_hay_query(self):
        url = catalogo._url_con_medida("https://cdn.test/foto.jpg?v=2")
        self.assertIn("foto.jpg?v=2&quality=85", url)
        self.assertNotIn("?v=2?quality", url)

    def test_no_duplica_el_signo_de_pregunta(self):
        url = catalogo._url_con_medida("https://cdn.test/foto.jpg")
        self.assertEqual(url.count("?"), 1)

    def test_deja_pasar_urls_que_no_son_http(self):
        self.assertEqual(catalogo._url_con_medida("img/local.jpg"), "img/local.jpg")

    def test_tolera_vacio_y_none(self):
        self.assertEqual(catalogo._url_con_medida(""), "")
        self.assertIsNone(catalogo._url_con_medida(None))

    def test_incluye_alto_y_ancho(self):
        url = catalogo._url_con_medida("https://cdn.test/foto.jpg")
        self.assertIn("height=800", url)
        self.assertIn("width=800", url)


class ResumirProductoTest(unittest.TestCase):
    def test_incluye_la_imagen_ya_dimensionada(self):
        resumen = catalogo.resumir_producto(
            {
                "id": "1",
                "name": "CASCO",
                "image": "https://cdn.test/casco.jpg",
                "price": 230000,
            }
        )
        self.assertIn("quality=85", resumen["imagen"])

    def test_producto_sin_imagen_no_rompe(self):
        resumen = catalogo.resumir_producto({"id": "1", "name": "SIN FOTO", "image": None})
        self.assertIsNone(resumen["imagen"])

    def test_no_pasa_campos_de_mas_al_modelo(self):
        """Cuanto menos relleno recibe el modelo, menos inventa."""
        resumen = catalogo.resumir_producto(
            {"id": "1", "name": "X", "image": None, "metadata": {"a": 1}, "source": "Ciclovía"}
        )
        self.assertNotIn("metadata", resumen)
        self.assertNotIn("source", resumen)


if __name__ == "__main__":
    unittest.main()
