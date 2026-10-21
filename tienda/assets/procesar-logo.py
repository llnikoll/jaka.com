#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Genera los archivos de marca (logo, favicon, iconos) a partir de jaka-logo.webp.

Uso:
    python tienda/assets/procesar-logo.py

Salidas en tienda/assets/:
    jaka-icono.png          cabeza del mapache (encabezado)
    favicon-32.png          32 px
    favicon-192.png         android
    apple-touch-icon.png    180 px
    favicon.ico             multi-tamaño
    jaka-logo-completo.png  logo completo (emblema + JAKA)
    jaka-og.png             imagen para compartir (1200x630)
"""

from __future__ import annotations

import os
from collections import Counter

from PIL import Image

RAIZ = os.path.dirname(os.path.abspath(__file__))
ORIGEN = os.path.join(RAIZ, "jaka-logo.webp")


def recortar(im: Image.Image) -> Image.Image:
    alfa = im.getchannel("A").point(lambda a: 255 if a > 20 else 0)
    caja = alfa.getbbox()
    return im.crop(caja) if caja else im


def cabeza_sin_palabra(logo: Image.Image) -> Image.Image:
    """Recorta el mapache (sin la palabra JAKA, que arranca en el centro abajo)."""
    ancho, alto = logo.size
    alfa = logo.getchannel("A")
    inicio_centro = int(ancho * 0.34)
    fin_centro = int(ancho * 0.66)

    # perfil de la zona central: la palabra JAKA aparece después de un hueco
    centro = []
    for y in range(alto):
        centro.append(any(alfa.getpixel((x, y)) > 20 for x in range(inicio_centro, fin_centro, 3)))

    minimo = max(8, int(alto * 0.02))
    corte = alto
    y = int(alto * 0.25)
    while y < alto:
        if not centro[y]:
            inicio = y
            while y < alto and not centro[y]:
                y += 1
            if y - inicio >= minimo:
                corte = inicio
                break
        else:
            y += 1

    return recortar(logo.crop((0, 0, ancho, max(10, corte - 2))))


def color_marca(im: Image.Image) -> tuple[int, int, int]:
    colores = Counter()
    for x in range(0, im.width, 7):
        for y in range(0, im.height, 7):
            r, g, b, a = im.getpixel((x, y))
            if a > 200:
                colores[(r, g, b)] += 1
    return colores.most_common(1)[0][0] if colores else (0, 168, 79)


def encajar(im: Image.Image, caja: int, margen: float = 0.10) -> Image.Image:
    copia = im.copy()
    util = int(caja * (1 - 2 * margen))
    copia.thumbnail((util, util), Image.LANCZOS)
    return copia


def icono_verde(cabeza: Image.Image, color: tuple[int, int, int], lado: int) -> Image.Image:
    """Cuadrado del color de marca con la silueta blanca del mapache."""
    silueta = encajar(cabeza, lado, margen=0.14)
    mascara = silueta.getchannel("A")
    blanco = Image.new("RGBA", silueta.size, (255, 255, 255, 255))
    lienzo = Image.new("RGBA", (lado, lado), color + (255,))
    pos = ((lado - silueta.width) // 2, (lado - silueta.height) // 2)
    capa = Image.new("RGBA", (lado, lado), (0, 0, 0, 0))
    capa.paste(blanco, pos, mascara)
    return Image.alpha_composite(lienzo, capa)


def main() -> None:
    original = Image.open(ORIGEN).convert("RGBA")
    logo = recortar(original)
    cabeza = cabeza_sin_palabra(logo)
    color = color_marca(logo)

    # Encabezado: cuadrado verde con la silueta (mismo lenguaje que el favicon)
    icono = icono_verde(cabeza, color, 512)
    icono.save(os.path.join(RAIZ, "jaka-icono.png"), "PNG", optimize=True)
    encajar(cabeza, 512, margen=0.02).save(os.path.join(RAIZ, "jaka-cabeza.png"), "PNG", optimize=True)

    # Favicons con silueta blanca sobre verde
    icono_verde(cabeza, color, 192).save(os.path.join(RAIZ, "favicon-192.png"), "PNG", optimize=True)
    icono_verde(cabeza, color, 32).save(os.path.join(RAIZ, "favicon-32.png"), "PNG", optimize=True)
    icono_verde(cabeza, color, 180).save(os.path.join(RAIZ, "apple-touch-icon.png"), "PNG", optimize=True)
    icono_verde(cabeza, color, 64).save(
        os.path.join(RAIZ, "favicon.ico"),
        format="ICO",
        sizes=[(16, 16), (32, 32), (48, 48), (64, 64)],
    )

    # Logo completo (para compartir / usos grandes)
    completo = logo.copy()
    completo.thumbnail((1200, 1200), Image.LANCZOS)
    completo.save(os.path.join(RAIZ, "jaka-logo-completo.png"), "PNG", optimize=True)

    # Imagen para compartir (fondo blanco)
    og = Image.new("RGBA", (1200, 630), (255, 255, 255, 255))
    copia = completo.copy()
    copia.thumbnail((880, 460), Image.LANCZOS)
    og.paste(copia, ((1200 - copia.width) // 2, (630 - copia.height) // 2), copia)
    og.convert("RGB").save(os.path.join(RAIZ, "jaka-og.png"), "PNG", optimize=True)

    print(f"OK · color de marca #{color[0]:02X}{color[1]:02X}{color[2]:02X} · cabeza {cabeza.size} · logo {logo.size}")
    for nombre in ("jaka-icono.png", "jaka-cabeza.png", "favicon-32.png", "favicon-192.png",
                   "apple-touch-icon.png", "favicon.ico", "jaka-logo-completo.png", "jaka-og.png"):
        ruta = os.path.join(RAIZ, nombre)
        print(f"   {nombre:<24} {os.path.getsize(ruta) / 1024:6.1f} KB")


if __name__ == "__main__":
    main()
