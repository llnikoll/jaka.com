#!/usr/bin/env python3
"""API local de catálogo para el asistente de Jaka Bicicletería.

Solo usa la biblioteca estándar de Python. Los JSON de tienda/data son la
fuente de verdad; no scrapea ni modifica el catálogo al atender consultas.
"""
from __future__ import annotations

import json
import os
import re
import unicodedata
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "tienda" / "data"
CONFIG = ROOT / "tienda" / "assets" / "config.js"
HOST = os.getenv("CATALOG_HOST", "127.0.0.1")
PORT = int(os.getenv("CATALOG_PORT", "8787"))
ALLOWED_ORIGIN = os.getenv("CATALOG_ALLOWED_ORIGIN", "*")
SITE_URL = os.getenv("CATALOG_SITE_URL", "https://www.bicicleteria.capiata.com.py")
BIKE_IMAGE_BASE = "https://www.ciclovia.com.py/media/catalog/product/"
MOTO_IMAGE_BASE = "https://www.chacomer.com.py/media/catalog/product/"

# Coincide con TIENDA_CONFIG de tienda/assets/config.js.
DEFAULT_CONFIG = {
    "recargoPct": 15,
    "recargoBajoPct": 0,
    "umbralBajo": 0,
    "redondeoPrecio": True,
    "moneda": "Gs.",
    "servicios": [
        {"nombre": "Básico", "precio": 80000, "items": [
            "Lavado integral", "Ajuste de cambio", "Ajuste de frenos",
            "Limpieza y lubricado de transmisión"]},
        {"nombre": "Completo", "precio": 120000, "items": [
            "Lavado integral", "Ajuste de cambio", "Ajuste de frenos",
            "Limpieza y lubricado de transmisión", "Mantenimiento de caja",
            "Centrado de ruedas", "Mantenimiento de las masas"]},
        {"nombre": "Premium", "precio": 150000, "items": [
            "Lavado integral", "Ajuste de cambio", "Ajuste de frenos",
            "Limpieza y lubricado de transmisión", "Mantenimiento de caja",
            "Centrado de ruedas", "Mantenimiento de las masas",
            "Mantenimiento de suspensión y juego de dirección"]},
    ],
    "serviciosNota": "Precios en guaraníes. Repuestos no incluidos. Los turnos se coordinan por WhatsApp.",
}
CACHE = None


def read_json(path: Path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def load_products():
    """Carga las dos fuentes de catálogo publicadas por los builders existentes."""
    bikes_doc = read_json(DATA / "catalogo.json", {})
    bikes = bikes_doc.get("productos", []) if isinstance(bikes_doc, dict) else []
    if not bikes:
        # Respaldo si no está el JSON completo: el builder ya publica esta vista.
        bikes = read_json(DATA / "v" / "todos.json", [])
    motos = read_json(DATA / "motos" / "v" / "todos.json", [])
    if not isinstance(bikes, list):
        bikes = []
    if not isinstance(motos, list):
        motos = []
    products = []
    seen = set()
    for raw, kind in [(p, "bicicletas") for p in bikes] + [(p, "motos") for p in motos]:
        pid = str(raw.get("i") or "").strip()
        if not pid:
            continue
        key = (kind, pid)
        if key in seen:
            continue
        seen.add(key)
        products.append(normalize_product(raw, kind))
    index = read_json(DATA / "indice.json", {}) or {}
    return products, index


def load_config():
    """Lee valores comerciales del config.js sin ejecutar JavaScript."""
    cfg = dict(DEFAULT_CONFIG)
    try:
        source = CONFIG.read_text(encoding="utf-8")
        for key in ("recargoPct", "recargoBajoPct", "umbralBajo"):
            match = re.search(r"\b" + key + r"\s*:\s*(-?\d+(?:\.\d+)?)", source)
            if match:
                cfg[key] = float(match.group(1))
        match = re.search(r"\bredondeoPrecio\s*:\s*(true|false)", source)
        if match:
            cfg["redondeoPrecio"] = match.group(1) == "true"
        match = re.search(r'\bmoneda\s*:\s*"([^"]+)"', source)
        if match:
            cfg["moneda"] = match.group(1)
        # Servicios se mantienen sincronizados con el archivo de la tienda.
        start = source.find("servicios: [")
        end = source.find("serviciosNota:", start)
        if start >= 0 and end > start:
            block = source[start:end]
            services = []
            pattern = re.compile(
                r'\{\s*nombre:\s*"([^"]+)"\s*,\s*precio:\s*(\d+)\s*,\s*items:\s*\[(.*?)\]\s*\}',
                re.S,
            )
            for item in pattern.finditer(block):
                services.append({
                    "nombre": item.group(1),
                    "precio": int(item.group(2)),
                    "items": re.findall(r'"([^"]+)"', item.group(3)),
                })
            if services:
                cfg["servicios"] = services
        note = re.search(r'\bserviciosNota\s*:\s*"([^"]*)"', source)
        if note:
            cfg["serviciosNota"] = note.group(1)
    except OSError:
        pass
    return cfg


def round_sale(value, enabled=True):
    if not enabled:
        return int(round(value))
    step = 10 if value < 1000 else 100 if value < 100000 else 1000 if value < 1000000 else 10000
    # Equivalente a Math.ceil(valor / paso) * paso del frontend.
    import math
    return int(math.ceil(value / step) * step)


def sale_price(original, cfg):
    if original is None:
        return None
    original = float(original)
    general = float(cfg["recargoPct"])
    low = float(cfg["recargoBajoPct"])
    threshold = float(cfg["umbralBajo"])
    percent = low if low > 0 and threshold > 0 and original <= threshold else general
    return round_sale(original * (1 + percent / 100), cfg["redondeoPrecio"]) if percent else int(round(original))


def normalize_product(raw, kind):
    is_moto = kind == "motos" or bool(raw.get("ch"))
    pid = str(raw.get("i") or "")
    image = str(raw.get("img") or "")
    if image and not image.startswith(("http://", "https://", "data:")):
        image = (MOTO_IMAGE_BASE if is_moto else BIKE_IMAGE_BASE) + image
    view = "motos" if is_moto else "todos"
    return {
        "id": pid,
        "name": str(raw.get("n") or "").strip(),
        "brand": str(raw.get("m") or "").strip() or None,
        "sku": str(raw.get("s") or "").strip() or None,
        "categories": raw.get("c") if isinstance(raw.get("c"), list) else [],
        "source_price": raw.get("p"),
        "source_list_price": raw.get("o"),
        "image": image or None,
        "source": "Chacomer" if is_moto else "Ciclovía",
        "kind": "motos" if is_moto else "bicicletas",
        "stock_code": raw.get("e"),
        "stock_confirm_required": bool(is_moto or raw.get("sc")),
        "on_sale": bool(raw.get("of")),
        "product_url": f"{SITE_URL}/tienda.html?p={pid}&v={view}",
        "_raw": raw,
    }


def normalize(text):
    text = unicodedata.normalize("NFD", str(text or "").lower())
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


# El catálogo escribe las velocidades de tres formas: "7 VELOCIDADES", "7V" y "7VL".
# Se unifican todas a "7v" ANTES de buscar, tanto en la consulta como en el nombre del
# producto, para que "piñón 7 velocidades" encuentre los tres.
#
# La alternativa —convertir "velocidades" en el token suelto "v"— se probó y es peor:
# "pinon" + "7" + "v" hacía match con cualquier producto que tuviera un 7 en el código
# y una "v" en cualquier palabra ("PIÑON DE LEVA MILESTONE ..."). Junto el número con
# su unidad y el ruido desaparece.
PATRON_VELOCIDADES = re.compile(r"(\d+)\s*(?:velocidades|velocidad|vel|vl|v)\b")


def normalize(text):
    text = unicodedata.normalize("NFD", str(text or "").lower())
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = re.sub(r"[^a-z0-9]+", " ", text).strip()
    return PATRON_VELOCIDADES.sub(r"\1v", text)


def expandir_terminos(consulta):
    """Normaliza la consulta y la parte en términos. Devuelve (frase, términos)."""
    frase = normalize(consulta)
    return frase, [t for t in frase.split() if t]


def enrich(product, cfg):
    p = {k: v for k, v in product.items() if k != "_raw"}
    p["price"] = sale_price(product["source_price"], cfg)
    p["list_price"] = sale_price(product["source_list_price"], cfg)
    p["currency"] = "PYG"
    p["availability"] = availability(product)
    p["availability_label"] = {
        "available_in_catalog": "Figura en catálogo; confirmar disponibilidad",
        "out_of_stock": "Sin stock según catálogo",
        "confirm": "Disponibilidad a confirmar",
        "no_data": "Consultar disponibilidad",
    }[p["availability"]]
    return p


def availability(product):
    # Chacomer no informa stock en el listado que consume el scraper actual.
    if product["stock_confirm_required"]:
        return "confirm"
    code = product["stock_code"]
    if code == 0:
        return "available_in_catalog"
    if code == 1:
        return "out_of_stock"
    if code == 2:
        return "confirm"
    return "no_data"


def category_catalog(index, products):
    labels = {}
    for item in index.get("categorias", []) if isinstance(index, dict) else []:
        if item.get("slug"):
            labels[item["slug"]] = item.get("nombre") or item["slug"]
    counts = {}
    for p in products:
        for slug in p["categories"]:
            counts[slug] = counts.get(slug, 0) + 1
    return [{"slug": slug, "name": labels.get(slug, slug.split("/")[-1].replace("-", " ").title()),
             "count": count} for slug, count in sorted(counts.items(), key=lambda x: x[0])]


def get_cache(force=False):
    global CACHE
    if CACHE is None or force:
        products, index = load_products()
        cfg = load_config()
        CACHE = {
            "products": products,
            "by_id": {p["id"]: p for p in products},
            "index": index,
            "config": cfg,
            "categories": category_catalog(index, products),
        }
    return CACHE


def search_products(query, category=None, kind=None, limit=10, offset=0):
    data = get_cache()
    q, terms = expandir_terminos(query)
    if not terms:
        return [], 0
    matches = []
    for p in data["products"]:
        if kind and p["kind"] != kind:
            continue
        if category and category not in p["categories"]:
            continue
        name = normalize(p["name"])
        brand = normalize(p["brand"])
        sku = normalize(p["sku"])
        cats = normalize(" ".join(p["categories"]))
        haystack = " ".join((name, brand, sku, cats))
        if not all(term in haystack for term in terms):
            continue
        score = (100 if q == name else 0) + (60 if q == sku else 0)
        score += sum(12 for t in terms if t in name)
        score += sum(8 for t in terms if t in brand)
        score += sum(15 for t in terms if t in sku)
        matches.append((score, p))
    matches.sort(key=lambda item: (-item[0], normalize(item[1]["name"])))
    total = len(matches)
    cfg = data["config"]
    return [enrich(p, cfg) for _, p in matches[offset:offset + limit]], total


class Handler(BaseHTTPRequestHandler):
    server_version = "JakaCatalogAPI/1.0"

    def send_json(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", ALLOWED_ORIGIN)
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", ALLOWED_ORIGIN)
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        path = parsed.path.rstrip("/") or "/"
        try:
            data = get_cache()
            if path == "/health":
                return self.send_json(200, {"ok": True, "service": "jaka-catalog-api"})
            if path == "/catalog/status":
                meta = data["index"].get("meta", {})
                return self.send_json(200, {
                    "ok": True, "total": len(data["products"]),
                    "by_type": {
                        "bicicletas": sum(p["kind"] == "bicicletas" for p in data["products"]),
                        "motos": sum(p["kind"] == "motos" for p in data["products"]),
                    },
                    "generated_at": meta.get("generado"),
                    "source": meta.get("fuente"),
                    "index_total": meta.get("total"),
                    "note": "El catálogo es una referencia; la disponibilidad se confirma con el local.",
                })
            if path == "/catalog/categories":
                return self.send_json(200, {"items": data["categories"], "count": len(data["categories"])})
            if path == "/services":
                return self.send_json(200, {
                    "items": data["config"]["servicios"],
                    "note": data["config"]["serviciosNota"],
                    "currency": "PYG",
                })
            if path == "/catalog/search":
                query = (params.get("q") or [""])[0]
                category = (params.get("category") or [None])[0]
                kind = (params.get("type") or [None])[0]
                if kind not in (None, "bicicletas", "motos"):
                    return self.send_json(400, {"error": "type debe ser bicicletas o motos"})
                if not query.strip():
                    return self.send_json(400, {"error": "El parámetro q es obligatorio"})
                limit = min(50, max(1, int((params.get("limit") or ["10"])[0])))
                offset = max(0, int((params.get("offset") or ["0"])[0]))
                items, total = search_products(query, category, kind, limit, offset)
                return self.send_json(200, {
                    "query": query, "total": total, "limit": limit, "offset": offset,
                    "items": items,
                })
            if path.startswith("/catalog/product/"):
                pid = path.rsplit("/", 1)[-1]
                product = data["by_id"].get(pid)
                if not product:
                    return self.send_json(404, {"error": "Producto no encontrado", "id": pid})
                return self.send_json(200, {"item": enrich(product, data["config"])})
            if path == "/catalog/reload":
                # Intencionalmente deshabilitado en modo abierto; reiniciar proceso
                # o activar un endpoint autenticado en un despliegue futuro.
                return self.send_json(405, {"error": "Recarga manual deshabilitada"})
            return self.send_json(404, {"error": "Ruta no encontrada"})
        except ValueError:
            return self.send_json(400, {"error": "Parámetro numérico inválido"})
        except Exception as exc:
            self.log_error("Error procesando %s: %s", self.path, exc)
            return self.send_json(500, {"error": "Error interno de catálogo"})

    def log_message(self, fmt, *args):
        print("%s - %s" % (self.address_string(), fmt % args))


def main():
    cache = get_cache()
    if not cache["products"]:
        raise SystemExit(
            "No se cargaron productos. Verificá tienda/data/catalogo.json y "
            "tienda/data/motos/v/todos.json."
        )
    print(f"Jaka Catalog API en http://{HOST}:{PORT}")
    print(f"Productos cargados: {len(cache['products'])}")
    print("Ctrl+C para detener.")
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
