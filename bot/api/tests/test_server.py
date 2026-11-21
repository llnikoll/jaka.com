import unittest

from bot.api.server import availability, normalize, round_sale, sale_price, DEFAULT_CONFIG


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
