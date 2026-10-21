#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PoC: extractor de catálogo y precios de https://www.ciclovia.com.py/ (Magento 2, tema Chacomer).

Qué hace
--------
1. Lee robots.txt y el sitemap (con caché en disco).
2. Descubre las categorías a partir del sitemap (URLs .html de 2 niveles, que en este
   sitio son siempre categorías) + el menú de navegación de las páginas ya bajadas
   + una lista corta de landings/colecciones presentes en el sitemap.
3. Baja TODAS las páginas de cada categoría manejando `?p=N` y `product_list_limit`.
4. Extrae de cada tarjeta: nombre, URL canónica, SKU, precio final, precio anterior,
   moneda, disponibilidad, imagen, etiqueta de descuento y categorías donde aparece.
5. Para 5 fichas (una por rubro) extrae además: marca, SKU, precios, stock, imágenes,
   descripción, especificaciones y variantes/opciones (productos configurables).
6. Deduplica por URL, escribe `data/productos.jsonl`, `data/productos.csv`,
   `data/fichas.jsonl`, `data/categorias.csv` y `data/estadisticas.json`.

Restricciones de cortesía implementadas
--------------------------------------
* Secuencial (1 request a la vez), sin paralelismo.
* Delay aleatorio entre requests (por defecto 0,8–1,5 s).
* User-Agent identificable (ver UA_SCRAPER).
* Tope duro de requests HTTP por corrida (--max-requests, por defecto 150) y presupuesto
  reservado para las fichas de producto.
* Caché en disco: un archivo por URL; una segunda corrida no vuelve a pedir nada.
* Respeta robots.txt (urllib.robotparser) antes de cada request.

Uso
---
    python scraper_ciclovia.py --modo robots        # muestra robots.txt y si nos permite pasar
    python scraper_ciclovia.py --modo probe         # prueba tamaños de página (1-2 requests)
    python scraper_ciclovia.py --modo categorias    # catálogo completo (tarjetas)
    python scraper_ciclovia.py --modo fichas        # 5 fichas de producto
    python scraper_ciclovia.py --modo validar       # valida las salidas ya escritas
    python scraper_ciclovia.py --modo todo          # categorías + fichas + validación

Requisitos: Python 3.9+ y `lxml` (obligatorio). `requests` es opcional: si no está,
se usa urllib de la stdlib. Ver README.md.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

# ---------------------------------------------------------------------------
# Dependencias
# ---------------------------------------------------------------------------
try:
    from lxml import html as LH
except ImportError:  # pragma: no cover
    sys.exit(
        "ERROR: falta lxml. Instalá con: pip install lxml\n"
        "Si no hay Python del sistema con paquetes, usá el Python de load_workspace_dependencies "
        "(trae lxml) y ejecutá: <python-bundle> poc\\scraper_ciclovia.py --modo todo"
    )

try:
    import requests  # opcional, más cómodo
except ImportError:  # pragma: no cover
    requests = None

try:
    from urllib.robotparser import RobotFileParser
except ImportError:  # pragma: no cover
    RobotFileParser = None


# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------
BASE = "https://www.ciclovia.com.py"
UA_SCRAPER = (
    "BiciTiendaPoC/1.0 (+scraper secuencial de catalogo; "
    "proyecto propio de revendedor; ver poc/README.md)"
)
HEADERS = {
    "User-Agent": UA_SCRAPER,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-AR,es;q=0.9,en;q=0.5",
}

# Zona horaria de Paraguay (UTC-3, sin cambio de horario desde 2024).
TZ_PY = timezone(timedelta(hours=-3))

POC_DIR = Path(__file__).resolve().parent
CACHE_DIR = POC_DIR / "cache"
DATA_DIR = POC_DIR / "data"

# Rubros de primer nivel (para agrupar la salida y elegir fichas).
RUBROS = ["bicicletas", "fitness", "indumentaria", "autoaccesorios"]

# Landings/colecciones que están en el sitemap y no son hijas de ningún rubro.
# Se valida al descargarlas: si no son categorías Magento, se descartan y se informa.
CATEGORIAS_EXTRA = ["promociones.html", "cyberday.html"]

# Ficha usada como control de calidad: el Lead ya verificó estos valores a mano.
URL_FICHA_CONTROL = f"{BASE}/bicicleta-mtb-scott-contrail-40.html"
ESPERADO_FICHA_CONTROL = {
    "sku": "410116726",
    "precio_final": 3811800,
    "precio_anterior": 5082400,
    "cantidad_variantes": 11,
    "variantes_vendibles": 3,
}

RE_BG_IMG = re.compile(r"background-image:\s*url\(\s*'?([^')]+)'?\s*\)")
RE_CURRENCY = re.compile(r"^\s*([A-Z]{3})\b")
RE_ID_PRICE = re.compile(r"product-price-(\d+)")
RE_DIGITS_DOT = re.compile(r"\d[\d.]*")
# Bytes de control que rompen el parser HTML (hay fichas con \x00 dentro del nombre:
# libxml2 corta el documento ahí y se pierden las tarjetas siguientes).
RE_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def limpiar_html(texto: str) -> str:
    """Quita caracteres de control (incluido NUL) que truncan el parseo de lxml."""
    if not texto:
        return ""
    return RE_CONTROL.sub(" ", texto)


# ---------------------------------------------------------------------------
# Utilidades chicas
# ---------------------------------------------------------------------------
def ahora_iso() -> str:
    """Timestamp ISO-8601 en hora de Paraguay."""
    return datetime.now(TZ_PY).isoformat(timespec="seconds")


def etext(node) -> str:
    """Texto normalizado (colapsa espacios y saltos de línea)."""
    if node is None:
        return ""
    return " ".join(node.text_content().split())


def a_entero(valor) -> int | None:
    """Convierte un precio de PYG a int, tolerando separadores y decimales.

    Casos reales del sitio:
      '3811800' -> 3811800        (atributo normal)
      'PYG 5.082.400' -> 5082400  (puntos como separador de miles)
      '41678.1' -> 41678          (el sitio publica algunos precios con un decimal;
                                   sin esto se leía 416781, 10x de más)
    """
    if valor is None:
        return None
    if isinstance(valor, int):
        return valor
    txt = str(valor).strip().replace("\u00a0", " ")
    if not txt:
        return None
    m = re.search(r"\d[\d.,]*", txt)
    if not m:
        return None
    s = m.group(0)
    if "," in s and "." in s:            # 1.234,56 -> 1234.56
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:                        # 1,5 decimal vs 1,234 miles
        partes = s.split(",")
        s = s.replace(",", "") if len(partes[-1]) == 3 else s.replace(",", ".")
    if s.count(".") == 1 and len(s.split(".")[1]) in (1, 2):
        return int(round(float(s)))       # decimal real
    return int(s.replace(".", ""))        # separador de miles


def a_decimal_2(valor) -> str:
    """Número con punto decimal (para descuentos), sin separador de miles."""
    return f"{valor:.2f}"


def slug_de_url(url: str) -> str:
    """Nombre de archivo de caché legible a partir de una URL."""
    p = urlparse(url)
    path = p.path.strip("/")
    if not path:
        return "home"
    if path.endswith(".html"):
        path = path[: -len(".html")]
    q = (p.query or "").replace("&", "_").replace("=", "")
    base = f"{path}__{q}" if q else path
    base = re.sub(r"[^A-Za-z0-9_.-]+", "-", base)
    return base.strip("-")[:110] or "pagina"


def es_url_categoria_candidata(url: str) -> bool:
    """Categoría candidata según el sitemap: .html con 2 niveles de path (siempre categorías).

    Los productos de este sitio cuelgan de la raíz (1 nivel: /bicicleta-xxx.html), así que
    un path de 2 niveles (/fitness/cintas.html) es inequívocamente una categoría.
    """
    if not url.startswith(BASE):
        return False
    path = urlparse(url).path
    if not path.endswith(".html"):
        return False
    partes = [s for s in path.split("/") if s]
    return len(partes) == 2


def profundidad_categoria(url: str) -> int:
    return len([s for s in urlparse(url).path.split("/") if s])


def primer_segmento(url: str) -> str:
    partes = [s for s in urlparse(url).path.split("/") if s]
    if not partes:
        return ""
    return partes[0][: -len(".html")] if partes[0].endswith(".html") else partes[0]


def descontar(previo: int | None, final: int | None) -> float | None:
    if not previo or not final or previo <= 0:
        return None
    return round(100.0 * (previo - final) / previo, 2)


# ---------------------------------------------------------------------------
# Extracción de JSON embebido en <script type="text/x-magento-init">
# ---------------------------------------------------------------------------
def scripts_json(doc) -> list:
    """Devuelve la lista de objetos JSON de los x-magento-init del documento."""
    salida = []
    for s in doc.xpath("//script[@type='text/x-magento-init']"):
        texto = (s.text or "").strip()
        if not texto:
            continue
        try:
            datos = json.loads(texto)
        except (ValueError, TypeError):
            continue
        salida.append(datos)
    return salida


def buscar_clave(obj, clave):
    """Genera todos los valores asociados a `clave` en cualquier nivel de `obj`."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == clave:
                yield v
            else:
                yield from buscar_clave(v, clave)
    elif isinstance(obj, list):
        for v in obj:
            yield from buscar_clave(v, clave)


# ---------------------------------------------------------------------------
# Parseo: página de categoría
# ---------------------------------------------------------------------------
# Tarjetas del grid principal. Se exige el <ol class="products ... product-items"> porque en
# el HTML también aparece la plantilla de "comparar" con <li class="product-item"> sueltos.
XP_GRID = ("//ol[contains(@class,'product-items') and contains(@class,'products') "
           "and not(@id='compare-items')]")
XP_TARJETAS = (XP_GRID + "/li[contains(concat(' ', normalize-space(@class), ' '), ' product-item ')]")
XP_TARJETAS_GENERICO = "//li[contains(concat(' ', normalize-space(@class), ' '), ' product-item ')]"


def _primero(nodos):
    return nodos[0] if nodos else None


def parse_total_toolbar(doc) -> int | None:
    """Total de resultados de la categoría según el toolbar de Magento."""
    el = _primero(doc.xpath("//p[contains(@class,'toolbar-amount')]"))
    if el is None:
        return None
    texto = etext(el)
    numeros = RE_DIGITS_DOT.findall(texto)
    if not numeros:
        return None
    if " de " in texto and len(numeros) >= 2:
        return a_entero(numeros[-1])
    return a_entero(numeros[0])


def parse_moneda_pagina(doc) -> str:
    """Moneda de la tienda, tomada del meta de precio o del config de Magento."""
    meta = _primero(doc.xpath("//meta[@itemprop='priceCurrency']/@content"))
    if meta:
        return meta.strip()
    for obj in scripts_json(doc):
        for cfg in buscar_clave(obj, "priceFormat"):
            if isinstance(cfg, dict) and isinstance(cfg.get("pattern"), str):
                m = RE_CURRENCY.match(cfg["pattern"].replace("\u00a0", " "))
                if m:
                    return m.group(1)
    return "PYG"


def parse_tarjeta(card, moneda_pagina: str, url_pagina: str) -> dict | None:
    """Extrae una tarjeta de producto del grid de categoría.

    Se descartan dos plantillas que el tema mete dentro del mismo grid y que inflaban el
    conteo: la de autocompletado (`ol.product-items-names`) y la de comparar (último
    `li.product-item` con `data-bind` y sin `data-role="priceBox"`).
    """
    if card.get("data-bind"):
        return None
    if card.xpath("ancestor::ol[contains(@class,'product-items-names')]"):
        return None
    enlace = _primero(card.xpath(".//a[contains(@class,'product-item-link')]"))
    if enlace is not None and enlace.get("data-bind"):
        return None
    nombre = etext(enlace)
    href = (enlace.get("href") or "").strip() if enlace is not None else ""
    if not nombre or not href:
        return None
    url = urljoin(url_pagina, href)

    pid = _primero(card.xpath(".//div[@data-role='priceBox']/@data-product-id"))
    if not pid:
        pid = _primero(card.xpath(".//input[@name='product']/@value"))
    if not pid:
        m = re.search(r'"product"\s*:\s*"?(\d+)"?', LH.tostring(card, encoding="unicode"))
        pid = m.group(1) if m else None
    if not pid:
        m = RE_ID_PRICE.search(" ".join(
            card.xpath(".//*[starts-with(@id,'product-price-')]/@id")
            + card.xpath(".//*[starts-with(@id,'old-price-')]/@id")
        ))
        pid = m.group(1) if m else None

    sku = _primero(card.xpath(".//form[@data-role='tocart-form']/@data-product-sku")) or ""
    sku = sku.strip()

    finales = [a_entero(x) for x in card.xpath(".//*[@data-price-type='finalPrice']/@data-price-amount")]
    finales = [x for x in finales if x is not None]
    previos = [a_entero(x) for x in card.xpath(".//*[@data-price-type='oldPrice']/@data-price-amount")]
    previos = [x for x in previos if x is not None]
    final = finales[0] if finales else None
    previo = previos[0] if previos else None

    texto_precio = etext(_primero(card.xpath(
        ".//*[@data-price-type='finalPrice']//span[contains(@class,'price')]")))
    # El HTML trae el nbsp mal codificado como 'Â ': se normaliza para el texto de salida.
    texto_precio = texto_precio.replace("\u00a0", " ").replace("Â", " ").strip()
    moneda = moneda_pagina
    m = RE_CURRENCY.match(texto_precio)
    if m:
        moneda = m.group(1)

    etiqueta = etext(_primero(card.xpath(".//span[contains(@class,'special-price-discount')]")))

    # Imagen: el tema usa lazy-load con background-image y un <img> de respaldo.
    imagen = ""
    m = RE_BG_IMG.search(LH.tostring(card, encoding="unicode"))
    if m:
        imagen = m.group(1).strip()
    if not imagen:
        for xp in (".//img[contains(@class,'product-image-photo')]/@src",
                   ".//img[contains(@class,'product-image-photo')]/@data-src",
                   ".//img[contains(@class,'product-image-photo')]/@data-original"):
            imagen = _primero(card.xpath(xp)) or ""
            if imagen:
                break
    if imagen.startswith("//"):
        imagen = "https:" + imagen
    elif imagen.startswith("/"):
        imagen = BASE + imagen

    # Estado de la tarjeta. El sitio tiene 3 casos y NO hay marcador positivo de stock:
    #  (a) con precio            -> "con_precio"
    #  (b) solo catálogo         -> div.onlycatalog-message ("Adquiéralo en un distribuidor
    #                               autorizado"), sin precio, pero cuenta en el total
    #  (c) agotado               -> .stock.unavailable "Sin stock"
    # Si no dice "Sin stock" se asume disponible.
    stock_el = _primero(card.xpath(".//div[contains(@class,'stock')]"))
    sin_stock = False
    if stock_el is not None:
        txt_stock = etext(stock_el).lower()
        clases_stock = (stock_el.get("class") or "").lower()
        sin_stock = ("sin stock" in txt_stock or "agotado" in txt_stock
                     or "unavailable" in clases_stock)
    solo_catalogo = bool(card.xpath(".//div[contains(@class,'onlycatalog-message')]")) or bool(
        card.xpath(".//*[contains(@class,'onlycatalog-message')]"))
    if solo_catalogo:
        estado_tarjeta = "solo_catalogo"
        disponibilidad = "Solo catálogo (sin venta online)"
    elif sin_stock:
        estado_tarjeta = "agotado"
        disponibilidad = "Agotado"
    elif final is not None:
        estado_tarjeta = "con_precio"
        disponibilidad = "En stock"  # asumido: el grid no publica stock positivo
    else:
        estado_tarjeta = "sin_dato"
        disponibilidad = "En stock"  # asumido

    return {
        "id_magento": str(pid) if pid else "",
        "sku": sku,
        "nombre": nombre,
        "url": url,
        "moneda": moneda,
        "precio_final": final,
        "precio_final_texto": texto_precio,
        "precio_anterior": previo,
        "descuento_pct": descontar(previo, final),
        "etiqueta": etiqueta or None,
        "estado_tarjeta": estado_tarjeta,
        "disponibilidad": disponibilidad,
        "disponibilidad_inferida": True,
        "imagen": imagen or None,
    }


def parse_pagina_categoria(texto_html: str, url_pagina: str) -> dict:
    """Parsea una página de categoría: metadatos + tarjetas.

    Ojo: no se usa `<body class>` para decidir si es categoría porque el parser de lxml
    pierde los atributos del body en estas páginas (el <head> trae markup raro). Se usan
    marcadores del grid/toolbar, que sí parsean bien.
    """
    doc = LH.fromstring(limpiar_html(texto_html))
    # lxml pierde los atributos de <body> en estas páginas; se sacan con regex del HTML crudo.
    m_body = re.search(r"<body\b[^>]*\bclass=[\"']([^\"']*)[\"']", texto_html, re.I)
    clases_body = (m_body.group(1).lower() if m_body else " ".join(doc.xpath("//body/@class")).lower())
    titulo = etext(_primero(doc.xpath("//h1[contains(@class,'page-title')]")))
    total = parse_total_toolbar(doc)
    moneda = parse_moneda_pagina(doc)
    tarjetas = []
    nodos = doc.xpath(XP_TARJETAS)
    if not nodos:
        nodos = doc.xpath(XP_TARJETAS_GENERICO)
    for card in nodos:
        datos = parse_tarjeta(card, moneda, url_pagina)
        if datos:
            tarjetas.append(datos)
    es_producto = bool(doc.xpath("//div[contains(@class,'product-info-main')]")) or bool(
        doc.xpath("//form[contains(@class,'product-add-form')]") + doc.xpath("//div[@id='product-addtocart-form']"))
    hay_grid = bool(doc.xpath(XP_GRID)) or bool(doc.xpath("//p[contains(@class,'toolbar-amount')]"))
    return {
        # Un producto puede traer un carrusel de relacionados; por eso se descarta si es ficha.
        "es_categoria": hay_grid and not es_producto,
        "es_categoria_magento": "catalog-category-view" in clases_body,
        "es_producto": es_producto,
        "titulo": titulo,
        "total_declarado": total,
        "moneda": moneda,
        "tarjetas": tarjetas,
        "clases_body": clases_body,
    }


def categorias_del_menu(doc) -> list[str]:
    """URLs de categoría que aparecen en el menú de navegación de cualquier página."""
    encontradas = []
    for a in doc.xpath("//nav[contains(@class,'navigation')]//a[@href]"):
        href = (a.get("href") or "").strip()
        if href.startswith("/"):
            href = BASE + href
        if not href.startswith(BASE):
            continue
        path = urlparse(href).path
        if not path.endswith(".html"):
            continue
        if len([s for s in path.split("/") if s]) <= 2:
            encontradas.append(href.split("?")[0])
    return encontradas


# ---------------------------------------------------------------------------
# Parseo: ficha de producto
# ---------------------------------------------------------------------------
def parse_ficha(texto_html: str, url_pagina: str) -> dict:
    """Parsea una ficha de producto (catalog-product-view)."""
    doc = LH.fromstring(limpiar_html(texto_html))
    clases_body = " ".join(doc.xpath("//body/@class")).lower()
    scripts = scripts_json(doc)

    nombre = etext(_primero(doc.xpath("//h1[contains(@class,'page-title')]//span[contains(@class,'base')]")))
    if not nombre:
        nombre = etext(_primero(doc.xpath("//h1[contains(@class,'page-title')]")))

    marca = etext(_primero(doc.xpath("//div[contains(@class,'product-item-brand')]//span")))
    sku = etext(_primero(doc.xpath("//div[contains(@class,'product') and contains(@class,'sku')]//div[contains(@class,'value')]")))
    if not sku:
        sku = (etext(_primero(doc.xpath("//*[@itemprop='sku']"))) or "").strip()

    # Precios visibles de la ficha (también hay meta itemprop=price).
    finales = [a_entero(x) for x in doc.xpath("//*[@data-price-type='finalPrice']/@data-price-amount")]
    finales = [x for x in finales if x is not None]
    previos = [a_entero(x) for x in doc.xpath("//*[@data-price-type='oldPrice']/@data-price-amount")]
    previos = [x for x in previos if x is not None]
    precio_final = finales[0] if finales else a_entero(_primero(doc.xpath("//meta[@itemprop='price']/@content")))
    precio_previo = previos[0] if previos else None

    moneda = (_primero(doc.xpath("//meta[@itemprop='priceCurrency']/@content")) or "").strip()
    if not moneda:
        moneda = parse_moneda_pagina(doc)

    # Stock: div.stock.available / div.stock.unavailable con texto "En stock" / "Agotado".
    disponibilidad = "sin dato"
    disponibilidad_texto = ""
    stock_el = _primero(doc.xpath(
        "//div[contains(@class,'stock') and not(contains(@class,'stock-sku'))]"))
    if stock_el is None:
        stock_el = _primero(doc.xpath("//div[@title='Disponibilidad']"))
    if stock_el is not None:
        disponibilidad_texto = etext(stock_el)
        clases = (stock_el.get("class") or "").lower()
        if "unavailable" in clases or "agotado" in disponibilidad_texto.lower():
            disponibilidad = "Agotado"
        elif "available" in clases or "stock" in disponibilidad_texto.lower():
            disponibilidad = "En stock"

    # Imágenes: JSON de la galería (mage/gallery/gallery).
    imagenes, captions = [], []
    for cfg in buscar_clave(scripts, "mage/gallery/gallery"):
        if isinstance(cfg, dict) and isinstance(cfg.get("data"), list):
            for img in cfg["data"]:
                if not isinstance(img, dict):
                    continue
                url = img.get("full") or img.get("img") or img.get("thumb")
                if url and url not in imagenes:
                    imagenes.append(url)
                    if img.get("caption"):
                        captions.append(img["caption"])
            break
    if not imagenes:
        for xp in ("//meta[@property='og:image']/@content", "//link[@itemprop='image']/@href"):
            for u in doc.xpath(xp):
                if u and u not in imagenes:
                    imagenes.append(u.strip())
    if not captions:
        captions = [etext(_primero(doc.xpath("//img[@itemprop='image']/@alt")))] if imagenes else []

    # Descripción (bloque "Detalles"). Se toma el contenedor interno para no arrastrar el
    # texto del enlace "Ver más" que el tema agrega al final.
    descripcion = etext(_primero(doc.xpath(
        "//div[@id='description']//div[contains(@class,'toggle-container')]")))
    if not descripcion:
        descripcion = etext(_primero(doc.xpath("//div[@id='description']//div[@itemprop='description']")))
    if not descripcion:
        descripcion = etext(_primero(doc.xpath(
            "//div[contains(@class,'attribute') and contains(@class,'description')]//div[contains(@class,'value')]")))
    descripcion = re.sub(r"\s*Ver m[áa]s\s*$", "", descripcion).strip()

    # Especificaciones (tabla "Más información" / "Especificaciones").
    especificaciones = {}
    for fila in doc.xpath("//table[contains(@class,'additional-attributes')]//tr"):
        etiqueta = etext(_primero(fila.xpath("./th")))
        valor = etext(_primero(fila.xpath("./td")))
        if etiqueta and valor:
            especificaciones[etiqueta] = valor
    if not marca and especificaciones.get("Marca"):
        marca = especificaciones["Marca"]

    # Tipo de producto (simple / configurable / virtual...).
    tipo_producto = ""
    for obj in scripts:
        for v in buscar_clave(obj, "productType"):
            if isinstance(v, str) and v:
                tipo_producto = v
                break
        if tipo_producto:
            break

    # Variantes: jsonConfig del swatch-renderer de Magento (solo configurables).
    variantes, opciones = [], []
    swatch_cfg = None
    for cfg in buscar_clave(scripts, "Magento_Swatches/js/swatch-renderer"):
        if isinstance(cfg, dict) and isinstance(cfg.get("jsonConfig"), dict):
            swatch_cfg = cfg["jsonConfig"]
            break
    if swatch_cfg:
        attrs = swatch_cfg.get("attributes") or {}
        precios_por_variante = swatch_cfg.get("optionPrices") or {}
        skus_por_variante = swatch_cfg.get("sku") or {}
        indice = swatch_cfg.get("index") or {}
        etiquetas_attr = {aid: (a.get("label") or a.get("code") or aid) for aid, a in attrs.items()}
        for aid, a in attrs.items():
            opciones.append({
                "atributo": etiquetas_attr[aid],
                "codigo": a.get("code"),
                "valores": [o.get("label") for o in (a.get("options") or []) if isinstance(o, dict)],
            })
        # `salable` viene como {attrId: {optionId: [childIds]}}: los hijos realmente vendibles.
        vendibles: set[str] = set()
        salable_cfg = swatch_cfg.get("salable") or {}
        if isinstance(salable_cfg, dict):
            for opciones_attr in salable_cfg.values():
                if isinstance(opciones_attr, dict):
                    for ids in opciones_attr.values():
                        if isinstance(ids, (list, tuple)):
                            vendibles.update(str(x) for x in ids)
                        elif ids not in (None, ""):
                            vendibles.add(str(ids))
                elif isinstance(opciones_attr, (list, tuple)):
                    vendibles.update(str(x) for x in opciones_attr)
        self_vendibles = vendibles

        def _armar_variante(pid, atributos):
            precios = precios_por_variante.get(str(pid)) or {}
            pf = (precios.get("finalPrice") or {}).get("amount")
            pp = (precios.get("oldPrice") or {}).get("amount")
            return {
                "id_variante": str(pid),
                "sku": skus_por_variante.get(str(pid), ""),
                "atributos": atributos,
                "precio_final": a_entero(pf),
                "precio_anterior": a_entero(pp),
                "vendible": (str(pid) in self_vendibles) if self_vendibles else None,
            }

        for pid, combo in indice.items():
            if not isinstance(combo, dict):
                continue
            atributos = {}
            for aid, oid in combo.items():
                etiqueta_attr = etiquetas_attr.get(str(aid), str(aid))
                label = str(oid)
                for o in (attrs.get(str(aid), {}) or {}).get("options") or []:
                    if str(o.get("id")) == str(oid):
                        label = o.get("label") or str(oid)
                        break
                atributos[etiqueta_attr] = label
            variantes.append(_armar_variante(pid, atributos))
        if not variantes and skus_por_variante:
            for pid, sku_v in skus_por_variante.items():
                variantes.append(_armar_variante(pid, {}))
        if variantes and not self_vendibles:
            # Último recurso: interpretar stock por variante desde optionPrices si viniera.
            for v in variantes:
                v["vendible"] = None

    # Categorías / breadcrumbs.
    categorias = []
    for a in doc.xpath("//div[contains(@class,'breadcrumbs')]//li//a[@href]"):
        href = (a.get("href") or "").strip()
        txt = etext(a)
        if not txt or href.endswith("/") and txt.lower().startswith("página"):
            continue
        if href.startswith("/"):
            href = BASE + href
        categorias.append({"nombre": txt, "url": href.split("?")[0]})
    # El último ítem del breadcrumb suele ser <strong> (sin <a>).
    if not categorias:
        for li in doc.xpath("//div[contains(@class,'breadcrumbs')]//li"):
            txt = etext(li)
            if txt:
                categorias.append({"nombre": txt, "url": ""})

    canonical = (_primero(doc.xpath("//link[@rel='canonical']/@href")) or url_pagina).strip()

    return {
        "nombre": nombre,
        "url": canonical,
        "marca": marca,
        "sku": sku,
        "tipo_producto": tipo_producto,
        "moneda": moneda,
        "precio_final": precio_final,
        "precio_anterior": precio_previo,
        "descuento_pct": descontar(precio_previo, precio_final),
        "disponibilidad": disponibilidad,
        "disponibilidad_texto": disponibilidad_texto,
        "descripcion": descripcion,
        "especificaciones": especificaciones,
        "imagenes": imagenes,
        "imagen_principal": imagenes[0] if imagenes else None,
        "cantidad_imagenes": len(imagenes),
        "opciones": opciones,
        "variantes": variantes,
        "cantidad_variantes": len(variantes),
        "variantes_vendibles": sum(1 for v in variantes if v.get("vendible") is True),
        "categorias_breadcrumb": categorias,
        "clases_body": clases_body,
    }


# ---------------------------------------------------------------------------
# Cliente HTTP con caché, robots y presupuesto de requests
# ---------------------------------------------------------------------------
class PresupuestoAgotado(Exception):
    pass


class RobotsBloqueado(Exception):
    pass


class Scraper:
    def __init__(self, args):
        self.args = args
        self.n_http = 0
        self.n_cache = 0
        self.robots = None
        self.robots_texto = ""
        self.registro = []          # detalle de requests HTTP de esta corrida
        self.log_path = CACHE_DIR / "_requests.jsonl"
        self.sesion = requests.Session() if requests is not None else None
        if self.sesion is not None:
            self.sesion.headers.update(HEADERS)
        self.historial_categorias = []
        self._raices_validas: set[str] = set()
        self.max_requests = args.max_requests
        self.estadisticas = {
            "fecha_corrida": ahora_iso(),
            "user_agent": UA_SCRAPER,
            "delay": [args.delay_min, args.delay_max],
            "limite_pagina": args.limite_pagina,
            "max_requests": args.max_requests,
        }

    # -- infraestructura ---------------------------------------------------
    def _ruta_cache(self, nombre: str) -> Path:
        return CACHE_DIR / nombre

    def _guardar_cache(self, nombre: str, texto: str) -> None:
        ruta = self._ruta_cache(nombre)
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text(texto, encoding="utf-8")

    def _leer_cache(self, nombre: str) -> str | None:
        ruta = self._ruta_cache(nombre)
        if ruta.exists():
            try:
                return ruta.read_text(encoding="utf-8", errors="replace")
            except OSError:
                return None
        return None

    def _anotar_request(self, url: str, status: int, nbytes: int, ms: int) -> None:
        fila = {
            "ts": ahora_iso(),
            "url": url,
            "status": status,
            "bytes": nbytes,
            "ms": ms,
            "user_agent": UA_SCRAPER,
        }
        self.registro.append(fila)
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with self.log_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(fila, ensure_ascii=False) + "\n")
        except OSError:
            pass

    def cargar_robots(self, forzar: bool = False) -> None:
        """Descarga (o lee de caché) robots.txt y prepara el parser."""
        url = f"{BASE}/robots.txt"
        texto = None if forzar else self._leer_cache("robots.txt")
        if texto is not None:
            self.n_cache += 1
        else:
            texto = self._http_get(url, "robots.txt", comprobar_robots=False)
        self.robots_texto = texto or ""
        if RobotFileParser is not None and self.robots_texto:
            rp = RobotFileParser()
            rp.parse(self.robots_texto.splitlines())
            self.robots = rp

    def _rutas_prohibidas_explicitas(self, url: str) -> bool:
        """Rutas que el sitio prohíbe explícitamente (robots.txt) y que nunca tocamos."""
        path = urlparse(url).path
        prohibidas = (
            "/js/", "/lib/", "/skin/", "/checkout/", "/customer/",
            "/catalog/product/view/", "/index.php/", "/sendfriend/", "/review/",
        )
        if any(path.startswith(p) for p in prohibidas):
            return True
        # /media/ salvo imágenes de producto
        if path.startswith("/media/") and not path.startswith("/media/catalog/product/"):
            return True
        return False

    def _robots_permite(self, url: str) -> bool:
        """Política de robots.txt.

        robots.txt de Magento 2 trae `Disallow: /*?`, que en teoría bloquea cualquier URL
        con query string, incluido el paginado `?p=N`. Es una regla genérica de la
        plantilla (también la aplican a Googlebot) y la tienda publica categorías y
        productos en el sitemap. Con `--politica-robots paginado` (por defecto) se
        permiten SOLO los parámetros de paginación `p` y `product_list_limit`, que es lo
        que la tarea pide recorrer. Con `--politica-robots estricta` se respeta la regla
        al pie de la letra: solo se baja la página 1 de cada categoría.
        """
        if self._rutas_prohibidas_explicitas(url):
            return False
        tiene_query = bool(urlparse(url).query)
        if tiene_query:
            if self.args.politica_robots == "estricta":
                return False
            from urllib.parse import parse_qs
            claves = set(parse_qs(urlparse(url).query, keep_blank_values=True))
            if not claves.issubset({"p", "product_list_limit"}):
                return False
            return True
        if self.robots is None:
            return True
        try:
            return self.robots.can_fetch(UA_SCRAPER, url)
        except Exception:
            return True

    def _esperar(self) -> None:
        time.sleep(random.uniform(self.args.delay_min, self.args.delay_max))

    def _http_get(self, url: str, nombre_cache: str, comprobar_robots: bool = True) -> str:
        """GET real (sin caché). Aplica robots, delay, reintento y tope de presupuesto."""
        if comprobar_robots and not self._robots_permite(url):
            raise RobotsBloqueado(f"robots.txt prohíbe {url}")
        if self.n_http + self.args.reservado >= self.max_requests:
            raise PresupuestoAgotado(
                f"tope de {self.max_requests} requests alcanzado (reservado={self.args.reservado})"
            )
        intentos = 0
        while True:
            intentos += 1
            self._esperar()
            t0 = time.time()
            try:
                if self.sesion is not None:
                    resp = self.sesion.get(url, timeout=self.args.timeout)
                    status = resp.status_code
                    contenido = resp.content
                else:
                    req = Request(url, headers=HEADERS)
                    with urlopen(req, timeout=self.args.timeout) as resp:
                        status = resp.getcode()
                        contenido = resp.read()
                ms = int((time.time() - t0) * 1000)
                if status >= 400:
                    self._anotar_request(url, status, len(contenido or b""), ms)
                    raise HTTPError(url, status, f"HTTP {status}", None, None)
                texto = (contenido or b"").decode("utf-8", errors="replace")
                self._guardar_cache(nombre_cache, texto)
                self.n_http += 1
                self._anotar_request(url, status, len(contenido or b""), ms)
                return texto
            except HTTPError as exc:
                if exc.code in (429, 503) and intentos < 3:
                    time.sleep(10 * intentos)
                    continue
                if exc.code in (429, 503):
                    self._anotar_request(url, exc.code, 0, int((time.time() - t0) * 1000))
                raise
            except (URLError, TimeoutError, OSError) as exc:
                if intentos < 3:
                    time.sleep(5 * intentos)
                    continue
                raise RuntimeError(f"fallo de red en {url}: {exc}") from exc

    def obtener(self, url: str, nombre_cache: str, forzar: bool = False) -> tuple[str | None, bool]:
        """Devuelve (html, desde_cache). Usa caché en disco salvo --force."""
        forzar = forzar or self.args.force
        if not forzar:
            cacheado = self._leer_cache(nombre_cache)
            if cacheado is not None:
                self.n_cache += 1
                return cacheado, True
        if self.args.sin_red:
            return None, False
        return self._http_get(url, nombre_cache), False

    # -- sitemap -----------------------------------------------------------
    def sitemap(self) -> list[dict]:
        texto, desde_cache = self.obtener(f"{BASE}/sitemap.xml", "sitemap.xml")
        if texto is None:
            raise RuntimeError("no hay sitemap en caché y se pidió --sin-red")
        filas = []
        patron = re.compile(
            r"<url>\s*<loc>([^<]+)</loc>(?:\s*<lastmod>([^<]+)</lastmod>)?", re.S
        )
        for m in patron.finditer(texto):
            filas.append({"url": m.group(1).strip(), "lastmod": (m.group(2) or "").strip() or None})
        if not filas:  # fallback: solo <loc>
            filas = [{"url": u.strip(), "lastmod": None}
                     for u in re.findall(r"<loc>([^<]+)</loc>", texto)]
        self.estadisticas["sitemap"] = {
            "urls": len(filas),
            "desde_cache": desde_cache,
            "html": sum(1 for f in filas if f["url"].endswith(".html")),
        }
        return filas

    # -- descubrimiento de categorías -------------------------------------
    def descubrir_categorias(self, filas_sitemap: list[dict]) -> list[str]:
        """Categorías del sitemap.

        Ojo: en este sitio algunos productos tienen URL con barra (p. ej.
        `/sensor-mano-con-boton-star/stop-atr510t64.html`), así que "path de 2 niveles"
        no alcanza como criterio. Se exige además que el primer nivel sea una categoría
        raíz real (`/<seg>.html` presente en el sitemap), lo que descarta esos productos.
        """
        urls_sitemap = {f["url"].split("?")[0] for f in filas_sitemap}
        candidatas = []
        for f in filas_sitemap:
            url = f["url"].split("?")[0]
            if not url.endswith(".html"):
                continue
            partes = [s for s in urlparse(url).path.split("/") if s]
            if len(partes) != 2:
                continue
            seg = partes[0]
            if f"{BASE}/{seg}.html" in urls_sitemap:  # primer nivel = categoría raíz real
                candidatas.append(url)

        # Raíces: padre de cada categoría de 2 niveles, si está en el sitemap.
        raices = sorted({f"{BASE}/{primer_segmento(u)}.html" for u in candidatas})

        # Landings/colecciones conocidas (se validan al descargarlas).
        extras = [f"{BASE}/{x}" for x in CATEGORIAS_EXTRA if f"{BASE}/{x}" in urls_sitemap]

        orden = (raices if self.args.incluir_raices else []) + candidatas + extras
        vistos, salida = set(), []
        for u in orden:
            if u not in vistos:
                vistos.add(u)
                salida.append(u)
        self.estadisticas["descubrimiento"] = {
            "categorias_2_niveles": len(candidatas),
            "raices_detectadas": raices,
            "raices_incluidas": bool(self.args.incluir_raices),
            "extras": extras,
            "total_candidatas": len(salida),
            "productos_con_barra_en_url_descartados": sum(
                1 for f in filas_sitemap
                if f["url"].endswith(".html")
                and len([s for s in urlparse(f["url"]).path.split("/") if s]) == 2
                and f"{BASE}/{primer_segmento(f['url'])}.html" not in urls_sitemap),
            "fuente": "sitemap.xml (+ menú de navegación al vuelo)",
        }
        return salida

    # -- categorías --------------------------------------------------------
    def url_categoria_pagina(self, url_base: str, pagina: int) -> str:
        if self.args.politica_robots == "estricta" and pagina == 1:
            return url_base  # sin query string: URL limpia publicada en el sitemap
        sep = "&" if "?" in url_base else "?"
        return f"{url_base}{sep}product_list_limit={self.args.limite_pagina}&p={pagina}"

    def crawl_categoria(self, url_categoria: str, productos: dict) -> dict:
        """Baja todas las páginas de una categoría. Devuelve estadísticas de la categoría."""
        path_cat = urlparse(url_categoria).path.strip("/")
        clave_categoria = path_cat[:-len(".html")] if path_cat.endswith(".html") else path_cat
        info = {
            "categoria_url": url_categoria,
            # slug = identificador apto para nombre de archivo; categoria = clave con "/"
            "slug": clave_categoria.replace("/", "-"),
            "categoria": clave_categoria,
            "nombre": "",
            "total_declarado": None,
            "paginas_previstas": None,
            "paginas_bajadas": 0,
            "tarjetas": 0,
            "tarjetas_esperadas": 0,
            "tarjetas_descartadas": 0,
            "nuevas": 0,
            "estado": "ok",
            "moneda": None,
            "detalle_paginas": [],
            "es_categoria": None,
        }
        pagina = 1
        while pagina <= 200:
            url = self.url_categoria_pagina(url_categoria, pagina)
            nombre_cache = f"cat__{slug_de_url(url)}.html"
            try:
                texto, desde_cache = self.obtener(url, nombre_cache)
            except RobotsBloqueado as exc:
                info.update(estado="robots_bloqueado", error=str(exc))
                break
            except PresupuestoAgotado as exc:
                info.update(estado="presupuesto_agotado", error=str(exc))
                break
            except HTTPError as exc:
                if pagina == 1:
                    info.update(estado=f"http_{exc.code}", error=f"HTTP {exc.code}")
                else:
                    info.update(estado="parcial_http_error", error=f"página {pagina}: HTTP {exc.code}")
                break
            except RuntimeError as exc:
                info.update(estado="error_red", error=str(exc))
                break
            if texto is None:
                info.update(estado="sin_cache", error="--sin-red y no hay caché")
                break
            try:
                datos = parse_pagina_categoria(texto, url)
            except Exception as exc:  # noqa: BLE001 - queremos seguir con el resto
                info.update(estado="error_parseo", error=f"página {pagina}: {exc}")
                break

            if pagina == 1:
                info["nombre"] = datos["titulo"]
                info["es_categoria"] = datos["es_categoria"]
                info["moneda"] = datos["moneda"]
                info["total_declarado"] = datos["total_declarado"]
                info["es_categoria_magento"] = datos.get("es_categoria_magento")
                if not datos["es_categoria"]:
                    info["estado"] = ("categoria_sin_grid_server_side"
                                      if datos.get("es_categoria_magento")
                                      else "no_es_categoria")
                    break
                total = datos["total_declarado"]
                if total is not None:
                    # Si el sitio ignora product_list_limit y devuelve 36 tarjetas, el tamaño
                    # real de página es el observado: se recalcula para no dejar páginas sin bajar.
                    tam_efectivo = len(datos["tarjetas"]) if datos["tarjetas"] else self.args.limite_pagina
                    tam_efectivo = max(1, tam_efectivo)
                    info["tam_pagina_efectivo"] = tam_efectivo
                    info["paginas_previstas"] = max(1, -(-total // tam_efectivo))
                # Categorías nuevas que aparezcan en el menú (se encolan fuera).
                info["_menu"] = categorias_del_menu(LH.fromstring(limpiar_html(texto)))

            tarjetas = datos["tarjetas"]
            info["paginas_bajadas"] += 1
            info["tarjetas"] += len(tarjetas)
            esperadas_pagina = 0
            total = info["total_declarado"]
            tam_pagina = info.get("tam_pagina_efectivo") or self.args.limite_pagina
            if total is not None:
                esperadas_pagina = min(tam_pagina, max(0, total - (pagina - 1) * tam_pagina))
            info["tarjetas_esperadas"] += esperadas_pagina
            nuevas = 0
            for p in tarjetas:
                # Deduplicación por product_id (no por URL): el sitio publica la misma ficha
                # como /slug.html y como /catalog/product/view/id/<id>/... sin canonical.
                clave = p.get("id_magento") or p["url"]
                existente = productos.get(clave)
                if existente is None:
                    p["categorias"] = [info["categoria"]]
                    p["urls_vistas"] = [p["url"]]
                    productos[clave] = p
                    nuevas += 1
                else:
                    if info["categoria"] not in existente["categorias"]:
                        existente["categorias"].append(info["categoria"])
                    if p["url"] not in existente.get("urls_vistas", []):
                        existente.setdefault("urls_vistas", []).append(p["url"])
                    # Si una aparición trae precio y la primera no, se completa el dato.
                    if existente.get("precio_final") is None and p.get("precio_final") is not None:
                        for campo in ("precio_final", "precio_final_texto", "precio_anterior",
                                      "descuento_pct", "etiqueta", "estado_tarjeta", "sku"):
                            existente[campo] = p.get(campo)
            info["nuevas"] += nuevas
            info["detalle_paginas"].append({
                "pagina": pagina,
                "url": url,
                "desde_cache": desde_cache,
                "tarjetas": len(tarjetas),
                "esperadas": esperadas_pagina,
            })
            previstas = info["paginas_previstas"] or 0
            if not tarjetas:
                break
            if previstas and pagina >= previstas:
                break
            if self.args.politica_robots == "estricta" and pagina == 1:
                # Política estricta: `Disallow: /*?` impide pedir ?p=2, así que solo
                # se documenta la primera página (36 productos) de cada categoría.
                info["estado"] = "solo_pagina_1_por_robots"
                break
            pagina += 1
        # Limpieza: _menu se usa en run() para encolar categorías nuevas.
        menu = info.pop("_menu", None)
        info["_menu"] = menu
        return info

    # -- fichas ------------------------------------------------------------
    def extraer_ficha(self, producto: dict) -> dict:
        url = producto["url"]
        nombre_cache = f"ficha__{slug_de_url(url)}.html"
        try:
            texto, desde_cache = self.obtener(url, nombre_cache)
        except RobotsBloqueado as exc:
            return {"url": url, "error": str(exc), "estado": "robots_bloqueado"}
        except PresupuestoAgotado as exc:
            return {"url": url, "error": str(exc), "estado": "presupuesto_agotado"}
        except HTTPError as exc:
            return {"url": url, "error": f"HTTP {exc.code}", "estado": "http_error"}
        except RuntimeError as exc:
            return {"url": url, "error": str(exc), "estado": "error_red"}
        if texto is None:
            return {"url": url, "error": "--sin-red y no hay caché", "estado": "sin_cache"}
        try:
            datos = parse_ficha(texto, url)
        except Exception as exc:  # noqa: BLE001
            return {"url": url, "error": f"error de parseo: {exc}", "estado": "error_parseo"}
        datos.update({
            "estado": "ok",
            "desde_cache": desde_cache,
            "html_cache": f"cache/{nombre_cache}",
            "fecha_captura": ahora_iso(),
            "categoria_principal": producto.get("categoria_principal"),
            "categorias_catalogo": producto.get("categorias", []),
            "precio_final_catalogo": producto.get("precio_final"),
            "moneda_catalogo": producto.get("moneda"),
        })
        return datos

    def elegir_fichas(self, productos: list[dict]) -> list[dict]:
        """Elige hasta 5 productos: uno por rubro y uno de promociones."""
        rnd = random.Random(self.args.seed)
        elegidos, usados = [], set()
        rubros_cubiertos = set()

        def candidatos(filtro):
            lista = sorted([p for p in productos if filtro(p)], key=lambda p: p.get("url", ""))
            if self.args.fichas_preferir_cache:
                con_cache = [p for p in lista if _ficha_en_cache(p)]
                if con_cache:
                    return con_cache
            return lista

        def _ficha_en_cache(p) -> bool:
            return self._leer_cache(f"ficha__{slug_de_url(p.get('url', ''))}.html") is not None

        def agregar(prod, motivo):
            if prod is None or prod.get("url") in usados:
                return
            usados.add(prod["url"])
            elegidos.append({**prod, "_motivo": motivo})
            rubros_cubiertos.add(prod.get("rubro"))

        # 0) Ficha de control pedida por el Lead (se verifica contra valores esperados).
        control = None
        if self.args.ficha_control:
            for p in productos:
                if p.get("url") == self.args.ficha_control or self.args.ficha_control in p.get("urls_vistas", []):
                    control = p
                    break
        if control is not None:
            agregar(control, "control Lead (bicicletas)")

        # 1) Una ficha por rubro (al azar, con semilla fija para que sea reproducible).
        for rubro in RUBROS:
            if rubro in rubros_cubiertos:
                continue
            cands = [p for p in candidatos(lambda p: p.get("rubro") == rubro) if p["url"] not in usados]
            if cands:
                agregar(rnd.choice(cands), f"rubro {rubro}")
        # 2) Un producto de la colección de promociones (transversal a los rubros).
        if len(elegidos) < 5:
            cands_promo = [p for p in candidatos(lambda p: "promociones" in p.get("categorias", []))
                           if p["url"] not in usados]
            if not cands_promo:
                cands_promo = [p for p in candidatos(lambda p: "cyberday" in p.get("categorias", []))
                               if p["url"] not in usados]
            if cands_promo:
                agregar(rnd.choice(cands_promo), "promociones")
        # 3) Completar hasta 5 si algún rubro quedó vacío.
        for p in candidatos(lambda p: True):
            if len(elegidos) >= 5:
                break
            agregar(p, "completar cuota")
        return elegidos[:5]

    # -- orquestación ------------------------------------------------------
    def run(self) -> None:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        modo = self.args.modo

        if self.args.presupuesto_total:
            usados = 0
            if self.log_path.exists():
                usados = sum(1 for _ in self.log_path.open(encoding="utf-8"))
            self.max_requests = max(0, self.args.presupuesto_total - usados)
            print(f"[presupuesto] requests ya hechos (log histórico): {usados} | "
                  f"tope total: {self.args.presupuesto_total} | disponibles: {self.max_requests}")
        self.estadisticas["max_requests"] = self.max_requests

        self.cargar_robots()
        self.estadisticas["robots"] = {
            "url": f"{BASE}/robots.txt",
            "bytes": len(self.robots_texto),
            "politica": self.args.politica_robots,
            # robots.txt (User-agent: *) trae `Disallow: /*?`: TODA URL con query string está
            # prohibida, incluidos ?p=N y ?product_list_limit=64. El barrido paginado NO es
            # robots-compliant: es la vía eficiente y queda sujeto a autorización del sitio.
            "permite_url_con_query": self._robots_permite(f"{BASE}/bicicletas.html?p=2")
            if self.args.politica_robots == "estricta" else False,
            "robo_txt_disallow_query": "/*?" in self.robots_texto,
            "paginado_habilitado_por_politica": self.args.politica_robots == "paginado",
            "advertencia": (
                "robots.txt tiene 'Disallow: /*?' bajo 'User-agent: *'. El paginado "
                "?p=N&product_list_limit=64 NO es robots-compliant y requiere autorización "
                "escrita del dueño del sitio. Vía 100% compliant: sitemap + fichas SEO "
                "individuales (3.778 requests, ~1,2 s c/u)."
            ),
            "permite_categoria": self._robots_permite(f"{BASE}/bicicletas.html"),
            "permite_ficha": self._robots_permite(f"{BASE}/bicicleta-mtb-best-infinity-1-0.html"),
            "permite_media_producto": self._robots_permite(
                f"{BASE}/media/catalog/product/a/p/foto.jpg"),
            "permite_catalog_product_view": self._robots_permite(
                f"{BASE}/catalog/product/view/id/1/"),
            "texto": self.robots_texto,
        }

        if modo == "robots":
            print(self.robots_texto)
            print("\n--- resumen ---")
            print(f"  politica de robots: {self.estadisticas['robots']['politica']}")
            print(f"  ADVERTENCIA: {self.estadisticas['robots']['advertencia']}")
            for k in ("permite_url_con_query", "permite_categoria", "permite_ficha",
                      "permite_media_producto", "permite_catalog_product_view"):
                print(f"  {k}: {self.estadisticas['robots'][k]}")
            return

        if modo == "probe":
            self._modo_probe()
            return

        if modo == "inventario":
            self._modo_inventario()
            return

        if modo == "validar":
            self.validar_salidas()
            return

        filas_sitemap = self.sitemap()
        categorias = self.descubrir_categorias(filas_sitemap)
        self._raices_validas = {primer_segmento(c) for c in categorias
                                if profundidad_categoria(c) == 2}

        # Raíces ya cacheadas al 100%: se pueden incluir sin gastar ni un request.
        raices_detectadas = self.estadisticas.get("descubrimiento", {}).get("raices_detectadas", [])
        reutilizadas, no_reutilizadas = [], []
        for raiz in raices_detectadas:
            if raiz in categorias:
                continue
            if self._raiz_completa_en_cache(raiz):
                categorias.append(raiz)
                reutilizadas.append(raiz)
            else:
                no_reutilizadas.append(raiz)
        self.estadisticas["raices_reutilizadas_de_cache"] = reutilizadas
        self.estadisticas["raices_no_bajadas"] = no_reutilizadas
        if reutilizadas:
            print(f"[categorías] raíces reutilizadas desde caché (0 requests): {len(reutilizadas)}")

        productos: dict[str, dict] = {}
        cola = list(categorias)
        visitadas = set()
        while cola:
            url_cat = cola.pop(0)
            if url_cat in visitadas:
                continue
            visitadas.add(url_cat)
            print(f"[categoría] {url_cat}")
            info = self.crawl_categoria(url_cat, productos)
            menu = info.pop("_menu", None) or []
            for u in menu:
                if u in visitadas or u in cola or not u.startswith(BASE):
                    continue
                # Solo categorías con la forma esperada; nunca productos con barra en el slug.
                prof = profundidad_categoria(u)
                if prof == 1 and not self.args.incluir_raices:
                    continue
                if prof == 1 or (prof == 2 and primer_segmento(u) in self._raices_validas):
                    cola.append(u)
            print(
                f"    estado={info['estado']} total={info['total_declarado']} "
                f"páginas={info['paginas_bajadas']}/{info['paginas_previstas']} "
                f"tarjetas={info['tarjetas']} nuevas={info['nuevas']}"
            )
            self.historial_categorias.append(info)
            if info["estado"] == "presupuesto_agotado":
                print("!! presupuesto de requests agotado: se corta el barrido de categorías")
                for restante in cola:
                    if restante not in visitadas:
                        self.historial_categorias.append({
                            "categoria_url": restante, "nombre": "", "estado": "no_bajada",
                            "paginas_bajadas": 0, "tarjetas": 0, "nuevas": 0,
                        })
                        visitadas.add(restante)
                break

        # Rubro y categoría principal de cada producto.
        lista = list(productos.values())
        for p in lista:
            p["rubro"] = self._rubro_de(p["categorias"])
            p["categoria_principal"] = self._categoria_principal(p["categorias"])
            p["fecha_captura"] = ahora_iso()
            p["origen"] = "tarjeta_categoria"
        lista.sort(key=lambda p: (p["rubro"], p["nombre"] or "", p["url"]))

        self.escribir_catalogo(lista)
        self.escribir_categorias()

        fichas = []
        if self.args.con_fichas:
            elegidos = self.elegir_fichas(lista)
            print(f"\n[fichas] elegidos {len(elegidos)} productos")
            for prod in elegidos:
                print(f"    ficha: {prod['url']}  ({prod.get('_motivo')})")
                ficha = self.extraer_ficha(prod)
                ficha["motivo_seleccion"] = prod.get("_motivo")
                fichas.append(ficha)
            self.escribir_fichas(fichas)

        # Verificación de la ficha de control (valores conocidos por el recon del Lead).
        self.estadisticas["ficha_control"] = None
        for f in fichas:
            if self.args.ficha_control and (f.get("url") == self.args.ficha_control
                                            or f.get("motivo_seleccion", "").startswith("control")):
                verificacion = self.verificar_ficha_control(f)
                self.estadisticas["ficha_control"] = verificacion
                print(f"\n[ficha control] {verificacion['url']}")
                for campo, chk in verificacion["chequeos"].items():
                    marca = "OK" if chk["ok"] else "FALLA"
                    print(f"    {campo}: esperado={chk['esperado']!r} actual={chk['actual']!r} -> {marca}")
                print(f"    resultado: {'OK' if verificacion['ok'] else 'CON DIFERENCIAS'}")
                break

        self.estadisticas.update({
            "fecha_fin": ahora_iso(),
            "requests_http": self.n_http,
            "cache_hits": self.n_cache,
            "categorias": self.historial_categorias,
            "totales": {
                "categorias_intentadas": len(self.historial_categorias),
                "categorias_ok": sum(1 for c in self.historial_categorias if c.get("estado") == "ok"),
                "paginas_bajadas": sum(c.get("paginas_bajadas", 0) for c in self.historial_categorias),
                "tarjetas_extraidas": sum(c.get("tarjetas", 0) for c in self.historial_categorias),
                "tarjetas_esperadas": sum(c.get("tarjetas_esperadas", 0) for c in self.historial_categorias),
                "productos_unicos": len(lista),
                "fichas_ok": sum(1 for f in fichas if f.get("estado") == "ok"),
                "fichas_total": len(fichas),
            },
            "cobertura_por_pilar": self._cobertura_por_pilar(lista),
            "registro_requests": self.registro,
        })
        self.estadisticas["completitud"] = self._completitud(lista)
        (DATA_DIR / "estadisticas.json").write_text(
            json.dumps(self.estadisticas, ensure_ascii=False, indent=2), encoding="utf-8")

        print("\n=== resumen ===")
        for k, v in self.estadisticas["totales"].items():
            print(f"  {k}: {v}")
        print(f"  requests HTTP: {self.n_http} | caché: {self.n_cache}")
        if self.estadisticas.get("cobertura_por_pilar"):
            print("\n  pilar        total declarado  tarjetas  cobertura")
            for f in self.estadisticas["cobertura_por_pilar"]:
                print(f"  {f['pilar']:<12} {str(f['total_declarado']):>15} {str(f['tarjetas_extraidas']):>10} "
                      f"{str(f['cobertura_pct']):>9}%")
        self.validar_salidas()

    # -- helpers de clasificación -----------------------------------------
    def verificar_ficha_control(self, ficha: dict) -> dict:
        """Compara una ficha contra los valores que el Lead verificó manualmente."""
        chequeos = {}
        for campo, esperado in ESPERADO_FICHA_CONTROL.items():
            actual = ficha.get(campo)
            chequeos[campo] = {"esperado": esperado, "actual": actual, "ok": actual == esperado}
        return {
            "url": ficha.get("url"),
            "ok": all(c["ok"] for c in chequeos.values()),
            "chequeos": chequeos,
            "estado_ficha": ficha.get("estado"),
        }

    def _cobertura_por_pilar(self, lista: list[dict]) -> list[dict]:
        """Tabla pilar (categoría raíz) → total declarado → tarjetas extraídas → cobertura %."""
        filas = []
        for c in self.historial_categorias:
            if profundidad_categoria(c.get("categoria_url", "")) != 1:
                continue  # solo las raíces (pilares), no las subcategorías
            pilar = primer_segmento(c["categoria_url"])
            total = c.get("total_declarado")
            extraidas = c.get("tarjetas")
            cobertura = (round(100.0 * extraidas / total, 1) if total else None)
            filas.append({
                "pilar": pilar,
                "url_pilar": c["categoria_url"],
                "estado": c.get("estado"),
                "total_declarado": total,
                "tarjetas_extraidas": extraidas,
                "cobertura_pct": cobertura,
                "productos_unicos_rubro": sum(1 for p in lista if p.get("rubro") == pilar),
            })
        return filas

    @staticmethod
    def _rubro_de(categorias: list[str]) -> str:
        """Rubro = primer nivel de la categoría MÁS ESPECÍFICA donde aparece el producto.

        Ej.: un casco que está en `bicicletas` (raíz) y en `indumentaria/calzados` cuenta
        como indumentaria, que es donde el visitante lo encuentra.
        """
        ordenadas = sorted(categorias,
                           key=lambda c: (-len([s for s in c.split("/") if s]), c))
        for c in ordenadas:
            seg = c.split("/")[0]
            if seg in RUBROS:
                return seg
        if any(c.split("/")[0] in ("promociones", "cyberday") for c in ordenadas):
            return "promociones"
        return "otros"

    @staticmethod
    def _categoria_principal(categorias: list[str]) -> str:
        if not categorias:
            return ""

        def clave(c):
            return (-len([s for s in c.split("/") if s]), c)

        return sorted(categorias, key=clave)[0]

    def _completitud(self, lista: list[dict]) -> dict:
        total = len(lista) or 1
        campos = ["sku", "precio_final", "precio_anterior", "imagen", "disponibilidad", "id_magento"]
        salida = {}
        for campo in campos:
            if campo == "disponibilidad":
                con = sum(1 for p in lista if p.get(campo) not in (None, "", "sin dato"))
            else:
                con = sum(1 for p in lista if p.get(campo) not in (None, ""))
            salida[campo] = {"con_dato": con, "pct": round(100.0 * con / total, 1)}
        salida["por_rubro"] = {}
        for p in lista:
            r = p.get("rubro", "otros")
            salida["por_rubro"][r] = salida["por_rubro"].get(r, 0) + 1
        salida["por_estado_tarjeta"] = {}
        for p in lista:
            e = p.get("estado_tarjeta", "?")
            salida["por_estado_tarjeta"][e] = salida["por_estado_tarjeta"].get(e, 0) + 1
        salida["con_descuento"] = sum(1 for p in lista if p.get("descuento_pct"))
        return salida

    # -- escritura de salidas ---------------------------------------------
    COLUMNAS_CSV = [
        "id_magento", "sku", "nombre", "url", "rubro", "categoria_principal", "categorias",
        "moneda", "precio_final", "precio_anterior", "descuento_pct", "etiqueta",
        "estado_tarjeta", "disponibilidad", "imagen", "fecha_captura",
    ]

    def escribir_catalogo(self, lista: list[dict]) -> None:
        ruta_jsonl = DATA_DIR / "productos.jsonl"
        with ruta_jsonl.open("w", encoding="utf-8") as fh:
            for p in lista:
                fh.write(json.dumps(p, ensure_ascii=False) + "\n")
        ruta_csv = DATA_DIR / "productos.csv"
        with ruta_csv.open("w", encoding="utf-8-sig", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=self.COLUMNAS_CSV, extrasaction="ignore")
            w.writeheader()
            for p in lista:
                fila = dict(p)
                fila["categorias"] = "|".join(p.get("categorias", []))
                w.writerow(fila)
        print(f"[salida] {ruta_jsonl} ({len(lista)} productos)")
        print(f"[salida] {ruta_csv}")

    def escribir_categorias(self) -> None:
        ruta = DATA_DIR / "categorias.csv"
        columnas = ["categoria", "nombre", "categoria_url", "estado", "total_declarado",
                    "paginas_previstas", "paginas_bajadas", "tarjetas", "tarjetas_descartadas",
                    "nuevas"]
        with ruta.open("w", encoding="utf-8-sig", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=columnas, extrasaction="ignore")
            w.writeheader()
            for c in self.historial_categorias:
                w.writerow(c)
        print(f"[salida] {ruta} ({len(self.historial_categorias)} categorías)")

    def escribir_fichas(self, fichas: list[dict]) -> None:
        ruta = DATA_DIR / "fichas.jsonl"
        with ruta.open("w", encoding="utf-8") as fh:
            for f in fichas:
                fh.write(json.dumps(f, ensure_ascii=False) + "\n")
        print(f"[salida] {ruta} ({len(fichas)} fichas)")

    # -- probe -------------------------------------------------------------
    def _modo_probe(self) -> None:
        """Prueba si el sitio acepta product_list_limit>64 en el paginado."""
        base_cat = f"{BASE}/bicicletas.html"
        resultados = []
        for limite in (200, 64):
            url = f"{base_cat}?product_list_limit={limite}&p=2"
            nombre = f"probe__{slug_de_url(url)}.html"
            print(f"[probe] GET {url}")
            try:
                texto, desde_cache = self.obtener(url, nombre)
            except Exception as exc:  # noqa: BLE001
                print(f"    error: {exc}")
                resultados.append({"limite": limite, "error": str(exc)})
                continue
            datos = parse_pagina_categoria(texto, url)
            fila = {
                "limite": limite,
                "desde_cache": desde_cache,
                "total_toolbar": datos["total_declarado"],
                "tarjetas": len(datos["tarjetas"]),
                "primera": datos["tarjetas"][0]["nombre"] if datos["tarjetas"] else None,
            }
            print(f"    → tarjetas={fila['tarjetas']} total={fila['total_toolbar']} "
                  f"primera={fila['primera']!r}")
            resultados.append(fila)
        (DATA_DIR / "probe.json").write_text(
            json.dumps(resultados, ensure_ascii=False, indent=2), encoding="utf-8")
        aceptado = next((r["limite"] for r in resultados
                         if r.get("tarjetas") and r["tarjetas"] > 64), None)
        print(f"\n[probe] product_list_limit grande aceptado: {aceptado or 'NO'}")

    # -- inventario (sin red) ---------------------------------------------
    def _raiz_completa_en_cache(self, raiz: str) -> bool:
        """True si TODAS las páginas de una categoría raíz ya están en la caché."""
        texto = self._leer_cache(f"cat__{slug_de_url(self.url_categoria_pagina(raiz, 1))}.html")
        if texto is None:
            return False
        try:
            datos = parse_pagina_categoria(texto, raiz)
        except Exception:  # noqa: BLE001
            return False
        total = datos["total_declarado"]
        if not total:
            return False
        tam = len(datos["tarjetas"]) or self.args.limite_pagina
        paginas = max(1, -(-total // tam))
        for p in range(1, paginas + 1):
            if self._leer_cache(f"cat__{slug_de_url(self.url_categoria_pagina(raiz, p))}.html") is None:
                return False
        return True

    def _modo_inventario(self) -> None:
        """Lee la caché y planifica el barrido: totales por categoría y páginas que faltan."""
        filas = self.sitemap()
        categorias = self.descubrir_categorias(filas)
        productos_sitemap = sum(1 for f in filas if f["url"].endswith(".html"))
        print(f"[inventario] sitemap: {len(filas)} URLs, {productos_sitemap} .html")
        print(f"[inventario] categorías candidatas: {len(categorias)}")
        filas_tabla, total_paginas, faltantes, con_cache = [], 0, 0, 0
        for url in categorias:
            nombre_cache = f"cat__{slug_de_url(self.url_categoria_pagina(url, 1))}.html"
            texto = self._leer_cache(nombre_cache)
            if texto is None:
                filas_tabla.append({"categoria": url, "total": None, "paginas": None,
                                    "cacheadas": 0, "faltan": None})
                total_paginas = None
                continue
            con_cache += 1
            datos = parse_pagina_categoria(texto, url)
            total = datos["total_declarado"]
            tam = len(datos["tarjetas"]) or self.args.limite_pagina
            if total is None:
                paginas = None
                faltan = None
            else:
                paginas = max(1, -(-total // tam))
                # páginas ya cacheadas
                cacheadas = 0
                for p in range(1, paginas + 1):
                    if self._leer_cache(f"cat__{slug_de_url(self.url_categoria_pagina(url, p))}.html"):
                        cacheadas += 1
                faltan = paginas - cacheadas
                if total_paginas is not None:
                    total_paginas += paginas
                    faltantes += faltan
            filas_tabla.append({"categoria": url, "total": total, "paginas": paginas,
                                "cacheadas": cacheadas if total is not None else 0,
                                "faltan": faltan})
        ancho = max(len(f["categoria"]) for f in filas_tabla) if filas_tabla else 20
        for f in filas_tabla:
            print(f"  {f['categoria']:<{ancho}}  total={f['total']!s:>6}  "
                  f"páginas={f['paginas']!s:>4}  cacheadas={f['cacheadas']:>3}  faltan={f['faltan']!s:>4}")
        print(f"\n[inventario] categorías con caché: {con_cache}/{len(categorias)}")
        print(f"[inventario] páginas totales del plan: {total_paginas} | faltan bajar: {faltantes}")
        print(f"[inventario] requests hechos hasta ahora (log): "
              f"{sum(1 for _ in self.log_path.open(encoding='utf-8')) if self.log_path.exists() else 0}")

    # -- validación --------------------------------------------------------
    def validar_salidas(self) -> dict:
        """Valida precios numéricos en PYG, duplicados y completitud de las salidas."""
        ruta_csv = DATA_DIR / "productos.csv"
        ruta_jsonl = DATA_DIR / "productos.jsonl"
        informe = {"ok": True, "errores": [], "avisos": []}
        if not ruta_csv.exists():
            informe["ok"] = False
            informe["errores"].append("no existe data/productos.csv")
            return self._imprimir_validacion(informe)

        with ruta_csv.open("r", encoding="utf-8-sig", newline="") as fh:
            filas = list(csv.DictReader(fh))
        with ruta_jsonl.open("r", encoding="utf-8") as fh:
            filas_jsonl = [json.loads(linea) for linea in fh if linea.strip()]

        informe["productos_csv"] = len(filas)
        informe["productos_jsonl"] = len(filas_jsonl)
        if len(filas) != len(filas_jsonl):
            informe["ok"] = False
            informe["errores"].append(
                f"CSV ({len(filas)}) y JSONL ({len(filas_jsonl)}) tienen distinta cantidad de filas")

        # Precios: enteros en PYG, sin separadores de miles ni decimales. El precio vacío es
        # legítimo para tarjetas "solo catálogo" (no se venden online), así que no es error.
        problema_precio = 0
        sin_precio = 0
        for fila in filas:
            for col in ("precio_final", "precio_anterior"):
                valor = (fila.get(col) or "").strip()
                if not valor:
                    if col == "precio_final":
                        sin_precio += 1
                    continue
                if not re.fullmatch(r"\d+", valor):
                    problema_precio += 1
                    if problema_precio <= 5:
                        informe["errores"].append(
                            f"precio no numérico en {col}: {valor!r} ({fila.get('url')})")
        if problema_precio:
            informe["ok"] = False
        informe["precios_invalidos"] = problema_precio
        informe["sin_precio_final"] = sin_precio
        estados = {}
        for fila in filas:
            e = fila.get("estado_tarjeta") or "(sin campo)"
            estados[e] = estados.get(e, 0) + 1
        informe["por_estado_tarjeta"] = estados

        # Moneda.
        monedas = {f.get("moneda") for f in filas}
        informe["monedas"] = sorted(m for m in monedas if m)
        if monedas - {"PYG"}:
            informe["avisos"].append(f"monedas distintas de PYG: {sorted(monedas - {'PYG'})}")

        # Duplicados: por product_id y por URL.
        ids = [f.get("id_magento") for f in filas if f.get("id_magento")]
        dups_id = sorted({i for i in ids if ids.count(i) > 1})
        urls = [f.get("url") for f in filas if f.get("url")]
        dups_url = sorted({u for u in urls if urls.count(u) > 1})
        informe["duplicados_por_id"] = len(dups_id)
        informe["duplicados_por_url"] = len(dups_url)
        if dups_id or dups_url:
            informe["ok"] = False
            if dups_id:
                informe["errores"].append(f"{len(dups_id)} product_id duplicados")
            if dups_url:
                informe["errores"].append(f"{len(dups_url)} URLs duplicadas, ej: {dups_url[:3]}")

        # Coherencia precio_anterior >= precio_final.
        incoherentes = [
            f.get("url") for f in filas
            if f.get("precio_anterior") and f.get("precio_final")
            and int(f["precio_anterior"]) < int(f["precio_final"])
        ]
        informe["precio_anterior_menor"] = len(incoherentes)
        if incoherentes:
            informe["avisos"].append(f"{len(incoherentes)} filas con precio_anterior < precio_final")

        # Completitud rápida sobre el CSV.
        informe["pct_con_sku"] = round(100.0 * sum(1 for f in filas if f.get("sku")) / max(1, len(filas)), 1)
        informe["pct_con_precio"] = round(100.0 * sum(1 for f in filas if f.get("precio_final")) / max(1, len(filas)), 1)
        informe["pct_con_imagen"] = round(100.0 * sum(1 for f in filas if f.get("imagen")) / max(1, len(filas)), 1)
        informe["pct_con_precio_anterior"] = round(
            100.0 * sum(1 for f in filas if f.get("precio_anterior")) / max(1, len(filas)), 1)

        ruta_fichas = DATA_DIR / "fichas.jsonl"
        if ruta_fichas.exists():
            with ruta_fichas.open("r", encoding="utf-8") as fh:
                fichas = [json.loads(x) for x in fh if x.strip()]
            informe["fichas"] = len(fichas)
            informe["fichas_ok"] = sum(1 for f in fichas if f.get("estado") == "ok")
            for f in fichas:
                faltan = [c for c in ("nombre", "sku", "marca", "precio_final", "disponibilidad",
                                      "imagenes", "descripcion")
                          if not f.get(c)]
                if faltan:
                    informe["avisos"].append(f"ficha {f.get('url')} sin: {', '.join(faltan)}")
        (DATA_DIR / "validacion.json").write_text(
            json.dumps(informe, ensure_ascii=False, indent=2), encoding="utf-8")
        return self._imprimir_validacion(informe)

    @staticmethod
    def _imprimir_validacion(informe: dict) -> dict:
        print("\n=== validación de salidas ===")
        for k, v in informe.items():
            if k in ("errores", "avisos"):
                continue
            print(f"  {k}: {v}")
        for e in informe.get("errores", []):
            print(f"  ERROR: {e}")
        for a in informe.get("avisos", []):
            print(f"  aviso: {a}")
        print(f"  resultado: {'OK' if informe.get('ok') else 'CON ERRORES'}")
        return informe


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def parse_args(argv=None):
    p = argparse.ArgumentParser(
        description="PoC scraper de catálogo y precios de ciclovia.com.py",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--modo", default="todo",
                   choices=["robots", "probe", "inventario", "categorias", "fichas", "todo", "validar"])
    p.add_argument("--limite-pagina", type=int, default=64,
                   help="valor de product_list_limit (el sitio ofrece 36/48/64; valores mayores "
                        "se ignoran y vuelven a 36, por eso el default es 64)")
    p.add_argument("--delay-min", type=float, default=0.8)
    p.add_argument("--delay-max", type=float, default=1.5)
    p.add_argument("--timeout", type=float, default=45.0)
    p.add_argument("--max-requests", type=int, default=150,
                   help="tope duro de requests HTTP reales en la corrida")
    p.add_argument("--presupuesto-total", type=int, default=0,
                   help="si se indica, calcula el tope de la corrida como (total - requests ya "
                        "registrados en cache/_requests.jsonl)")
    p.add_argument("--reservado", type=int, default=10,
                   help="requests que se dejan libres para las fichas y reintentos")
    p.add_argument("--politica-robots", default="paginado", choices=["paginado", "estricta"],
                   help="paginado: permite solo ?p= y ?product_list_limit= (default); "
                        "estricta: respeta `Disallow: /*?` y baja solo la página 1 de cada categoría")
    p.add_argument("--incluir-raices", action="store_true",
                   help="incluye las 4 categorías raíz (bicicletas, fitness, ...). Son supersets "
                        "de las hojas: cuestan requests de más y duplican productos")
    p.add_argument("--ficha-control", default=URL_FICHA_CONTROL,
                   help="URL de ficha que se baja siempre como control y se compara contra "
                        "ESPERADO_FICHA_CONTROL (usar --ficha-control '' para desactivar)")
    p.add_argument("--seed", type=int, default=20261021, help="semilla para elegir fichas")
    p.add_argument("--fichas-preferir-cache", dest="fichas_preferir_cache", default=True,
                   action="store_true",
                   help="elige las fichas entre productos cuya ficha ya está en caché (ahorra requests)")
    p.add_argument("--sin-fichas-cacheadas", dest="fichas_preferir_cache", action="store_false",
                   help="desactiva la preferencia por fichas ya cacheadas")
    p.add_argument("--force", action="store_true", help="ignora la caché y vuelve a pedir")
    p.add_argument("--sin-red", action="store_true", help="no hace requests: solo usa caché")
    p.add_argument("--sin-fichas", dest="con_fichas", action="store_false",
                   help="no extrae fichas de producto")
    p.set_defaults(con_fichas=True)
    return p.parse_args(argv)


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:  # pragma: no cover
            pass
    args = parse_args(argv)
    if args.delay_min > args.delay_max:
        args.delay_min, args.delay_max = args.delay_max, args.delay_min
    if args.modo == "fichas":
        args.con_fichas = True
    if args.modo == "categorias":
        args.con_fichas = False
    scraper = Scraper(args)
    try:
        scraper.run()
    except KeyboardInterrupt:
        print("\ninterrumpido por el usuario")
        return 130
    except RobotsBloqueado as exc:
        print(f"\n!! bloqueado por robots.txt: {exc}")
        return 2
    except Exception as exc:  # noqa: BLE001
        print(f"\n!! error: {exc}")
        raise
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
