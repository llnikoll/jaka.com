# -*- coding: utf-8 -*-
"""Tests de integración de bot/db/repository.py contra un PostgreSQL real.

Estos tests NECESITAN una base de datos: verifican las restricciones del esquema, la
deduplicación por id externo y la atomicidad de los pedidos. No tiene sentido simularlos
con un doble, porque lo que hay que probar es justamente lo que hace PostgreSQL
(índices únicos parciales, CHECK, ON CONFLICT, JSONB).

Si no hay DATABASE_URL configurada, se saltean en vez de fallar: así se puede correr la
suite completa en una máquina sin base de datos.

Requisitos:

    py -3 -m pip install -r bot/db/requirements.txt
    $env:DATABASE_URL = "postgresql://jaka_bot:TU_CLAVE@127.0.0.1:5432/jaka_chatbot"
    py -m unittest discover -s bot/db/tests -t . -v

Aplica `bot/db/schema.sql` al empezar (es idempotente) y borra sus propios datos al
terminar, así que se puede correr contra la base de desarrollo sin dejar basura.
"""
from __future__ import annotations

import os
import unittest
import uuid
from pathlib import Path

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError:  # pragma: no cover
    psycopg = None
    dict_row = None

from bot.db import repository

RAIZ = Path(__file__).resolve().parents[3]
SCHEMA = RAIZ / "bot" / "db" / "schema.sql"

HAY_DB = bool(os.getenv("DATABASE_URL", "").strip()) and psycopg is not None


def aplicar_schema() -> None:
    """Ejecuta schema.sql. Es IF NOT EXISTS, así que se puede correr siempre."""
    sql = SCHEMA.read_text(encoding="utf-8")
    with psycopg.connect(repository.database_url()) as conn:
        conn.execute(sql)


def borrar_datos(telefono: str) -> None:
    """
    Borra todo lo que generó el test, en orden inverso a las claves foráneas.

    Los pedidos y los mensajes no se borran en cascada desde contacts, así que hay que
    ir de abajo hacia arriba o el DELETE falla por integridad referencial.
    """
    with psycopg.connect(repository.database_url(), row_factory=dict_row) as conn:
        ids = [
            r["id"]
            for r in conn.execute(
                "SELECT id FROM conversations WHERE contact_id = "
                "(SELECT id FROM contacts WHERE phone_e164 = %s)",
                (telefono,),
            ).fetchall()
        ]
        for cid in ids:
            conn.execute("DELETE FROM audit_log WHERE conversation_id = %s", (cid,))
            conn.execute(
                "DELETE FROM order_items WHERE order_id IN "
                "(SELECT id FROM orders WHERE conversation_id = %s)",
                (cid,),
            )
            conn.execute("DELETE FROM orders WHERE conversation_id = %s", (cid,))
            conn.execute("DELETE FROM messages WHERE conversation_id = %s", (cid,))
            conn.execute("DELETE FROM conversations WHERE id = %s", (cid,))
        conn.execute("DELETE FROM contacts WHERE phone_e164 = %s", (telefono,))


@unittest.skipUnless(HAY_DB, "sin DATABASE_URL o sin psycopg: se saltea la base real")
class RepositorioTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        aplicar_schema()

    def setUp(self):
        # Teléfono único por test: evita que una corrida anterior lo ensucie.
        self.telefono = f"+59598{uuid.uuid4().int % 100000000:08d}"
        self.addCleanup(borrar_datos, self.telefono)

    # ── contactos ────────────────────────────────────────────────────

    def test_contacto_se_crea_y_es_idempotente(self):
        primero = repository.get_or_create_contact(self.telefono, "Ana")
        segundo = repository.get_or_create_contact(self.telefono, "Ana")

        self.assertEqual(primero["phone_e164"], self.telefono)
        self.assertEqual(primero["display_name"], "Ana")
        self.assertEqual(primero["id"], segundo["id"], "creó dos contactos para el mismo teléfono")

    def test_contacto_actualiza_el_nombre_sin_pisarlo_con_vacio(self):
        repository.get_or_create_contact(self.telefono, "Ana")
        sin_nombre = repository.get_or_create_contact(self.telefono)
        con_nombre = repository.get_or_create_contact(self.telefono, "Ana Gómez")

        self.assertEqual(sin_nombre["display_name"], "Ana", "un alta sin nombre borró el anterior")
        self.assertEqual(con_nombre["display_name"], "Ana Gómez")

    def test_telefono_invalido_lo_rechaza_la_base(self):
        with self.assertRaises(psycopg.errors.CheckViolation):
            repository.get_or_create_contact("0981-123-456")

    # ── conversaciones ───────────────────────────────────────────────

    def test_conversacion_abierta_es_unica_por_contacto(self):
        contacto = repository.get_or_create_contact(self.telefono)
        primera = repository.get_or_create_conversation(contacto["id"])
        segunda = repository.get_or_create_conversation(contacto["id"])

        self.assertEqual(primera["id"], segunda["id"])
        self.assertEqual(primera["status"], "bot_active")

    def test_al_cerrar_la_conversacion_se_abre_otra(self):
        contacto = repository.get_or_create_contact(self.telefono)
        primera = repository.get_or_create_conversation(contacto["id"])
        repository.set_conversation_mode(primera["id"], "closed", actor="test")

        nueva = repository.get_or_create_conversation(contacto["id"])
        self.assertNotEqual(nueva["id"], primera["id"], "reutilizó una conversación cerrada")
        self.assertEqual(nueva["status"], "bot_active")

    # ── mensajes ─────────────────────────────────────────────────────

    def test_mensaje_con_id_externo_no_se_duplica(self):
        contacto = repository.get_or_create_contact(self.telefono)
        conv = repository.get_or_create_conversation(contacto["id"])
        externo = f"wamid.{uuid.uuid4().hex}"

        primero = repository.save_message(
            conv["id"], "inbound", "Hola", provider="meta", provider_message_id=externo
        )
        repetido = repository.save_message(
            conv["id"], "inbound", "Hola", provider="meta", provider_message_id=externo
        )

        self.assertIsNotNone(primero)
        self.assertIsNone(repetido, "el reintento del webhook se guardó dos veces")

    def test_mensaje_sin_id_externo_se_guarda_igual(self):
        contacto = repository.get_or_create_contact(self.telefono)
        conv = repository.get_or_create_conversation(contacto["id"])

        primero = repository.save_message(conv["id"], "inbound", "Hola")
        segundo = repository.save_message(conv["id"], "inbound", "Hola")

        self.assertIsNotNone(primero)
        self.assertIsNotNone(segundo, "sin id externo no hay nada que deduplicar")

    def test_mensaje_actualiza_la_actividad_de_la_conversacion(self):
        contacto = repository.get_or_create_contact(self.telefono)
        conv = repository.get_or_create_conversation(contacto["id"])
        self.assertIsNone(conv["last_message_at"])

        repository.save_message(conv["id"], "inbound", "Hola")

        with psycopg.connect(repository.database_url(), row_factory=dict_row) as conn:
            actualizada = conn.execute(
                "SELECT last_message_at FROM conversations WHERE id = %s", (conv["id"],)
            ).fetchone()
        self.assertIsNotNone(actualizada["last_message_at"])

    # ── modo bot / humano ────────────────────────────────────────────

    def test_cambio_de_modo_deja_auditoria(self):
        contacto = repository.get_or_create_contact(self.telefono)
        conv = repository.get_or_create_conversation(contacto["id"])

        actualizada = repository.set_conversation_mode(
            conv["id"], "human", actor="op-1", assigned_to="Enrique"
        )
        self.assertEqual(actualizada["status"], "human")
        self.assertEqual(actualizada["assigned_to"], "Enrique")

        with psycopg.connect(repository.database_url(), row_factory=dict_row) as conn:
            filas = conn.execute(
                "SELECT actor, action, details FROM audit_log WHERE conversation_id = %s",
                (conv["id"],),
            ).fetchall()
        self.assertEqual(len(filas), 1)
        self.assertEqual(filas[0]["actor"], "op-1")
        self.assertEqual(filas[0]["action"], "conversation.mode_changed")
        self.assertEqual(filas[0]["details"]["mode"], "human")

    def test_modo_invalido_se_rechaza_antes_de_tocar_la_base(self):
        contacto = repository.get_or_create_contact(self.telefono)
        conv = repository.get_or_create_conversation(contacto["id"])
        with self.assertRaises(ValueError):
            repository.set_conversation_mode(conv["id"], "modo_inventado", actor="test")

    def test_conversacion_inexistente_lanza_error(self):
        with self.assertRaises(ValueError):
            repository.set_conversation_mode(str(uuid.uuid4()), "human", actor="test")

    # ── pedidos ──────────────────────────────────────────────────────

    def _conversacion(self):
        contacto = repository.get_or_create_contact(self.telefono, "Ana")
        conv = repository.get_or_create_conversation(contacto["id"])
        return contacto, conv

    def test_pedido_pendiente_con_items_y_subtotal(self):
        contacto, conv = self._conversacion()

        pedido = repository.create_pending_order(
            conv["id"],
            contacto["id"],
            [
                {"product_id": "442397", "product_name": "Barra portaequipaje",
                 "quantity": 2, "unit_price": 447350, "availability": "available_in_catalog"},
                {"product_id": "motocicleta-kenton-go-125", "product_name": "Kenton GO 125",
                 "quantity": 1, "unit_price": 8081050, "availability": "confirm"},
            ],
            customer_name="Ana",
            delivery_method="delivery",
            delivery_address="Capiatá",
        )

        self.assertEqual(pedido["status"], "pending_confirmation")
        self.assertEqual(pedido["subtotal"], 447350 * 2 + 8081050)

        with psycopg.connect(repository.database_url(), row_factory=dict_row) as conn:
            items = conn.execute(
                "SELECT product_id, quantity, unit_price, availability_snapshot "
                "FROM order_items WHERE order_id = %s ORDER BY product_id",
                (pedido["id"],),
            ).fetchall()
            auditoria = conn.execute(
                "SELECT action FROM audit_log WHERE conversation_id = %s", (conv["id"],)
            ).fetchall()

        self.assertEqual(len(items), 2)
        moto = next(i for i in items if i["product_id"].startswith("motocicleta"))
        self.assertEqual(moto["availability_snapshot"], "confirm")
        self.assertEqual(moto["unit_price"], 8081050)
        self.assertIn("order.created_pending", [a["action"] for a in auditoria])

    def test_pedido_sin_stock_confirmado_se_guarda_igual(self):
        contacto, conv = self._conversacion()
        pedido = repository.create_pending_order(
            conv["id"], contacto["id"],
            [{"product_id": "x1", "product_name": "Producto agotado", "quantity": 1,
              "unit_price": 100000, "availability": "out_of_stock"}],
        )
        self.assertEqual(pedido["status"], "pending_confirmation")

    def test_pedido_sin_items_se_rechaza(self):
        contacto, conv = self._conversacion()
        with self.assertRaises(ValueError):
            repository.create_pending_order(conv["id"], contacto["id"], [])

    def test_cantidad_invalida_se_rechaza(self):
        contacto, conv = self._conversacion()
        with self.assertRaises(ValueError):
            repository.create_pending_order(
                conv["id"], contacto["id"],
                [{"product_id": "x", "product_name": "X", "quantity": 0, "unit_price": 1}],
            )

    def test_disponibilidad_invalida_se_rechaza(self):
        contacto, conv = self._conversacion()
        with self.assertRaises(ValueError):
            repository.create_pending_order(
                conv["id"], contacto["id"],
                [{"product_id": "x", "product_name": "X", "quantity": 1,
                  "unit_price": 1, "availability": "hay_stock"}],
            )

    def test_metodo_de_entrega_invalido_se_rechaza(self):
        contacto, conv = self._conversacion()
        with self.assertRaises(ValueError):
            repository.create_pending_order(
                conv["id"], contacto["id"],
                [{"product_id": "x", "product_name": "X", "quantity": 1, "unit_price": 1}],
                delivery_method="envio",
            )

    def test_pedido_invalido_no_deja_basura(self):
        """
        Si algo falla DESPUÉS de insertar el pedido, la transacción entera se revierte.

        El item malo pasa la validación de Python pero rompe el tipo INTEGER de la base
        (cantidad 2**40), así que el error ocurre con el pedido ya insertado: es la única
        forma de probar de verdad el rollback y no solo la validación previa.
        """
        contacto, conv = self._conversacion()
        with self.assertRaises(psycopg.Error):
            repository.create_pending_order(
                conv["id"], contacto["id"],
                [
                    {"product_id": "ok", "product_name": "Bien", "quantity": 1,
                     "unit_price": 1000, "availability": "confirm"},
                    {"product_id": "rompe", "product_name": "Cantidad imposible",
                     "quantity": 2**40, "unit_price": 1, "availability": "confirm"},
                ],
            )
        with psycopg.connect(repository.database_url(), row_factory=dict_row) as conn:
            pedidos = conn.execute(
                "SELECT count(*) AS n FROM orders WHERE conversation_id = %s", (conv["id"],)
            ).fetchone()
        self.assertEqual(pedidos["n"], 0, "quedó un pedido a medio crear")


if __name__ == "__main__":
    unittest.main()
