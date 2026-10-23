#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Genera el feed de productos para Meta (Facebook/Instagram) a partir del catálogo
de la tienda. El archivo queda publicado en:

    https://llnikoll.github.io/jaka.com/publicidad/catalogo-meta.csv

Uso:
    python publicidad/generar_feed.py
    python publicidad/generar_feed.py --min-precio 800000 --solo-stock
    python publicidad/generar_feed.py --salida otra/ruta.csv

Campos que pide Meta Commerce Manager:
  id, title, description, availability, condition, price, link, image_link,
  brand, google_product_category (+ etiquetas propias para armar conjuntos)
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ENTRADA = RAIZ / "tienda" / "data" / "v" / "todos.json"
CONFIG = RAIZ / "tienda" / "assets" / "config.js"
SALIDA = RAIZ / "tienda" / "publicidad" / "catalogo-meta.csv"

SITIO = "https://llnikoll.github.io/jaka.com/"
IMG_BASE = "https://www.ciclovia.com.py/media/catalog/product/"
IMG_PARAMS = "?quality=85&fit=bounds&height=800&width=800&canvas=800:800"
MONEDA = "PYG"
MARCA_FALLBACK = "Jaka"

CATEGORIA_GOOGLE = {
    "bicicletas/mtb": "Sporting Goods > Outdoor Recreation > Cycling > Bicycles",
    "bicicletas/ruta": "Sporting Goods > Outdoor Recreation > Cycling > Bicycles",
    "bicicletas/urbanas": "Sporting Goods > Outdoor Recreation > Cycling > Bicycles",
    "bicicletas/infantil": "Sporting Goods > Outdoor Recreation > Cycling > Bicycles",
    "bicicletas/electricas": "Sporting Goods > Outdoor Recreation > Cycling > Bicycles",
    "bicicletas/repuestos-de-bicicletas": "Sporting Goods > Outdoor Recreation > Cycling > Bicycle Accessories",
    "fitness/cintas": "Sporting Goods > Exercise & Fitness > Cardio Machines",
    "fitness/elipticas": "Sporting Goods > Exercise & Fitness > Cardio Machines",
    "fitness/bicicletas": "Sporting Goods > Exercise & Fitness > Cardio Machines",
    "fitness/spinning": "Sporting Goods > Exercise & Fitness > Cardio Machines",
    "fitness/remos": "Sporting Goods > Exercise & Fitness > Cardio Machines",
    "fitness/escaladoras": "Sporting Goods > Exercise & Fitness > Cardio Machines",
    "fitness/accesorios": "Sporting Goods > Exercise & Fitness",
    "fitness/abdominalera": "Sporting Goods > Exercise & Fitness",
    "fitness/suplementos-alimenticios": "Health & Beauty > Health Care > Fitness & Nutrition",
    "indumentaria/remeras": "Apparel & Accessories > Clothing",
    "indumentaria/abrigos": "Apparel & Accessories > Clothing",
    "indumentaria/shorts": "Apparel & Accessories > Clothing",
    "indumentaria/calzados": "Apparel & Accessories > Shoes",
    "indumentaria/mochilas": "Luggage & Bags",
    "indumentaria/guantes": "Apparel & Accessories > Clothing Accessories > Gloves & Mittens",
    "indumentaria/lentes": "Apparel & Accessories > Clothing Accessories > Sunglasses",
    "autoaccesorios/portabultos": "Vehicles & Parts > Vehicle Parts & Accessories",
    "autoaccesorios/portabici": "Vehicles & Parts > Vehicle Parts & Accessories",
}
CATEGORIA_POR_DEFECTO = "Sporting Goods"

PILARES = ("bicicletas", "fitness", "indumentaria", "autoaccesorios")


def leer_recargo() -> tuple[float, float, int, bool]:
    """Toma los parámetros de precio de tienda/assets/config.js."""
    recargo, extra, umbral, redondeo = 15.0, 0.0, 0, True
    try:
        texto = CONFIG.read_text(encoding="utf-8")
        m = re.search(r"recargoPct\s*:\s*([0-9.]+)", texto)
        if m:
            recargo = float(m.group(1))
        m = re.search(r"recargoBajoPct\s*:\s*([0-9.]+)", texto)
        if m:
            extra = float(m.group(1))
        m = re.search(r"umbralBajo\s*:\s*([0-9.]+)", texto)
        if m:
            umbral = int(float(m.group(1)))
        if re.search(r"redondeoPrecio\s*:\s*false", texto):
            redondeo = False
    except OSError:
        pass
    return recargo, extra, umbral, redondeo


def redondear(valor: float, redondeo: bool) -> int:
    if not redondeo:
        return round(valor)
    paso = 10 if valor < 1000 else 100 if valor < 100000 else 1000 if valor < 1000000 else 10000
    return int(math.ceil(valor / paso) * paso)


def precio_venta(valor: int, recargo: float, extra: float, umbral: int, redondeo: bool) -> int:
    """Misma fórmula que la tienda: +recargo y, si queda barato, +extra."""
    if not valor:
        return 0
    precio = redondear(valor * (1 + recargo / 100), redondeo) if recargo else round(valor)
    # El umbral se compara contra el precio ORIGINAL, no contra el ya aumentado
    if extra > 0 and umbral > 0 and valor <= umbral:
        precio = redondear(precio * (1 + extra / 100), redondeo)
    return precio


def vista_de(producto: dict) -> str:
    cats = producto.get("c") or []
    if "bicicletas/repuestos-de-bicicletas" in cats:
        return "accesorios"
    for cat in cats:
        pilar = cat.split("/")[0]
        if pilar in PILARES:
            return pilar
    return "todos"


def categoria_google(producto: dict) -> str:
    for cat in producto.get("c") or []:
        if cat in CATEGORIA_GOOGLE:
            return CATEGORIA_GOOGLE[cat]
    pilar = (producto.get("c") or [""])[0].split("/")[0]
    return {
        "bicicletas": "Sporting Goods > Outdoor Recreation > Cycling",
        "fitness": "Sporting Goods > Exercise & Fitness",
        "indumentaria": "Apparel & Accessories",
        "autoaccesorios": "Vehicles & Parts > Vehicle Parts & Accessories",
    }.get(pilar, CATEGORIA_POR_DEFECTO)


def limpiar(texto: str, largo: int = 200) -> str:
    limpio = re.sub(r"\s+", " ", str(texto or "")).strip()
    return limpio[:largo]


def main() -> None:
    parser = argparse.ArgumentParser(description="Genera el feed de Meta")
    parser.add_argument("--min-precio", type=int, default=0, help="omitir productos de venta menor a este monto")
    parser.add_argument("--solo-stock", action="store_true", help="omitir productos sin stock")
    parser.add_argument("--salida", type=Path, default=SALIDA)
    args = parser.parse_args()

    if not ENTRADA.exists():
        raise SystemExit(f"No encuentro {ENTRADA}. Corré antes tienda/build_catalogo.py")

    productos = json.loads(ENTRADA.read_text(encoding="utf-8"))
    recargo, extra, umbral, redondeo = leer_recargo()

    filas = []
    for p in productos:
        if not p.get("p"):
            continue
        if p.get("e") == 1 and args.solo_stock:
            continue
        precio = precio_venta(p["p"], recargo, extra, umbral, redondeo)
        if precio < args.min_precio:
            continue

        vista = vista_de(p)
        nombre = limpiar(p.get("n"), 150)
        marca = limpiar(p.get("m"), 60) or MARCA_FALLBACK
        categoria = categoria_google(p)
        descripcion = (
            f"{nombre}. {marca}. {categoria}. "
            "Disponible en Jaka Bicicletería — Asunción, Paraguay. "
            "Pedidos por WhatsApp con entrega en todo el país."
        )

        filas.append({
            "id": p["i"],
            "title": nombre,
            "description": descripcion,
            "availability": "out of stock" if p.get("e") == 1 else "in stock",
            "condition": "new",
            "price": f"{precio} {MONEDA}",
            "link": f"{SITIO}?p={p['i']}&v={vista}",
            "image_link": IMG_BASE + p["img"] + IMG_PARAMS if p.get("img") else "",
            "brand": marca,
            "google_product_category": categoria,
            "custom_label_0": vista,
            "custom_label_1": "agotado" if p.get("e") == 1 else "stock",
            "custom_label_2": "ticket-alto" if precio >= 800000 else ("ticket-medio" if precio >= 300000 else "ticket-bajo"),
        })

    filas.sort(key=lambda f: f["id"])
    args.salida.parent.mkdir(parents=True, exist_ok=True)
    campos = list(filas[0].keys()) if filas else []
    with args.salida.open("w", encoding="utf-8", newline="") as fh:
        escritor = csv.DictWriter(fh, fieldnames=campos, quoting=csv.QUOTE_MINIMAL)
        escritor.writeheader()
        escritor.writerows(filas)

    sin_stock = sum(1 for f in filas if f["availability"] == "out of stock")
    altos = sum(1 for f in filas if f["custom_label_2"] == "ticket-alto")
    kb = args.salida.stat().st_size / 1024
    print(f"OK -> {args.salida}")
    print(f"   {len(filas):,} productos · {sin_stock} sin stock · {altos} de ticket alto (>= Gs 800.000)")
    print(f"   recargo aplicado: {recargo}% · extra {extra}% para precios <= Gs {umbral:,}".replace(",", ".") + f" · {kb:,.0f} KB")
    print(f"   URL publicada: {SITIO}publicidad/catalogo-meta.csv")


if __name__ == "__main__":
    main()
