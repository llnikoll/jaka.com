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


def hay_ia() -> bool:
    """True si hay clave configurada. El servicio igual arranca sin ella (modo seco)."""
    return bool(GEMINI_API_KEY)
