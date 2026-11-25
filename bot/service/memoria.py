# bot/service/memoria.py
"""Historial de la conversación: PostgreSQL si está configurado, memoria si no.

El servicio tiene que poder probarse sin base de datos —quien recién clona el repo
no tiene PostgreSQL levantado— así que si falta `DATABASE_URL` guarda el historial
en un diccionario del proceso. Alcanza para probar en local y se pierde al cerrar,
que es exactamente lo que se espera de un modo de prueba.

Con base de datos usa `bot/db/repository.py`, la misma capa ya validada: contactos,
conversaciones, mensajes deduplicados y auditoría.
"""
from __future__ import annotations

import logging
import os
import time
from collections import defaultdict

logger = logging.getLogger("jaka.memoria")

try:
    from bot.db import repository
except ImportError:  # pragma: no cover
    repository = None

_en_memoria: dict[str, list[dict]] = defaultdict(list)

# Cuántos mensajes se conservan por teléfono en el modo sin base.
MAX_MEMORIA = 40


def hay_base() -> bool:
    """
    True si hay DATABASE_URL, la capa de repositorio y el driver psycopg.

    Se comprueba el driver a propósito: `repository` se importa igual sin psycopg
    (para poder mostrar un error claro al usarlo), así que mirar solo el import hacía
    que el health check dijera "postgresql" cuando en realidad no había forma de
    conectar. El chat seguía funcionando, pero con el historial en memoria y sin que
    se notara.
    """
    if not os.getenv("DATABASE_URL", "").strip() or repository is None:
        return False
    return getattr(repository, "psycopg", None) is not None


def motivo_sin_base() -> str:
    """Explicación corta de por qué no hay base, para el health check."""
    if not os.getenv("DATABASE_URL", "").strip():
        return "falta DATABASE_URL"
    if repository is None:
        return "no se pudo importar bot.db.repository"
    return "falta psycopg: py -3 -m pip install -r bot/db/requirements.txt"


def _rol(direccion: str) -> str:
    """direction de la base -> role que espera el modelo."""
    return "user" if direccion == "inbound" else "assistant"


def contexto(telefono: str, limite: int) -> list[dict]:
    """Los últimos mensajes de esa conversación, en orden cronológico."""
    if not hay_base():
        return list(_en_memoria[telefono][-limite:])

    try:
        contacto = repository.get_or_create_contact(telefono)
        repository.get_or_create_conversation(contacto["id"])
        historial = repository.get_conversation_history(contacto["id"], limit=limite)
        return [
            {"role": _rol(m["direction"]), "content": m["body"]}
            for m in historial.get("messages", [])
            if m.get("direction") in ("inbound", "outbound")
        ]
    except Exception as e:  # noqa: BLE001
        # La conversación no se cae porque la base falle: se sigue en memoria y se avisa.
        logger.error(f"No se pudo leer el historial de {telefono}: {e}. Se usa memoria.")
        return list(_en_memoria[telefono][-limite:])


def guardar(telefono: str, mensaje_usuario: str, respuesta: str) -> None:
    """Guarda el turno completo: lo que dijo el cliente y lo que contestó el bot."""
    _en_memoria[telefono].append({"role": "user", "content": mensaje_usuario})
    _en_memoria[telefono].append({"role": "assistant", "content": respuesta})
    if len(_en_memoria[telefono]) > MAX_MEMORIA:
        del _en_memoria[telefono][:-MAX_MEMORIA]

    if not hay_base():
        return

    try:
        contacto = repository.get_or_create_contact(telefono)
        conversacion = repository.get_or_create_conversation(contacto["id"])
        externo = f"local:{telefono}:{int(time.time() * 1000)}"
        repository.save_message(
            conversacion["id"], "inbound", mensaje_usuario,
            provider="local", provider_message_id=externo,
        )
        repository.save_message(
            conversacion["id"], "outbound", respuesta,
            provider="local", provider_message_id=externo + ":out",
            delivery_status="sent",
        )
    except Exception as e:  # noqa: BLE001
        logger.error(f"No se pudo guardar la conversación de {telefono} en la base: {e}")


def limpiar(telefono: str) -> None:
    """Borra el historial en memoria de ese teléfono (para reiniciar una prueba)."""
    _en_memoria.pop(telefono, None)


# ─────────────────────────────────────────────────────────────────────────
# Acciones con efecto: pedidos, turnos y cambio de modo
# ─────────────────────────────────────────────────────────────────────────


def _ids(telefono: str) -> dict | None:
    """Contacto y conversación abierta de ese teléfono, o None si no hay base."""
    if not hay_base():
        return None
    contacto = repository.get_or_create_contact(telefono)
    conversacion = repository.get_or_create_conversation(contacto["id"])
    return {"contact_id": contacto["id"], "conversation_id": conversacion["id"]}


def crear_pedido(telefono: str, lineas: list[dict]) -> dict | None:
    """
    Guarda el pedido como pendiente de confirmación.

    Devuelve None si no hay base o si falló: el asistente usa eso para avisarle al
    cliente que escriba al taller en vez de dar por hecho que quedó registrado.
    """
    try:
        ids = _ids(telefono)
        if not ids:
            logger.warning(f"Pedido de {telefono} no guardado: no hay base de datos")
            return None
        items = [
            {
                "product_id": linea["producto"]["id"],
                "product_name": linea["producto"]["nombre"],
                "quantity": linea["cantidad"],
                "unit_price": linea["producto"].get("precio_valor"),
                "availability": linea["producto"].get("disponibilidad_codigo") or "confirm",
            }
            for linea in lineas
        ]
        pedido = repository.create_pending_order(
            ids["conversation_id"], ids["contact_id"], items
        )
        logger.info(f"Pedido {pedido['id']} creado para {telefono} ({len(items)} ítems)")
        return pedido
    except Exception as e:  # noqa: BLE001
        logger.error(f"No se pudo crear el pedido de {telefono}: {e}")
        return None


def crear_turno(telefono: str, servicio: str, fecha) -> dict | None:
    """Guarda el turno de taller. Mismo criterio que crear_pedido: None si no se pudo."""
    try:
        ids = _ids(telefono)
        if not ids:
            logger.warning(f"Turno de {telefono} no guardado: no hay base de datos")
            return None
        turno = repository.crear_turno(
            ids["conversation_id"], ids["contact_id"], servicio, fecha
        )
        logger.info(f"Turno {turno['id']} creado para {telefono}: {servicio} {fecha}")
        return turno
    except Exception as e:  # noqa: BLE001
        logger.error(f"No se pudo crear el turno de {telefono}: {e}")
        return None


def marcar_humano(telefono: str) -> bool:
    """
    Pasa la conversación a una persona.

    Se usa después de armar un pedido: el bot no cierra ventas. En modo memoria no hay
    dónde anotarlo, así que sólo se registra en el log.
    """
    try:
        ids = _ids(telefono)
        if not ids:
            logger.info(f"[{telefono}] pedido de atención humana (sin base, no se persiste)")
            return False
        repository.set_conversation_mode(
            ids["conversation_id"], "human", actor="bot"
        )
        logger.info(f"[{telefono}] conversación derivada a una persona")
        return True
    except Exception as e:  # noqa: BLE001
        logger.error(f"No se pudo derivar la conversación de {telefono}: {e}")
        return False
