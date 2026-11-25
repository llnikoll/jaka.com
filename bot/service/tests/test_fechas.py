# bot/service/tests/test_fechas.py
"""Pruebas de la interpretación de fechas para los turnos.

Importa que sean estables: si "el sábado" se interpreta mal, el cliente cae otro día.
Las pruebas usan una fecha de referencia fija para no depender del día en que se corren.
"""
from __future__ import annotations

import unittest
from datetime import date, timedelta

from bot.service import fechas

# Miércoles 25/11/2026, para tener un día de semana conocido.
MIERCOLES = date(2026, 11, 25)


class ParsearTest(unittest.TestCase):
    def parsear(self, texto):
        return fechas.parsear(texto, referencia=MIERCOLES)

    def test_hoy(self):
        self.assertEqual(self.parsear("hoy"), MIERCOLES)

    def test_manana_con_y_sin_enie(self):
        self.assertEqual(self.parsear("mañana"), MIERCOLES + timedelta(days=1))
        self.assertEqual(self.parsear("manana"), MIERCOLES + timedelta(days=1))

    def test_proximo_dia_de_la_semana(self):
        # Desde un miércoles, "el sábado" es en 3 días.
        self.assertEqual(self.parsear("el sabado"), date(2026, 11, 28))
        self.assertEqual(self.parsear("sábado"), date(2026, 11, 28))

    def test_mismo_dia_cuenta_como_hoy(self):
        self.assertEqual(self.parsear("miercoles"), MIERCOLES)

    def test_dia_ya_pasado_va_a_la_semana_siguiente(self):
        # "lunes" desde un miércoles: el próximo lunes, no el que pasó.
        self.assertEqual(self.parsear("lunes"), date(2026, 11, 30))

    def test_abreviaturas(self):
        self.assertEqual(self.parsear("saba"), date(2026, 11, 28))
        self.assertEqual(self.parsear("mierc"), MIERCOLES)

    def test_formato_dd_mm(self):
        self.assertEqual(self.parsear("29/11"), date(2026, 11, 29))

    def test_formato_iso(self):
        self.assertEqual(self.parsear("2026-12-03"), date(2026, 12, 3))

    def test_fecha_pasada_se_rechaza(self):
        with self.assertRaises(ValueError) as ctx:
            self.parsear("03/11")
        self.assertIn("pasó", str(ctx.exception))

    def test_fecha_muy_lejana_se_rechaza(self):
        with self.assertRaises(ValueError):
            self.parsear("2027-06-01")

    def test_texto_que_no_es_fecha(self):
        with self.assertRaises(ValueError) as ctx:
            self.parsear("cuando pueda")
        self.assertIn("No entendí", str(ctx.exception))

    def test_vacio(self):
        with self.assertRaises(ValueError):
            self.parsear("")

    def test_describir(self):
        self.assertEqual(fechas.describir(date(2026, 11, 28)), "sábado 28/11")


if __name__ == "__main__":
    unittest.main()
