# bot/service/catalogo.py
"""Cliente de la API de catálogo local (etapa 1).

El servicio nunca lee los JSON de la tienda por su cuenta: todo precio, stock y
servicio pasa por esta API. Así hay una sola fuente de verdad y el día que cambie
la forma del catálogo se arregla en un lugar.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request

from bot.service import config


class ErrorCatalogo(RuntimeError):
    """La API de catálogo no respondió o respondió algo inesperado."""


def _get(ruta: str, params: dict | None = None, timeout: float = 20.0) -> dict:
    url = f"{config.CATALOG_API_URL}{ruta}"
    if params:
        limpios = {k: v for k, v in params.items() if v not in (None, "")}
        if limpios:
            url += "?" + urllib.parse.urlencode(limpios)
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        cuerpo = e.read().decode("utf-8", "replace")
        if e.code == 404:
            return {}
        raise ErrorCatalogo(f"La API de catálogo devolvió {e.code}: {cuerpo[:200]}") from e
    except (urllib.error.URLError, TimeoutError) as e:
        raise ErrorCatalogo(
            f"No se pudo contactar la API de catálogo en {config.CATALOG_API_URL}. "
            f"¿Está corriendo 'python bot/api/server.py'? ({e})"
        ) from e
    except ValueError as e:
        raise ErrorCatalogo(f"La API de catálogo devolvió algo que no es JSON: {e}") from e


def estado() -> dict:
    """Resumen del catálogo: cuántos productos y de cuándo es."""
    return _get("/catalog/status")


def buscar(consulta: str, tipo: str | None = None, limite: int = 5) -> dict:
    """Busca productos. Devuelve la respuesta cruda de la API (items + total)."""
    return _get(
        "/catalog/search",
        {"q": consulta, "type": tipo, "limit": limite},
    )


def producto(identificador: str) -> dict:
    """Ficha de un producto por id."""
    return _get(f"/catalog/product/{identificador}").get("item") or {}


def servicios() -> dict:
    """Los planes de servicio técnico con sus precios."""
    return _get("/services")


def _precio(valor) -> str:
    """1234000 -> 'Gs. 1.234.000'."""
    if valor is None:
        return "a consultar"
    return f"Gs. {int(valor):,}".replace(",", ".")


def resumir_producto(item: dict) -> dict:
    """
    Recorta un producto a lo que el modelo necesita para redactar.

    Se pasan pocos campos a propósito: cuanto más texto de relleno se le da, más
    probable es que el modelo invente con él.
    """
    return {
        "id": item.get("id"),
        "nombre": item.get("name"),
        "marca": item.get("brand"),
        "precio": _precio(item.get("price")),
        "precio_origen": item.get("source_price"),
        "disponibilidad": item.get("availability_label") or item.get("availability"),
        "categoria": (item.get("categories") or [None])[0],
        "link": item.get("product_url"),
    }


def resumir_servicios(datos: dict) -> list[dict]:
    """Los planes de taller con precio formateado."""
    return [
        {
            "nombre": s.get("nombre"),
            "precio": _precio(s.get("precio")),
            "incluye": "; ".join(s.get("items") or []),
        }
        for s in (datos.get("items") or [])
    ]
