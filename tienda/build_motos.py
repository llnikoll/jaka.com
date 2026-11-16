#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Convierte el scraping de motos de Chacomer (poc/data/motos.jsonl) en datos para
la tienda y lo integra al índice principal.

Salida:
    tienda/data/motos/v/todos.json   -> catálogo completo de motos
    tienda/data/motos/indice.json    -> categorías, totales y fecha
    tienda/data/indice.json          -> se le agrega la vista "Motos" y sus categorías

Uso:
    python tienda/build_motos.py
    (también lo llama solo build_catalogo.py al final)
"""

from __future__ import annotations

import json
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ENTRADA = RAIZ / "poc" / "data" / "motos.jsonl"
ENTRADA_CATS = RAIZ / "poc" / "data" / "motos_categorias.json"
DESTINO = RAIZ / "tienda" / "data" / "motos"
SALIDA_TODOS = DESTINO / "v" / "todos.json"
SALIDA_INDICE = DESTINO / "indice.json"
INDICE_TIENDA = RAIZ / "tienda" / "data" / "indice.json"

ORDEN = [
    "repuestos", "accesorios", "cubiertas", "baterias", "herramientas",
    "electricas", "kenton", "yamaha", "hd",
]
MINUSCULAS = {"y", "de", "del", "la", "las", "los", "el", "en", "para", "con", "por"}


def titulo(texto: str) -> str:
    """Pasa 'REPUESTOS Y ACEITES' a 'Repuestos y aceites'."""
    limpio = (texto or "").strip().lower()
    return limpio[:1].upper() + limpio[1:] if limpio else ""


def cargar_productos() -> list[dict]:
    if not ENTRADA.exists():
        return []
    productos = []
    with ENTRADA.open(encoding="utf-8") as fh:
        for linea in fh:
            linea = linea.strip()
            if not linea:
                continue
            try:
                p = json.loads(linea)
            except json.JSONDecodeError:
                continue
            if not p.get("p") or not p.get("n"):
                continue
            cats = p.get("c") or []
            categorias = ["motos"] + [f"motos/{c}" for c in cats if c]
            productos.append({
                "i": p["i"],
                "n": p["n"],
                "m": p.get("m") or "",
                "c": categorias,
                "p": int(p["p"]),
                "o": int(p["o"]) if p.get("o") else None,
                "e": 0,
                "img": p.get("img") or "",
                "ch": 1,
                "sc": 1,  # stock a confirmar (el listado de Chacomer no lo informa)
            })
    return productos


def construir() -> dict:
    """Genera los archivos de motos. Devuelve el resumen."""
    productos = cargar_productos()
    if not productos:
        return {"total": 0, "categorias": []}

    DESTINO.mkdir(parents=True, exist_ok=True)
    (DESTINO / "v").mkdir(parents=True, exist_ok=True)

    salida = {
        "generado": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "fuente": "https://www.chacomer.com.py/moto.html",
        "total": len(productos),
        "productos": productos,
    }
    SALIDA_TODOS.write_text(json.dumps(productos, ensure_ascii=False, separators=(",", ":")),
                            encoding="utf-8")

    resumen = json.loads(ENTRADA_CATS.read_text(encoding="utf-8")) if ENTRADA_CATS.exists() else {}
    totales = {c["slug"]: c for c in resumen.get("categorias", [])}
    categorias = []
    for slug in ORDEN:
        info = totales.get(slug)
        if not info:
            continue
        categorias.append({
            "slug": slug,
            "nombre": titulo(info.get("nombre") or slug),
            "total": info.get("total", 0),
        })
    for c in resumen.get("categorias", []):
        if c["slug"] not in ORDEN:
            categorias.append({"slug": c["slug"], "nombre": titulo(c.get("nombre") or c["slug"]), "total": c.get("total", 0)})

    SALIDA_INDICE.write_text(json.dumps({
        "generado": salida["generado"],
        "total": len(productos),
        "categorias": categorias,
        "archivo": "motos/v/todos.json",
    }, ensure_ascii=False, indent=1), encoding="utf-8")

    return {"total": len(productos), "categorias": categorias, "generado": salida["generado"]}


def resumen_actual() -> dict:
    """Si hay scraping nuevo lo procesa; si no, reutiliza lo ya generado (p. ej. en CI)."""
    if ENTRADA.exists():
        resumen = construir()
        if resumen.get("total"):
            return resumen
    if SALIDA_TODOS.exists():
        productos = json.loads(SALIDA_TODOS.read_text(encoding="utf-8"))
        datos = json.loads(SALIDA_INDICE.read_text(encoding="utf-8")) if SALIDA_INDICE.exists() else {}
        return {
            "total": len(productos),
            "categorias": datos.get("categorias") or [],
            "generado": datos.get("generado") or "",
        }
    return {"total": 0, "categorias": []}


def parchear_indice(resumen: dict | None = None) -> None:
    """Agrega la vista y las categorías de motos al índice principal de la tienda."""
    resumen = resumen or resumen_actual()
    if not resumen.get("total") or not INDICE_TIENDA.exists():
        return

    indice = json.loads(INDICE_TIENDA.read_text(encoding="utf-8"))
    vistas = indice.get("vistas") or []
    vistas = [v for v in vistas if v.get("slug") != "motos"]
    vista = {
        "slug": "motos",
        "nombre": "Motos",
        "archivo": "motos/v/todos.json",
        "total": resumen["total"],
        "categorias": [],
        "motos": True,
        "subcategorias": [f"motos/{c['slug']}" for c in resumen["categorias"]],
    }
    orden = [v["slug"] for v in vistas]
    pos = orden.index("ofertas") if "ofertas" in orden else len(vistas)
    vistas.insert(pos, vista)
    indice["vistas"] = vistas

    categorias = [c for c in (indice.get("categorias") or []) if not (c.get("pilar") == "motos")]
    categorias.append({"slug": "motos", "nombre": "Motos", "pilar": "motos", "total": resumen["total"], "hija": False})
    for c in resumen["categorias"]:
        categorias.append({
            "slug": f"motos/{c['slug']}",
            "nombre": c["nombre"],
            "pilar": "motos",
            "total": c["total"],
            "hija": True,
        })
    indice["categorias"] = categorias

    meta = indice.setdefault("meta", {})
    bikes = int(meta.get("total") or 0)
    if meta.get("motos_sumadas") != resumen["total"] and bikes:
        # se recalcula solo si cambió la cantidad (evita sumar dos veces)
        meta["total"] = bikes - int(meta.get("motos_sumadas") or 0) + resumen["total"]
        meta["motos_sumadas"] = resumen["total"]
    else:
        meta["total"] = bikes
    pilares = meta.get("pilares") or []
    if "motos" not in pilares:
        pilares.append("motos")
    meta["pilares"] = pilares
    meta["motos"] = {"total": resumen["total"], "generado": resumen["generado"]}

    INDICE_TIENDA.write_text(json.dumps(indice, ensure_ascii=False, separators=(",", ":")),
                             encoding="utf-8")
    # Copia como script para abrir la tienda sin servidor
    INDICE_TIENDA.with_suffix(".js").write_text(
        "window.INDICE_JSON=" + json.dumps(indice, ensure_ascii=False, separators=(",", ":")) + ";\n",
        encoding="utf-8",
    )


def main() -> None:
    resumen = resumen_actual()
    parchear_indice(resumen)
    print(f"OK -> {SALIDA_TODOS} · {resumen['total']:,} productos de motos")
    print(f"   categorías: {len(resumen['categorias'])} · índice parcheado: {INDICE_TIENDA}")
    for c in resumen["categorias"]:
        print(f"     {c['slug']:<12} {c['nombre']:<22} {c['total']:>5}")


if __name__ == "__main__":
    main()
