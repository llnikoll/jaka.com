# bot/service/negocio.py
"""Datos comerciales del negocio, leídos de la configuración de la tienda.

Se leen de `tienda/assets/config.js` para no duplicar el WhatsApp, la dirección ni
las notas de envío en dos lugares: si el dueño cambia el número en la tienda, el
chatbot dice el número nuevo sin tocar código.

Se cachea por fecha de modificación, así el cambio se toma sin reiniciar.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

RUTA_CONFIG = Path(__file__).resolve().parents[2] / "tienda" / "assets" / "config.js"

_cache: tuple[float, dict] | None = None


def _texto(fuente: str, clave: str) -> str:
    m = re.search(rf'\b{clave}\s*:\s*"([^"]*)"', fuente)
    return m.group(1).strip() if m else ""


def _bloque(fuente: str, clave: str) -> str:
    """Extrae el texto de un sub-objeto simple tipo `envio: { ... nota: "..." }`."""
    m = re.search(rf"\b{clave}\s*:\s*\{{(.*?)\}}", fuente, re.S)
    return m.group(1) if m else ""


def cargar() -> dict:
    """Datos del negocio listos para mostrarle al cliente."""
    global _cache

    try:
        mtime = RUTA_CONFIG.stat().st_mtime
    except OSError:
        return {}

    if _cache is not None and _cache[0] == mtime:
        return _cache[1]

    try:
        fuente = RUTA_CONFIG.read_text(encoding="utf-8")
    except OSError:
        return _cache[1] if _cache else {}

    datos = {
        "nombre": _texto(fuente, "marca") or "Jaka Bicicletería",
        "whatsapp": _texto(fuente, "whatsappVisible") or _texto(fuente, "whatsapp"),
        "whatsapp_numeros": _texto(fuente, "whatsapp"),
        "ubicacion": _texto(fuente, "ubicacion"),
        "nota_envio": _texto(_bloque(fuente, "envio"), "nota"),
        "nota_retiro": _texto(_bloque(fuente, "retiro"), "nota"),
    }
    _cache = (mtime, datos)
    return datos


def resumen_para_prompt() -> str:
    """Bloque de datos fijos que se le pasa al modelo en cada llamada."""
    d = cargar()
    if not d:
        return ""
    lineas = [
        f"Negocio: {d['nombre']} (Capiatá, Paraguay).",
        "Horario: lunes a sábado de 8:00 a 18:00.",
    ]
    if d.get("whatsapp"):
        lineas.append(f"WhatsApp: {d['whatsapp']}.")
    if d.get("ubicacion"):
        lineas.append(f"Ubicación: {d['ubicacion']}.")
    if d.get("nota_envio"):
        lineas.append(f"Envíos: {d['nota_envio']}")
    if d.get("nota_retiro"):
        lineas.append(f"Retiro: {d['nota_retiro']}")
    return "\n".join(lineas)


def como_json() -> str:
    return json.dumps(cargar(), ensure_ascii=False)
