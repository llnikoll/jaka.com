"""Persistencia PostgreSQL para conversaciones y pedidos de Jaka.

Requiere psycopg 3 y DATABASE_URL. No contiene lógica de catálogo ni WhatsApp.
"""
from __future__ import annotations

import json
import os
from contextlib import contextmanager
from typing import Any

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError:  # Permite importar el módulo y mostrar un error claro al usarlo.
    psycopg = None
    dict_row = None


def database_url() -> str:
    value = os.getenv("DATABASE_URL", "").strip()
    if not value:
        raise RuntimeError("Falta DATABASE_URL. Configurá la conexión PostgreSQL en el entorno.")
    return value


@contextmanager
def connection():
    if psycopg is None:
        raise RuntimeError("Falta psycopg. Instalá: py -3 -m pip install -r bot/db/requirements.txt")
    with psycopg.connect(database_url(), row_factory=dict_row) as conn:
        yield conn


def get_or_create_contact(phone_e164: str, display_name: str | None = None) -> dict[str, Any]:
    """Crea o actualiza el nombre visible del contacto; el teléfono debe estar normalizado."""
    with connection() as conn:
        row = conn.execute(
            """
            INSERT INTO contacts (phone_e164, display_name)
            VALUES (%s, %s)
            ON CONFLICT (phone_e164) DO UPDATE
              SET display_name = COALESCE(EXCLUDED.display_name, contacts.display_name),
                  updated_at = NOW()
            RETURNING *
            """,
            (phone_e164, display_name),
        ).fetchone()
        return row


def get_or_create_conversation(contact_id: str, channel: str = "whatsapp") -> dict[str, Any]:
    """Devuelve o crea atómicamente la conversación abierta del contacto/canal."""
    with connection() as conn:
        return conn.execute(
            """
            INSERT INTO conversations (contact_id, channel)
            VALUES (%s, %s)
            ON CONFLICT (contact_id, channel) WHERE status <> 'closed'
            DO UPDATE SET updated_at = conversations.updated_at
            RETURNING *
            """,
            (contact_id, channel),
        ).fetchone()


def save_message(
    conversation_id: str,
    direction: str,
    body: str,
    *,
    provider: str | None = None,
    provider_message_id: str | None = None,
    message_type: str = "text",
    delivery_status: str = "received",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Guarda mensajes; el ID externo único permite deduplicar reintentos de webhooks."""
    with connection() as conn:
        row = conn.execute(
            """
            INSERT INTO messages
              (conversation_id, direction, body, provider, provider_message_id,
               message_type, delivery_status, metadata)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb)
            ON CONFLICT (provider, provider_message_id)
              WHERE provider IS NOT NULL AND provider_message_id IS NOT NULL
            DO NOTHING
            RETURNING *
            """,
            (
                conversation_id, direction, body, provider, provider_message_id,
                message_type, delivery_status,
                json.dumps(metadata or {}, ensure_ascii=False),
            ),
        ).fetchone()
        if row:
            conn.execute(
                "UPDATE conversations SET last_message_at = NOW(), updated_at = NOW() WHERE id = %s",
                (conversation_id,),
            )
        return row


def set_conversation_mode(
    conversation_id: str,
    mode: str,
    *,
    actor: str,
    assigned_to: str | None = None,
) -> dict[str, Any]:
    """Cambia el control entre bot_active, human y closed y deja auditoría."""
    if mode not in {"bot_active", "human", "closed"}:
        raise ValueError("mode debe ser bot_active, human o closed")
    details = {"mode": mode, "assigned_to": assigned_to}
    with connection() as conn:
        row = conn.execute(
            """
            UPDATE conversations
            SET status = %s, assigned_to = %s, updated_at = NOW()
            WHERE id = %s RETURNING *
            """,
            (mode, assigned_to if mode == "human" else None, conversation_id),
        ).fetchone()
        if not row:
            raise ValueError("Conversación no encontrada")
        conn.execute(
            """
            INSERT INTO audit_log (conversation_id, actor, action, details)
            VALUES (%s, %s, 'conversation.mode_changed', %s::jsonb)
            """,
            (conversation_id, actor, json.dumps(details)),
        )
        return row


def create_pending_order(
    conversation_id: str,
    contact_id: str,
    items: list[dict[str, Any]],
    *,
    customer_name: str | None = None,
    delivery_method: str | None = None,
    delivery_address: str | None = None,
    customer_notes: str | None = None,
) -> dict[str, Any]:
    """Crea un pedido pendiente; nunca descuenta stock ni confirma disponibilidad.

    Cada item: product_id, product_name, quantity, unit_price, availability.
    Los precios y nombres deben provenir de la API de catálogo, no de la IA.
    """
    if not items:
        raise ValueError("El pedido debe contener al menos un producto")
    allowed = {"available_in_catalog", "out_of_stock", "confirm", "no_data"}
    subtotal = 0
    normalized = []
    for item in items:
        quantity = int(item["quantity"])
        if quantity <= 0:
            raise ValueError("La cantidad debe ser mayor que cero")
        price = item.get("unit_price")
        if price is not None and int(price) < 0:
            raise ValueError("El precio no puede ser negativo")
        availability = item.get("availability", "confirm")
        if availability not in allowed:
            raise ValueError("Estado de disponibilidad inválido")
        if price is not None:
            subtotal += int(price) * quantity
        normalized.append((str(item["product_id"]), str(item["product_name"]), quantity,
                           int(price) if price is not None else None, availability))
    with connection() as conn:
        order = conn.execute(
            """
            INSERT INTO orders
              (conversation_id, contact_id, status, customer_name, delivery_method,
               delivery_address, customer_notes, subtotal)
            VALUES (%s, %s, 'pending_confirmation', %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (conversation_id, contact_id, customer_name, delivery_method,
             delivery_address, customer_notes, subtotal),
        ).fetchone()
        for product_id, product_name, quantity, unit_price, availability in normalized:
            conn.execute(
                """
                INSERT INTO order_items
                  (order_id, product_id, product_name_snapshot, quantity, unit_price, availability_snapshot)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (order["id"], product_id, product_name, quantity, unit_price, availability),
            )
        conn.execute(
            """
            INSERT INTO audit_log (conversation_id, actor, action, details)
            VALUES (%s, 'system', 'order.created_pending',
                    jsonb_build_object('order_id', %s::text, 'items', %s))
            """,
            (conversation_id, str(order["id"]), len(normalized)),
        )
        return order
