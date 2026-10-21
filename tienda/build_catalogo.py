#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Genera los datos que consume la tienda (tienda/data/):
  indice.json        -> categorías, vistas y metadatos (liviano, ~3 KB)
  v/<vista>.json     -> productos de cada vista (se cargan bajo demanda)
  catalogo.json/.js  -> catálogo completo (respaldo para abrir sin servidor)
  ultimos_cambios.json -> qué cambió respecto de la corrida anterior

Uso:
    python tienda/build_catalogo.py

Cuando se actualicen los precios en origen:
    1) python poc/scraper_ciclovia.py --modo todo --incluir-raices --force
    2) python tienda/build_catalogo.py
    3) subir tienda/data/ al hosting
"""

from __future__ import annotations

import csv
import html
import json
import re
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ENTRADA_PRODUCTOS = RAIZ / "poc" / "data" / "productos.jsonl"
ENTRADA_CATEGORIAS = RAIZ / "poc" / "data" / "categorias.csv"
SALIDA_DIR = Path(__file__).resolve().parent / "data"
SALIDA_INDICE = SALIDA_DIR / "indice.json"
SALIDA_VISTAS = SALIDA_DIR / "v"
SALIDA_COMPLETO = SALIDA_DIR / "catalogo.json"

PILARES = ["bicicletas", "fitness", "indumentaria", "autoaccesorios"]

MARCAS = [
    "SCOTT", "CANNONDALE", "BEST", "BRAVO", "CALOI", "RUSH", "ATHLETIC", "PRO-X",
    "THULE", "TEKNIAL", "ENA", "LIFE BALANCE", "ENACCION", "MAGNUM", "DYNAMIC",
    "OXFORD", "SHIMANO", "MAXXIS", "HORIZON", "VISION", "TECNO FITNESS", "VITALGEN",
    "GATEWAY", "KALF", "BEEBE", "FMD", "PRO RIDE",
]

ESTADO = {"con_precio": 0, "agotado": 1, "solo_catalogo": 2, "sin_dato": 3}

PREFIJO_IMG = "https://www.ciclovia.com.py/media/catalog/product/"

# Vistas (pestañas). El orden es el que se muestra en la tienda.
VISTAS = [
    {
        "slug": "accesorios",
        "nombre": "Accesorios",
        "categorias": ["bicicletas/repuestos-de-bicicletas"],
    },
    {
        "slug": "bicicletas",
        "nombre": "Bicicletas",
        "categorias": [
            "bicicletas/mtb", "bicicletas/ruta", "bicicletas/urbanas",
            "bicicletas/infantil", "bicicletas/electricas",
            "bicicletas/repuestos-de-bicicletas",
        ],
    },
    {
        "slug": "fitness",
        "nombre": "Fitness",
        "categorias": [
            "fitness/cintas", "fitness/elipticas", "fitness/bicicletas",
            "fitness/accesorios", "fitness/abdominalera", "fitness/spinning",
            "fitness/remos", "fitness/escaladoras", "fitness/suplementos-alimenticios",
        ],
    },
    {
        "slug": "indumentaria",
        "nombre": "Indumentaria",
        "categorias": [
            "indumentaria/remeras", "indumentaria/abrigos", "indumentaria/calzados",
            "indumentaria/mochilas", "indumentaria/shorts", "indumentaria/guantes",
            "indumentaria/lentes",
        ],
    },
    {
        "slug": "autoaccesorios",
        "nombre": "Autoaccesorios",
        "categorias": ["autoaccesorios/portabultos", "autoaccesorios/portabici"],
    },
    {"slug": "ofertas", "nombre": "Ofertas", "categorias": []},
    {"slug": "todos", "nombre": "Todos", "categorias": []},
]


def limpiar_texto(valor: str | None) -> str:
    if not valor:
        return ""
    v = str(valor).replace("\x00", " ")
    return re.sub(r"\s+", " ", v).strip()


def marca_de(nombre: str) -> str:
    mayus = nombre.upper()
    for marca in MARCAS:
        if mayus.startswith(marca) or f" {marca} " in f" {mayus} ":
            return marca
    return ""


def imagen_normalizada(url: str | None) -> str:
    if not url:
        return ""
    url = html.unescape(url).split("?")[0]
    if url.startswith(PREFIJO_IMG):
        return url[len(PREFIJO_IMG):]
    return url


def precio(valor) -> int | None:
    try:
        n = int(round(float(valor)))
    except (TypeError, ValueError):
        return None
    return n if n > 0 else None


def nombre_categoria(texto: str) -> str:
    palabras = []
    for palabra in str(texto or "").split():
        if len(palabra) <= 3:
            palabras.append(palabra.upper())
        else:
            palabras.append(palabra.capitalize())
    return " ".join(palabras)


def cargar_categorias() -> dict[str, dict]:
    mapa: dict[str, dict] = {}
    if not ENTRADA_CATEGORIAS.exists():
        return mapa
    with ENTRADA_CATEGORIAS.open(encoding="utf-8-sig", newline="") as fh:
        for fila in csv.DictReader(fh):
            slug = (fila.get("categoria") or "").strip()
            if not slug:
                continue
            mapa[slug] = {
                "nombre": nombre_categoria(limpiar_texto(fila.get("nombre"))),
                "pilar": slug.split("/")[0],
                "total": int(fila.get("total_declarado") or 0),
            }
    return mapa


def en_vista(producto: dict, vista: str) -> bool:
    cats = producto["c"]
    if vista == "ofertas":
        return bool(producto["of"])
    if vista == "todos":
        return True
    definicion = next(v for v in VISTAS if v["slug"] == vista)
    if any(c in definicion["categorias"] for c in cats):
        return True
    # productos que solo tienen la categoría raíz (sin subcategoría)
    return any(c == vista or c.startswith(f"{vista}/") for c in cats)


def catalogo_vacio(nuevos: list[dict], primera: bool) -> dict:
    """Resultado cuando no hay catálogo anterior (primera corrida o JSON dañado)."""
    return {
        "primera_vez": primera,
        "precios": [],
        "stock": [],
        "altas": [{"id": str(p["i"]), "nombre": p["n"]} for p in nuevos],
        "bajas": [],
    }


def comparar_con_anterior(nuevos: list[dict]) -> dict:
    if not SALIDA_COMPLETO.exists():
        return catalogo_vacio(nuevos, primera=True)
    try:
        previo = json.loads(SALIDA_COMPLETO.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return catalogo_vacio(nuevos, primera=True)

    antes = {str(p.get("i")): p for p in previo.get("productos", [])}
    despues = {str(p.get("i")): p for p in nuevos}
    precios, stock = [], []
    for pid, nuevo in despues.items():
        viejo = antes.get(pid)
        if not viejo:
            continue
        if viejo.get("p") != nuevo.get("p") or viejo.get("o") != nuevo.get("o"):
            precios.append({
                "id": pid, "nombre": nuevo["n"],
                "antes": viejo.get("p"), "despues": nuevo.get("p"),
                "antes_lista": viejo.get("o"), "despues_lista": nuevo.get("o"),
            })
        if viejo.get("e") != nuevo.get("e"):
            stock.append({"id": pid, "nombre": nuevo["n"], "antes": viejo.get("e"), "despues": nuevo.get("e")})
    return {
        "primera_vez": False,
        "precios": precios,
        "stock": stock,
        "altas": [{"id": pid, "nombre": p["n"]} for pid, p in despues.items() if pid not in antes],
        "bajas": [{"id": pid, "nombre": p["n"]} for pid, p in antes.items() if pid not in despues],
    }


def escribir_json(ruta: Path, datos) -> int:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    texto = json.dumps(datos, ensure_ascii=False, separators=(",", ":"))
    ruta.write_text(texto, encoding="utf-8")
    return len(texto.encode("utf-8"))


def main() -> None:
    if not ENTRADA_PRODUCTOS.exists():
        raise SystemExit(f"No encuentro {ENTRADA_PRODUCTOS}. Corré primero el scraper del PoC.")

    categorias = cargar_categorias()
    productos: list[dict] = []
    vistos: set[str] = set()

    with ENTRADA_PRODUCTOS.open(encoding="utf-8") as fh:
        for linea in fh:
            linea = linea.strip()
            if not linea:
                continue
            fila = json.loads(linea)
            pid = str(fila.get("id_magento") or "").strip()
            if not pid or pid in vistos:
                continue
            vistos.add(pid)

            nombre = limpiar_texto(fila.get("nombre"))
            final = precio(fila.get("precio_final"))
            anterior = precio(fila.get("precio_anterior"))
            if anterior and final and anterior <= final:
                anterior = None

            cats = [c for c in (fila.get("categorias") or []) if c]
            principal = fila.get("categoria_principal") or ""
            if principal and principal not in cats:
                cats.insert(0, principal)

            productos.append({
                "i": pid,
                "n": nombre,
                "m": marca_de(nombre),
                "c": cats,
                "p": final,
                "o": anterior,
                "e": ESTADO.get(fila.get("estado_tarjeta") or "", 3),
                "img": imagen_normalizada(fila.get("imagen")),
                "s": limpiar_texto(fila.get("sku")) or None,
                "of": bool(final and anterior and final < anterior),
            })

    # Categorías presentes con su conteo
    conteo: dict[str, int] = {}
    for p in productos:
        for c in p["c"]:
            conteo[c] = conteo.get(c, 0) + 1

    arbol = []
    for slug, n in sorted(conteo.items(), key=lambda x: (x[0].count("/"), -x[1])):
        info = categorias.get(slug, {})
        arbol.append({
            "slug": slug,
            "nombre": info.get("nombre") or nombre_categoria(slug.split("/")[-1].replace("-", " ")),
            "pilar": slug.split("/")[0],
            "total": n,
            "hija": "/" in slug,
        })

    meta = {
        "generado": datetime.now().astimezone().isoformat(timespec="seconds"),
        "fuente": "https://www.ciclovia.com.py/",
        "moneda": "PYG",
        "total": len(productos),
        "por_estado": {
            "con_precio": sum(1 for p in productos if p["e"] == 0),
            "agotado": sum(1 for p in productos if p["e"] == 1),
            "solo_catalogo": sum(1 for p in productos if p["e"] == 2),
            "sin_dato": sum(1 for p in productos if p["e"] == 3),
        },
        "con_descuento": sum(1 for p in productos if p["of"]),
        "pilares": PILARES,
    }

    # ------------------- Vistas (archivos separados) -------------------
    tamanos: dict[str, int] = {}
    vistas_salida = []
    for vista in VISTAS:
        subset = [p for p in productos if en_vista(p, vista["slug"])]
        archivo = f"v/{vista['slug']}.json"
        tamanos[vista["slug"]] = escribir_json(SALIDA_VISTAS / f"{vista['slug']}.json", subset)
        vistas_salida.append({
            "slug": vista["slug"],
            "nombre": vista["nombre"],
            "archivo": archivo,
            "total": len(subset),
            "categorias": list(vista["categorias"]),
            "subcategorias": [
                s for s in vista["categorias"] if any(s in p["c"] for p in subset)
            ],
        })

    # ------------------- Índice -------------------
    indice = {
        "meta": meta,
        "predeterminada": "accesorios",
        "vistas": vistas_salida,
        "categorias": arbol,
    }
    escribir_json(SALIDA_INDICE, indice)
    # Copia como script: permite abrir la tienda sin servidor (file://)
    SALIDA_INDICE.with_suffix(".js").write_text(
        "window.INDICE_JSON=" + json.dumps(indice, ensure_ascii=False, separators=(",", ":")) + ";\n",
        encoding="utf-8",
    )

    # ------------------- Catálogo completo (respaldo / compatibilidad) -------------------
    cambios = comparar_con_anterior(productos)
    completo = {"meta": meta, "categorias": arbol, "productos": productos}
    escribir_json(SALIDA_COMPLETO, completo)
    SALIDA_COMPLETO.with_suffix(".js").write_text(
        "window.CATALOGO_JSON=" + json.dumps(completo, ensure_ascii=False, separators=(",", ":")) + ";\n",
        encoding="utf-8",
    )

    # ------------------- Reporte de cambios -------------------
    resumen = {
        "generado": meta["generado"],
        "primera_vez": cambios["primera_vez"],
        "precios_cambiados": len(cambios["precios"]),
        "stock_cambiado": len(cambios["stock"]),
        "altas": len(cambios["altas"]),
        "bajas": len(cambios["bajas"]),
        "detalle_precios": cambios["precios"][:300],
        "detalle_stock": cambios["stock"][:300],
        "detalle_altas": cambios["altas"][:150],
        "detalle_bajas": cambios["bajas"][:150],
    }
    escribir_json(SALIDA_DIR / "ultimos_cambios.json", resumen)

    # ------------------- Salida por consola -------------------
    kb = lambda n: f"{n / 1024:,.0f} KB".replace(",", ".")
    print(f"OK -> {SALIDA_INDICE}")
    print(f"   {len(productos):,} productos · {len(arbol)} categorías · {meta['con_descuento']:,} con descuento")
    print("   Vistas (tamaño sin comprimir; el servidor las sirve en gzip):")
    for v in vistas_salida:
        print(f"     {v['nombre']:<15} {v['total']:>5} productos   {kb(tamanos[v['slug']])}")
    print(f"   Índice: {kb(SALIDA_INDICE.stat().st_size)} · respaldo completo: {kb(SALIDA_COMPLETO.stat().st_size)}")
    if resumen["primera_vez"]:
        print("   Primera corrida: no hay catálogo anterior para comparar.")
    else:
        print(
            f"   Cambios vs. corrida anterior: {resumen['precios_cambiados']} precios · "
            f"{resumen['stock_cambiado']} stock · {resumen['altas']} altas · {resumen['bajas']} bajas"
        )


if __name__ == "__main__":
    main()
