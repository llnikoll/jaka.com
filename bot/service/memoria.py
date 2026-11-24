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
