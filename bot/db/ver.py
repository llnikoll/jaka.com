# bot/db/ver.py
"""Lo que el bot armó, para mirarlo desde la terminal.

El bot no confirma ventas: deja los pedidos en `pending_confirmation` y los turnos en
`pendiente`. Esto los muestra para que el dueño del taller los revise y siga la
conversación él.

    python -m bot.db.ver
    python -m bot.db.ver --pedidos 50
    python -m bot.db.ver --estado confirmed
"""
from __future__ import annotations

import argparse
import os
import sys

from bot.db import repository


def _gs(valor) -> str:
    if valor is None:
        return "a consultar"
    return f"Gs. {int(valor):,}".replace(",", ".")


def _fecha(valor) -> str:
    return valor.strftime("%d/%m/%Y") if hasattr(valor, "strftime") else str(valor)


def _quien(registro: dict) -> str:
    """'Ana (+595...)', o sólo el teléfono si no hay nombre."""
    nombre = (registro.get("display_name") or "").strip()
    telefono = registro.get("phone_e164") or "sin teléfono"
    return f"{nombre} ({telefono})" if nombre else telefono


def mostrar_pedidos(status: str, limite: int) -> int:
    pedidos = repository.listar_pedidos(status, limite)
    if not pedidos:
        print(f"No hay pedidos en estado '{status}'.")
        return 0

    print(f"\n{len(pedidos)} pedido(s) en estado '{status}':\n")
    for pedido in pedidos:
        print(f"  {_fecha(pedido['created_at'])}  {_quien(pedido)}")
        for item in pedido["items"]:
            precio = _gs(item["unit_price"])
            print(
                f"      {item['quantity']} x {item['product_name_snapshot']} — {precio}"
                f"   [{item['availability_snapshot']}]"
            )
        print(f"      Total: {_gs(pedido['subtotal'])}   id: {pedido['id']}")
        print()
    return len(pedidos)


def mostrar_turnos() -> int:
    from bot.db import repository as repo

    # listar_turnos pide un contacto, así que acá se consultan todos.
    with repo.connection() as conn:
        turnos = conn.execute(
            """
            SELECT t.fecha, t.servicio, t.estado, c.phone_e164, c.display_name
            FROM turnos t
            JOIN contacts c ON c.id = t.contact_id
            WHERE t.estado = 'pendiente' AND t.fecha >= CURRENT_DATE
            ORDER BY t.fecha
            """
        ).fetchall()

    if not turnos:
        print("\nNo hay turnos pendientes.")
        return 0

    print(f"\n{len(turnos)} turno(s) pendiente(s):\n")
    for turno in turnos:
        print(f"  {_fecha(turno['fecha'])}  {turno['servicio']:<10}  {_quien(turno)}")
    print()
    return len(turnos)


def main() -> int:
    parser = argparse.ArgumentParser(description="Ver pedidos y turnos del chatbot")
    parser.add_argument("--estado", default="pending_confirmation",
                        help="Estado del pedido (pending_confirmation, confirmed, rejected, cancelled)")
    parser.add_argument("--pedidos", type=int, default=20, help="Cuántos pedidos mostrar")
    parser.add_argument("--sin-turnos", action="store_true", help="No mostrar turnos")
    args = parser.parse_args()

    if not os.getenv("DATABASE_URL", "").strip():
        print(
            "Falta DATABASE_URL.\n"
            "Ejemplo:\n"
            '  $env:DATABASE_URL = "postgresql://jaka_bot:TU_CLAVE@127.0.0.1:5432/jaka_chatbot"',
            file=sys.stderr,
        )
        return 1

    if getattr(repository, "psycopg", None) is None:
        print(
            "Falta psycopg. Instalá: py -3 -m pip install -r bot/db/requirements.txt",
            file=sys.stderr,
        )
        return 1

    mostrar_pedidos(args.estado, args.pedidos)
    if not args.sin_turnos:
        mostrar_turnos()
    return 0


if __name__ == "__main__":
    sys.exit(main())
