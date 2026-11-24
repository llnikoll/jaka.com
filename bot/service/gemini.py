# bot/service/gemini.py
"""Cliente mínimo de la API de Gemini, sin SDK.

Se habla directo con el endpoint REST por tres razones: no agrega dependencias al
repo, deja ver exactamente qué se le manda al modelo y permite manejar los errores
de cuota con reintentos propios.

Decisiones que importan:

- `thinkingConfig.thinkingBudget = 0`. Los modelos actuales razonan antes de
  contestar y ese razonamiento se descuenta de `maxOutputTokens`: con el presupuesto
  por defecto, una respuesta corta se cortaba a la mitad ("Una bicicleta MTB (").
  Para clasificar intenciones y redactar mensajes de WhatsApp no hace falta que piense.
- Se reintenta con espera creciente sólo ante 429 (cuota) y 503 (demanda). Un 400 por
  esquema inválido no se reintenta: no se arregla solo.
- El esquema de respuesta no puede tener cadenas vacías en un enum; Gemini devuelve
  400. Por eso los enums llevan siempre un valor concreto.
"""
from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.request

from bot.service import config

logger = logging.getLogger("jaka.gemini")

BASE = "https://generativelanguage.googleapis.com/v1beta/models"

# Errores en los que tiene sentido reintentar.
REINTENTABLES = {429, 500, 502, 503, 504}


class ErrorGemini(RuntimeError):
    """Falla al hablar con el modelo, con un mensaje que se puede mostrar."""


def _pedir(url: str, payload: dict, timeout: float) -> dict:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": config.GEMINI_API_KEY,
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as respuesta:
        return json.loads(respuesta.read().decode("utf-8"))


def _texto(respuesta: dict) -> str:
    candidatos = respuesta.get("candidates") or [{}]
    partes = (candidatos[0].get("content") or {}).get("parts") or []
    return "".join(p.get("text", "") for p in partes).strip()


def generar(
    sistema: str,
    mensajes: list[dict],
    *,
    esquema: dict | None = None,
    temperatura: float = 0.3,
    max_tokens: int = 400,
    timeout: float = 20.0,
    reintentos: int = 1,
) -> str:
    """
    Una llamada al modelo y devuelve el texto.

    `mensajes` es [{"role": "user"|"assistant", "content": "..."}]. En Gemini los
    turnos del asistente se llaman "model", así que se traduce acá.

    Los valores por defecto son cortos a propósito: esto atiende un chat. Un caso
    aislado tardó 43 s por un 503 que se reintentó en silencio; con estos valores el
    peor caso queda en ~25 s y, sobre todo, el reintento se ve en el log.
    """
    if not config.GEMINI_API_KEY:
        raise ErrorGemini(
            "Falta GEMINI_API_KEY. Ponela en bot/service/.env o en el entorno."
        )

    contenidos = [
        {"role": "model" if m["role"] == "assistant" else "user", "parts": [{"text": m["content"]}]}
        for m in mensajes
        if (m.get("content") or "").strip()
    ]
    if not contenidos:
        raise ErrorGemini("No hay ningún mensaje para enviar al modelo.")

    generacion: dict = {
        "temperature": temperatura,
        "maxOutputTokens": max_tokens,
        "thinkingConfig": {"thinkingBudget": 0},
    }
    if esquema:
        generacion["responseMimeType"] = "application/json"
        generacion["responseSchema"] = esquema

    payload = {
        "contents": contenidos,
        "systemInstruction": {"parts": [{"text": sistema}]},
        "generationConfig": generacion,
    }
    url = f"{BASE}/{config.GEMINI_MODEL}:generateContent"

    ultimo_error = ""
    for intento in range(reintentos + 1):
        arranque = time.time()
        try:
            respuesta = _pedir(url, payload, timeout)
            texto = _texto(respuesta)
            if not texto:
                motivo = (respuesta.get("candidates") or [{}])[0].get("finishReason")
                raise ErrorGemini(f"El modelo devolvió una respuesta vacía (motivo: {motivo}).")
            logger.info(
                f"Gemini {config.GEMINI_MODEL}: {time.time() - arranque:.1f}s "
                f"(intento {intento + 1})"
            )
            return texto
        except urllib.error.HTTPError as e:
            cuerpo = e.read().decode("utf-8", "replace")
            ultimo_error = _mensaje_de_error(e.code, cuerpo)
            if e.code not in REINTENTABLES or intento == reintentos:
                raise ErrorGemini(ultimo_error) from e
            logger.warning(f"Gemini {e.code} en el intento {intento + 1}; se reintenta")
        except urllib.error.URLError as e:
            ultimo_error = f"No se pudo contactar a Gemini: {e.reason}"
            if intento == reintentos:
                raise ErrorGemini(ultimo_error) from e
            logger.warning(f"Error de red en el intento {intento + 1}; se reintenta")
        except TimeoutError:
            ultimo_error = "Gemini tardó demasiado en responder."
            if intento == reintentos:
                raise ErrorGemini(ultimo_error)
            logger.warning(f"Timeout en el intento {intento + 1}; se reintenta")

        time.sleep(1.5 * (intento + 1))

    raise ErrorGemini(ultimo_error or "Fallo desconocido al llamar a Gemini.")


def _mensaje_de_error(codigo: int, cuerpo: str) -> str:
    """Traduce el error de Google a algo accionable."""
    try:
        detalle = json.loads(cuerpo)["error"]["message"]
    except (ValueError, KeyError, TypeError):
        detalle = cuerpo[:300]

    if codigo == 429:
        return f"Se agotó la cuota gratuita de Gemini por ahora. Probá en un rato. ({detalle})"
    if codigo in (401, 403):
        return f"La GEMINI_API_KEY no es válida o no tiene permiso. ({detalle})"
    if codigo == 404:
        return f"El modelo '{config.GEMINI_MODEL}' no está disponible. ({detalle})"
    if codigo == 503:
        return f"Gemini está saturado; se reintentó y siguió sin responder. ({detalle})"
    return f"Gemini devolvió {codigo}: {detalle}"


def generar_json(sistema: str, mensajes: list[dict], esquema: dict, **kwargs) -> dict:
    """Igual que generar(), pero parsea el JSON y falla claro si vino mal."""
    texto = generar(sistema, mensajes, esquema=esquema, temperatura=0, **kwargs)
    try:
        datos = json.loads(texto)
    except ValueError as e:
        raise ErrorGemini(f"El modelo no devolvió JSON válido: {texto[:200]}") from e
    if not isinstance(datos, dict):
        raise ErrorGemini(f"El modelo devolvió un JSON que no es un objeto: {texto[:200]}")
    return datos
