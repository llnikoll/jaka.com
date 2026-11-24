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


# Valores aceptados por orders.delivery_method en schema.sql.
DELIVERY_METHODS = {"pickup", "delivery", "to_coordinate"}


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
    if delivery_method is not None and delivery_method not in DELIVERY_METHODS:
        # Sin esto, un "envio" del asistente llegaba hasta el CHECK de la tabla y salía
        # como CheckViolation de psycopg, que no dice nada útil sobre qué corregir.
        raise ValueError(
            "delivery_method debe ser pickup, delivery o to_coordinate"
        )
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


# ─────────────────────────────────────────────────────────────────────────
# Lectura del historial (lo que el asistente necesita para tener contexto)
# ─────────────────────────────────────────────────────────────────────────


def get_recent_messages(
    conversation_id: str,
    limit: int = 20,
    *,
    include_internal: bool = False,
) -> list[dict[str, Any]]:
    """
    Los últimos `limit` mensajes de una conversación, del más viejo al más nuevo.

    Devuelve en orden cronológico a propósito: el orden inverso (de más nuevo a más
    viejo) es cómodo para la consulta pero incómodo para armar el contexto del modelo,
    y es el error clásico al conectar esto. El recorte a `limit` sí se hace por el final.

    `include_internal` deja afuera los mensajes con direction='internal' (notas del
    dueño, por ejemplo): el asistente no debe leer sus propias notas de trabajo.

    Se ordena por `created_at` y se desempata con `id` para que dos mensajes guardados
    en el mismo instante salgan siempre en el mismo orden. El id es un UUID, así que no
    representa el orden real de llegada; si algún día importa, hace falta una columna
    serial en `messages`.
    """
    try:
        limite = max(1, min(int(limit), 200))
    except (TypeError, ValueError):
        raise ValueError("limit debe ser un número entre 1 y 200")

    with connection() as conn:
        filas = conn.execute(
            """
            SELECT id, direction, body, message_type, delivery_status, created_at
            FROM messages
            WHERE conversation_id = %s
              AND (%s::boolean OR direction <> 'internal')
            ORDER BY created_at DESC, id DESC
            LIMIT %s
            """,
            (conversation_id, include_internal, limite),
        ).fetchall()

    return list(reversed(filas))


def get_conversation_history(
    contact_id: str,
    channel: str = "whatsapp",
    limit: int = 20,
    *,
    include_internal: bool = False,
) -> dict[str, Any]:
    """
    La conversación abierta del contacto y sus últimos mensajes.

    Es la llamada que hace el asistente al recibir un mensaje: una sola función que
    resuelve a qué conversación pertenece y qué se dijeron antes.

    Si el contacto todavía no tiene conversación abierta, devuelve
    {"conversation": None, "messages": []} en vez de crear una: leer no debe escribir.
    """
    with connection() as conn:
        conversacion = conn.execute(
            """
            SELECT * FROM conversations
            WHERE contact_id = %s AND channel = %s AND status <> 'closed'
            ORDER BY updated_at DESC
            LIMIT 1
            """,
            (contact_id, channel),
        ).fetchone()

    if conversacion is None:
        return {"conversation": None, "messages": []}

    return {
        "conversation": conversacion,
        "messages": get_recent_messages(
            conversacion["id"], limit, include_internal=include_internal
        ),
    }


# ─────────────────────────────────────────────────────────────────────────
# Pedidos: lectura y cambio de estado
# ─────────────────────────────────────────────────────────────────────────

# Estados posibles de un pedido (deben coincidir con el CHECK de orders.status).
ORDER_STATUSES = ("pending_confirmation", "confirmed", "rejected", "cancelled")

# A qué estados se puede pasar desde cada uno. Los estados finales no vuelven atrás:
# un pedido rechazado o cancelado no se "des-cancela", se crea uno nuevo, así queda
# la traza de qué pasó.
ORDER_TRANSITIONS: dict[str, set[str]] = {
    "pending_confirmation": {"confirmed", "rejected", "cancelled"},
    "confirmed": {"cancelled"},
    "rejected": set(),
    "cancelled": set(),
}


def get_order(order_id: str) -> dict[str, Any]:
    """Un pedido con sus renglones. Lanza ValueError si no existe."""
    with connection() as conn:
        pedido = conn.execute("SELECT * FROM orders WHERE id = %s", (order_id,)).fetchone()
        if pedido is None:
            raise ValueError("Pedido no encontrado")
        pedido["items"] = conn.execute(
            """
            SELECT id, product_id, product_name_snapshot, quantity, unit_price,
                   availability_snapshot
            FROM order_items
            WHERE order_id = %s
            ORDER BY created_at, id
            """,
            (order_id,),
        ).fetchall()
        return pedido


def set_order_status(
    order_id: str,
    status: str,
    *,
    actor: str,
    reason: str | None = None,
) -> dict[str, Any]:
    """
    Confirma, rechaza o cancela un pedido, y deja constancia en la auditoría.

    No descuenta stock ni cobra nada: el pedido es un registro comercial, la venta se
    cierra por WhatsApp. Sí bloquea la fila con FOR UPDATE para que dos operadores que
    confirman al mismo tiempo no se pisen ni generen dos eventos de auditoría
    contradictorios.

    Volver a poner el estado que ya tiene es idempotente (no falla ni duplica auditoría):
    un reintento de n8n no debería romper.
    """
    if status not in ORDER_STATUSES:
        raise ValueError(f"status debe ser uno de: {', '.join(ORDER_STATUSES)}")

    with connection() as conn:
        pedido = conn.execute(
            "SELECT * FROM orders WHERE id = %s FOR UPDATE", (order_id,)
        ).fetchone()
        if pedido is None:
            raise ValueError("Pedido no encontrado")

        actual = pedido["status"]
        if status == actual:
            return pedido

        permitidos = ORDER_TRANSITIONS.get(actual, set())
        if status not in permitidos:
            opciones = ", ".join(sorted(permitidos)) or "ninguno (estado final)"
            raise ValueError(
                f"No se puede pasar un pedido de '{actual}' a '{status}'. "
                f"Desde '{actual}' solo se puede pasar a: {opciones}."
            )

        actualizado = conn.execute(
            "UPDATE orders SET status = %s, updated_at = NOW() WHERE id = %s RETURNING *",
            (status, order_id),
        ).fetchone()

        detalles = {
            "order_id": str(order_id),
            "from": actual,
            "to": status,
            "reason": reason,
        }
        conn.execute(
            """
            INSERT INTO audit_log (conversation_id, actor, action, details)
            VALUES (%s, %s, 'order.status_changed', %s::jsonb)
            """,
            (pedido["conversation_id"], actor, json.dumps(detalles, ensure_ascii=False)),
        )
        return actualizado
