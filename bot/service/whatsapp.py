# bot/service/whatsapp.py
"""Adaptador de WhatsApp Cloud API.

Todo lo que hay entre Meta y el asistente:

  Meta → POST /webhook → verificar firma → normalizar → asistente → respuesta (+foto)

Tres cosas que no son obvias y están resueltas acá:

1. **Se contesta 200 antes de pensar.** Meta espera respuesta en unos 5 segundos y
   reintenta hasta 7 veces si no la recibe. Llamar al modelo tarda 2-3 segundos, así que
   el servidor responde de inmediato y procesa en segundo plano.

2. **Deduplicación.** Esos reintentos traen el mismo mensaje otra vez. Se descarta por
   id antes de procesar, y además el repositorio tiene un índice único por id externo
   como respaldo durable.

3. **La firma.** Sin verificar `X-Hub-Signature-256` cualquiera puede mandarle mensajes
   falsos al webhook. Si no hay App Secret configurado se acepta todo y se avisa en el
   log: sirve para probar, no para dejar así.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import urllib.error
import urllib.request
from collections import OrderedDict

from bot.service import asistente, config

logger = logging.getLogger("jaka.whatsapp")

GRAFO = "https://graph.facebook.com"

# Cuántos ids de mensaje se recuerdan para descartar reintentos. Meta reintenta hasta
# 7 veces un mismo evento; con 2000 alcanza de sobra para una ventana de minutos.
MAX_RECORDADOS = 2000
_vistos: OrderedDict[str, None] = OrderedDict()


# ─────────────────────────────────────────────────────────────────────────
# Firma y normalización
# ─────────────────────────────────────────────────────────────────────────


def verificar_firma(cuerpo: bytes, cabecera: str | None) -> bool:
    """
    Compara X-Hub-Signature-256 contra el HMAC-SHA256 del cuerpo crudo.

    Se firma el cuerpo crudo, no el JSON re-serializado: cualquier diferencia de
    espacios o de orden de claves cambia el hash y la verificación fallaría siempre.
    """
    if not config.META_APP_SECRET:
        logger.warning("META_APP_SECRET sin configurar: los webhooks NO se verifican")
        return True

    if not cabecera or not cabecera.startswith("sha256="):
        logger.warning("Llegó un webhook sin firma válida: rechazado")
        return False

    esperada = hmac.new(
        config.META_APP_SECRET.encode("utf-8"), cuerpo, hashlib.sha256
    ).hexdigest()

    # compare_digest sobre str exige ASCII puro: un header con bytes raros tiraría
    # TypeError y el handler devolvería 500 en vez de 401.
    try:
        return hmac.compare_digest(esperada, cabecera.removeprefix("sha256="))
    except TypeError:
        logger.warning("La firma del webhook trae caracteres inválidos: rechazado")
        return False


def normalizar_telefono(numero: str) -> str:
    """
    Meta manda '595995622412'; la base guarda E.164 ('+595995622412').

    Sin el '+' el INSERT choca contra el CHECK de la tabla de contactos, y el pedido o
    el turno se pierden sin que el cliente entienda por qué.
    """
    limpio = str(numero or "").strip().replace(" ", "").replace("-", "")
    if not limpio:
        return ""
    return limpio if limpio.startswith("+") else "+" + limpio


def extraer_mensajes(payload: dict) -> list[dict]:
    """Saca los mensajes de texto del payload anidado de Meta."""
    mensajes = []
    for entrada in payload.get("entry") or []:
        for cambio in entrada.get("changes") or []:
            valor = cambio.get("value") or {}
            for mensaje in valor.get("messages") or []:
                if mensaje.get("type") != "text":
                    continue  # por ahora sólo texto: audio y fotos quedan para después
                texto = (mensaje.get("text") or {}).get("body") or ""
                telefono = normalizar_telefono(mensaje.get("from"))
                if not telefono or not texto.strip():
                    continue
                mensajes.append(
                    {
                        "telefono": telefono,
                        "texto": texto.strip(),
                        "mensaje_id": mensaje.get("id") or "",
                    }
                )
    return mensajes


# ─────────────────────────────────────────────────────────────────────────
# Deduplicación
# ─────────────────────────────────────────────────────────────────────────


def ya_procesado(mensaje_id: str) -> bool:
    """True si ese mensaje ya se atendió (Meta reintenta el mismo evento)."""
    if not mensaje_id:
        return False
    if mensaje_id in _vistos:
        return True
    _vistos[mensaje_id] = None
    while len(_vistos) > MAX_RECORDADOS:
        _vistos.popitem(last=False)
    return False


def olvidar(mensaje_id: str) -> None:
    """Suelta un id para que el reintento de Meta sí se procese (se usó al fallar el envío)."""
    _vistos.pop(mensaje_id, None)


def limpiar_vistos() -> None:
    """Vacía la memoria de ids (para las pruebas)."""
    _vistos.clear()


# ─────────────────────────────────────────────────────────────────────────
# Envío
# ─────────────────────────────────────────────────────────────────────────


def _post_grafo(cuerpo: dict) -> tuple[bool, str]:
    if not config.META_ACCESS_TOKEN or not config.META_PHONE_NUMBER_ID:
        return False, "faltan META_ACCESS_TOKEN o META_PHONE_NUMBER_ID"

    url = f"{GRAFO}/{config.META_API_VERSION}/{config.META_PHONE_NUMBER_ID}/messages"
    pedido = urllib.request.Request(
        url,
        data=json.dumps(cuerpo).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {config.META_ACCESS_TOKEN}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(pedido, timeout=30) as respuesta:
            return respuesta.status == 200, ""
    except urllib.error.HTTPError as e:
        detalle = e.read().decode("utf-8", "replace")[:300]
        return False, f"{e.code}: {detalle}"
    except (urllib.error.URLError, TimeoutError) as e:
        return False, f"error de red: {e}"


def enviar_texto(telefono: str, texto: str) -> bool:
    ok, detalle = _post_grafo(
        {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": telefono.lstrip("+"),
            "type": "text",
            "text": {"preview_url": False, "body": texto},
        }
    )
    if not ok:
        logger.error(f"No se pudo enviar el texto a {telefono}: {detalle}")
    return ok


def enviar_imagen(telefono: str, url: str, pie: str = "") -> bool:
    """
    Manda la foto con el texto como pie.

    WhatsApp corta los pies de foto en 1024 caracteres. Las respuestas del bot son
    mucho más cortas, pero se recorta igual para no perder el mensaje entero por eso.
    """
    cuerpo = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": telefono.lstrip("+"),
        "type": "image",
        "image": {"link": url},
    }
    if pie:
        cuerpo["image"]["caption"] = pie[:1024]

    ok, detalle = _post_grafo(cuerpo)
    if not ok:
        logger.warning(f"No se pudo enviar la foto a {telefono}: {detalle}")
    return ok


def enviar_respuesta(telefono: str, resultado: dict) -> bool:
    """Manda la respuesta del asistente: con foto si hay, y si la foto falla, sólo texto."""
    texto = resultado.get("respuesta") or ""
    imagen = (resultado.get("imagen") or {}).get("url")
    if imagen and enviar_imagen(telefono, imagen, texto):
        return True
    return enviar_texto(telefono, texto)


# ─────────────────────────────────────────────────────────────────────────
# Atención de un webhook
# ─────────────────────────────────────────────────────────────────────────


def atender(payload: dict, *, responder=None, enviar=None, historial_de=None) -> list[dict]:
    """
    Procesa un webhook completo: normaliza, deduplica, consulta al asistente y responde.

    `responder` se llama como responder(texto, historial, telefono) y tiene que devolver
    el dict del asistente. Los tres se pueden reemplazar en las pruebas para no salir a
    la red ni depender de la base.
    """
    responder = responder or (lambda texto, historial, telefono: asistente.responder(texto, historial))
    enviar = enviar or enviar_respuesta
    historial_de = historial_de or (lambda telefono: [])

    procesados = []
    for mensaje in extraer_mensajes(payload):
        if ya_procesado(mensaje["mensaje_id"]):
            logger.info(f"Mensaje repetido, se ignora: {mensaje['mensaje_id']}")
            continue

        logger.info(f"[{mensaje['telefono']}] {mensaje['texto']!r}")
        try:
            resultado = responder(
                mensaje["texto"], historial_de(mensaje["telefono"]), mensaje["telefono"]
            )
        except Exception as e:  # noqa: BLE001
            logger.exception(f"Falló el asistente con {mensaje['telefono']}: {e}")
            olvidar(mensaje["mensaje_id"])
            continue

        if not enviar(mensaje["telefono"], resultado):
            # Si el envío falló, se suelta el id: si Meta reintenta, hay que volver a
            # intentar la respuesta en vez de descartarla por duplicada.
            logger.error(f"No se pudo responder a {mensaje['telefono']}; se libera el evento")
            olvidar(mensaje["mensaje_id"])

        procesados.append({**mensaje, "resultado": resultado})

    return procesados
