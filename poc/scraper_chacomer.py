#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Scraper del catálogo de MOTOS de Chacomer (chacomer.com.py).

Recorre las categorías de /moto/ (repuestos, accesorios, cubiertas, baterías,
herramientas, eléctricas, Kenton, Yamaha, HD) incluyendo TODAS las páginas de
cada una, y guarda:

    poc/data/motos.jsonl           -> un producto por línea (deduplicado)
    poc/data/motos_categorias.json -> categorías con su cantidad y páginas

Uso:
    python poc/scraper_chacomer.py                 # usa caché si existe
    python poc/scraper_chacomer.py --force         # vuelve a descargar todo
    python poc/scraper_chacomer.py --categoria baterias   # solo una (prueba)
    python poc/scraper_chacomer.py --sin-red       # reprocesa la caché

El HTML crudo queda en poc/cache/chacomer/ para poder reprocesar sin red.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import http.client
import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

import lxml.html as LH

RAIZ = Path(__file__).resolve().parent.parent
CACHE = RAIZ / "poc" / "cache" / "chacomer"
SALIDA = RAIZ / "poc" / "data" / "motos.jsonl"
SALIDA_CATS = RAIZ / "poc" / "data" / "motos_categorias.json"

BASE = "https://www.chacomer.com.py"
HOST = "www.chacomer.com.py"
RAIZ_MOTO = BASE + "/moto.html"
IMG_BASE = "https://www.chacomer.com.py/media/catalog/product/"

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0 Safari/537.36"
)
PAUSA = 0.2
REINTENTOS = 3


class PresupuestoAgotado(Exception):
    pass


class Descargador:
    def __init__(self, force: bool = False, sin_red: bool = False, maximo: int = 1200):
        self.force = force
        self.sin_red = sin_red
        self.maximo = maximo
        self.peticiones = 0
        self.memoria: dict[str, str] = {}
        self._conn: http.client.HTTPSConnection | None = None

    def archivo(self, url: str) -> Path:
        return CACHE / (hashlib.sha1(url.encode("utf-8")).hexdigest()[:16] + ".html")

    def _conexion(self) -> http.client.HTTPSConnection:
        if self._conn is None:
            self._conn = http.client.HTTPSConnection(HOST, timeout=90)
        return self._conn

    def _pedir(self, url: str) -> str:
        partes = urllib.parse.urlsplit(url)
        ruta = partes.path + (("?" + partes.query) if partes.query else "")
        conn = self._conexion()
        conn.request("GET", ruta, headers={
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Encoding": "gzip",
            "Accept-Language": "es-PY,es",
            "Connection": "keep-alive",
        })
        resp = conn.getresponse()
        datos = resp.read()
        if resp.status in (301, 302, 303, 307, 308):
            destino = resp.getheader("Location")
            return self._pedir(urllib.parse.urljoin(url, destino))
        if resp.status != 200:
            raise RuntimeError(f"HTTP {resp.status} en {url}")
        if (resp.getheader("Content-Encoding") or "").lower() == "gzip":
            datos = gzip.decompress(datos)
        return datos.decode("utf-8", "ignore")

    def obtener(self, url: str) -> str:
        if url in self.memoria:
            return self.memoria[url]
        ruta = self.archivo(url)
        if ruta.exists() and not self.force:
            texto = ruta.read_text(encoding="utf-8", errors="ignore")
            self.memoria[url] = texto
            return texto
        if self.sin_red:
            raise FileNotFoundError(f"Sin caché para {url}")
        if self.peticiones >= self.maximo:
            raise PresupuestoAgotado(f"Límite de {self.maximo} peticiones alcanzado")
        self.peticiones += 1
        ultimo = None
        for intento in range(REINTENTOS):
            try:
                texto = self._pedir(url)
                CACHE.mkdir(parents=True, exist_ok=True)
                ruta.write_text(texto, encoding="utf-8")
                self.memoria[url] = texto
                time.sleep(PAUSA)
                return texto
            except Exception as exc:  # noqa: BLE001
                ultimo = exc
                self._conn = None
                time.sleep(1.2 * (intento + 1))
        raise RuntimeError(f"No se pudo descargar {url}: {ultimo}")


def limpio(texto: str) -> str:
    return re.sub(r"\s+", " ", texto or "").strip()


def slug_de(url: str) -> str:
    """Identificador estable: el slug del producto."""
    m = re.search(r"/id/(\d+)/", url)
    if m:
        return "ch" + m.group(1)
    m = re.search(r"/([^/]+)\.html", url)
    return m.group(1) if m else url


def normalizar_url(url: str) -> str:
    url = url.split("#")[0]
    return url


def parsear(html: str, categoria: str) -> list[dict]:
    """Extrae los productos de una página de listado."""
    doc = LH.fromstring(html)
    salida = []
    for li in doc.xpath('//li[contains(@class,"product-item")]'):
        enlaces = li.xpath('.//a[contains(@class,"product-item-link")]')
        if not enlaces:
            continue
        url = normalizar_url(enlaces[0].get("href") or "")
        if not url.startswith("http"):
            continue
        nombre = limpio(enlaces[0].text_content())
        if not nombre:
            continue

        marca = limpio(" ".join(li.xpath('.//*[contains(@class,"product-item-brand")]//text()')))

        def precio(tipo: str):
            for el in li.xpath(f'.//*[@data-price-type="{tipo}"]'):
                valor = el.get("data-price-amount")
                if valor:
                    return int(float(valor))
            return None

        final = precio("finalPrice")
        anterior = precio("oldPrice")
        if final is None:
            for el in li.xpath('.//*[@data-price-amount]'):
                valor = el.get("data-price-amount")
                if valor:
                    final = int(float(valor))
        if not final:
            continue

        imagen = ""
        for el in li.xpath('.//*[contains(@class,"product-image-photo")]'):
            estilo = el.get("style") or ""
            m = re.search(r"url\('([^']+)'\)", estilo)
            if m:
                imagen = m.group(1).split("?")[0]
                if imagen.startswith(IMG_BASE):
                    imagen = imagen[len(IMG_BASE):]
                break
        if not imagen:
            img = li.xpath('.//img[@src]')
            if img:
                imagen = (img[0].get("src") or "").split("?")[0]
                if imagen.startswith(IMG_BASE):
                    imagen = imagen[len(IMG_BASE):]

        salida.append({
            "i": slug_de(url),
            "n": nombre,
            "m": marca,
            "p": final,
            "o": anterior if anterior and anterior > final else None,
            "img": imagen,
            "u": url,
            "c": [categoria],
        })
    return salida


def descubrir_categorias(desc: Descargador) -> list[dict]:
    html = desc.obtener(RAIZ_MOTO)
    doc = LH.fromstring(html)
    vistas: dict[str, str] = {}
    for a in doc.xpath('//a[@href]'):
        href = normalizar_url(a.get("href") or "")
        m = re.match(rf"^{re.escape(BASE)}/moto/([a-z0-9\-]+)\.html$", href)
        if m and m.group(1) not in vistas:
            vistas[m.group(1)] = limpio(a.text_content()) or m.group(1).title()
    # Asegurar las conocidas aunque no estén en el menú
    for slug, nombre in {
        "repuestos": "Repuestos y aceites",
        "accesorios": "Accesorios",
        "cubiertas": "Cubiertas",
        "baterias": "Baterías",
        "herramientas": "Herramientas",
        "electricas": "Eléctricas",
        "kenton": "Kenton",
        "yamaha": "Yamaha",
        "hd": "Harley Davidson",
    }.items():
        vistas.setdefault(slug, nombre)
    return [{"slug": s, "nombre": n, "url": f"{BASE}/moto/{s}.html"} for s, n in vistas.items()]


def raspar_categoria(desc: Descargador, cat: dict, verbose: bool = True, max_paginas: int = 700) -> tuple[list[dict], int]:
    productos: dict[str, dict] = {}
    primera = None
    paginas = 0
    p = 1
    while True:
        url = cat["url"] if p == 1 else f'{cat["url"]}?p={p}'
        html = desc.obtener(url)
        items = parsear(html, cat["slug"])
        if not items:
            break
        paginas = p
        if p > 1 and primera and items[0]["i"] == primera:
            break  # el sitio repite la página 1 al pasarse del máximo
        primera = primera or items[0]["i"]
        nuevos = 0
        for it in items:
            actual = productos.get(it["i"])
            if actual:
                if cat["slug"] not in actual["c"]:
                    actual["c"].append(cat["slug"])
            else:
                productos[it["i"]] = it
                nuevos += 1
        if p > 1 and nuevos == 0:
            break  # página repetida / sin productos nuevos: fin de la categoría
        if verbose and p % 25 == 0:
            print(f"    {cat['slug']}: página {p} · {len(productos)} productos", flush=True)
        p += 1
        if p > max_paginas:
            print(f"    {cat['slug']}: tope de {max_paginas} páginas (¿cambió el listado?)", flush=True)
            break
    return list(productos.values()), paginas


def main() -> None:
    ap = argparse.ArgumentParser(description="Scraper de motos de Chacomer")
    ap.add_argument("--force", action="store_true", help="ignorar la caché y descargar de nuevo")
    ap.add_argument("--sin-red", action="store_true", help="solo reprocesar la caché")
    ap.add_argument("--max-peticiones", type=int, default=1200)
    ap.add_argument("--max-paginas", type=int, default=700, help="tope de páginas por categoría")
    ap.add_argument("--categoria", default="", help="solo una categoría (para pruebas)")
    args = ap.parse_args()

    CACHE.mkdir(parents=True, exist_ok=True)
    desc = Descargador(force=args.force, sin_red=args.sin_red, maximo=args.max_peticiones)

    print("Descubriendo categorías de /moto/…", flush=True)
    categorias = descubrir_categorias(desc)
    if args.categoria:
        categorias = [c for c in categorias if c["slug"] == args.categoria]
        if not categorias:
            raise SystemExit(f"No existe la categoría {args.categoria}")

    todos: dict[str, dict] = {}
    resumen = []
    inicio = time.time()
    for i, cat in enumerate(categorias, 1):
        print(f"[{i}/{len(categorias)}] {cat['nombre']} ({cat['slug']})", flush=True)
        items, paginas = raspar_categoria(desc, cat, max_paginas=args.max_paginas)
        for it in items:
            actual = todos.get(it["i"])
            if actual:
                for c in it["c"]:
                    if c not in actual["c"]:
                        actual["c"].append(c)
            else:
                todos[it["i"]] = it
        resumen.append({**cat, "total": len(items), "paginas": paginas})
        print(f"    -> {len(items)} productos · {paginas} páginas", flush=True)

    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    with SALIDA.open("w", encoding="utf-8") as fh:
        for it in todos.values():
            fh.write(json.dumps(it, ensure_ascii=False, separators=(",", ":")) + "\n")
    SALIDA_CATS.write_text(json.dumps({
        "generado": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "fuente": RAIZ_MOTO,
        "categorias": resumen,
        "total": len(todos),
        "peticiones": desc.peticiones,
        "segundos": round(time.time() - inicio, 1),
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\nOK -> {SALIDA}")
    print(f"   {len(todos):,} productos únicos · {len(categorias)} categorías · {desc.peticiones} peticiones "
          f"· {round(time.time()-inicio)} s")


if __name__ == "__main__":
    main()
