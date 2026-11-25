# bot/service/config.py
"""Configuración del servicio del chatbot.

Lee `bot/service/.env` sin depender de python-dotenv, para que el servicio siga
levantándose solo con la biblioteca estándar. Las variables ya definidas en el
entorno real tienen prioridad sobre el archivo: así se puede probar sin tocar el
.env y en producción se usan las del proceso.
"""
from __future__ import annotations

import os
from pathlib import Path

CARPETA = Path(__file__).resolve().parent
RAIZ = CARPETA.parents[1]
RUTA_ENV = CARPETA / ".env"


def cargar_env(ruta: Path = RUTA_ENV) -> list[str]:
    """Carga el .env. Devuelve las claves que leyó (sin los valores)."""
    if not ruta.exists():
        return []
    leidas = []
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        limpia = linea.strip()
        if not limpia or limpia.startswith("#") or "=" not in limpia:
            continue
        clave, valor = limpia.split("=", 1)
        clave = clave.strip()
        if not clave:
            continue
        os.environ.setdefault(clave, valor.strip())
        leidas.append(clave)
    return leidas


cargar_env()

# Proveedor de IA. El modelo elegido está medido: los Flash grandes tardan 17-35 s
# o devuelven 503 por demanda; el lite responde en 1-3 s, que es lo que necesita un
# bot de WhatsApp. Se puede cambiar sin tocar código.
GEMINI_API_KEY = (os.getenv("GEMINI_API_KEY") or "").strip()
GEMINI_MODEL = (os.getenv("GEMINI_MODEL") or "").strip() or "gemini-3.1-flash-lite"

# API de catálogo (etapa 1), corriendo en local.
CATALOG_API_URL = (os.getenv("CATALOG_API_URL") or "http://127.0.0.1:8787").rstrip("/")

# Servidor del propio servicio.
SERVICE_HOST = (os.getenv("SERVICE_HOST") or "127.0.0.1").strip()
SERVICE_PORT = int(os.getenv("SERVICE_PORT") or "8790")

# Cuántos mensajes previos se le pasan al modelo como contexto.
MAX_HISTORIAL = int(os.getenv("MAX_HISTORIAL") or "10")

# Cuántos productos se le muestran al modelo para redactar. Más de 5 lo confunde
# y encarece la llamada.
MAX_PRODUCTOS_CONTEXTO = 5

# ── WhatsApp Cloud API ────────────────────────────────────────────────
# Las cuatro son de la app de Meta. Sin ellas el servicio igual arranca: el chat local
# sigue funcionando y el webhook responde 503 con el detalle.
META_VERIFY_TOKEN = (os.getenv("META_VERIFY_TOKEN") or "jaka-bici-2026").strip()
META_APP_SECRET = (os.getenv("META_APP_SECRET") or "").strip()
META_ACCESS_TOKEN = (os.getenv("META_ACCESS_TOKEN") or "").strip()
META_PHONE_NUMBER_ID = (os.getenv("META_PHONE_NUMBER_ID") or "").strip()
META_API_VERSION = (os.getenv("META_API_VERSION") or "v25.0").strip()


def hay_ia() -> bool:
    """True si hay clave configurada. El servicio igual arranca sin ella (modo seco)."""
    return bool(GEMINI_API_KEY)


def whatsapp_configurado() -> bool:
    """True si están las tres credenciales que hacen falta para mandar mensajes."""
    return bool(META_ACCESS_TOKEN and META_PHONE_NUMBER_ID and META_APP_SECRET)


def falta_para_whatsapp() -> str:
    """Qué variable falta, para poder decirlo en el health check."""
    faltan = [
        nombre
        for nombre, valor in (
            ("META_ACCESS_TOKEN", META_ACCESS_TOKEN),
            ("META_PHONE_NUMBER_ID", META_PHONE_NUMBER_ID),
            ("META_APP_SECRET", META_APP_SECRET),
        )
        if not valor
    ]
    return ", ".join(faltan) if faltan else ""
