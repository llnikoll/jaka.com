import unittest

from bot.api.server import availability, normalize, round_sale, sale_price, DEFAULT_CONFIG


class VelocidadesTest(unittest.TestCase):
    """
    El catálogo escribe las velocidades de tres formas: "7 VELOCIDADES", "7V" y "7VL".
    Todas tienen que quedar en el mismo token, porque si no, buscar "piñón 7 velocidades"
    devuelve 1 producto cuando hay 5.
    """

    def test_velocidades_se_unifica_a_7v(self):
        self.assertEqual(normalize("PIÑON 7 VELOCIDADES"), "pinon 7v")

    def test_forma_corta_7v(self):
        self.assertEqual(normalize("PIÑON SUNRACE 7V 11-34T"), "pinon sunrace 7v 11 34t")

    def test_forma_vl_con_punto(self):
        self.assertEqual(normalize("PIÑON SHIMANO TZ-500 7VL. E-MTB"), "pinon shimano tz 500 7v e mtb")

    def test_no_confunde_un_numero_suelto(self):
        """Un 7 en un código no debe convertirse en '7v'."""
        self.assertEqual(normalize("PIÑON DE LEVA MILESTONE 90712124"), "pinon de leva milestone 90712124")

    def test_medidas_normales_no_se_tocan(self):
        self.assertEqual(normalize("CÁMARA 26 X 1.50"), "camara 26 x 1 50")

    def test_once_velocidades_no_se_vuelve_siete(self):
        self.assertEqual(normalize("PIÑON 11V 11-51"), "pinon 11v 11 51")


class CatalogRulesTest(unittest.TestCase):
    def test_normalize_accents_and_punctuation(self):
        self.assertEqual(normalize("CÁMARA 26\" - MTB"), "camara 26 mtb")

    def test_sale_price_matches_store_rounding(self):
        self.assertEqual(sale_price(100000, DEFAULT_CONFIG), 115000)
        self.assertEqual(sale_price(100001, DEFAULT_CONFIG), 116000)

    def test_rounding_steps(self):
        self.assertEqual(round_sale(999, True), 1000)
        self.assertEqual(round_sale(100001, True), 101000)
        self.assertEqual(round_sale(1000001, True), 1010000)

    def test_moto_availability_requires_confirmation(self):
        product = {"stock_confirm_required": True, "stock_code": 0}
        self.assertEqual(availability(product), "confirm")


if __name__ == "__main__":
    unittest.main()
