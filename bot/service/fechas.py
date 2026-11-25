# bot/service/fechas.py
"""Interpretación de fechas escritas como las escribe un cliente.

Para los turnos de taller no hace falta horario ni franjas: el cliente sólo dice qué
día puede traer la bici. Así que esto entiende "hoy", "mañana", "el sábado", "29/11" y
"2026-11-29", y nada más.

Paraguay quedó en UTC-3 todo el año desde que eliminó el horario de verano en 2024, por
eso se usa un desfase fijo y no ZoneInfo: en Windows la base de zonas horarias no viene
instalada y el servicio tiene que arrancar siempre.
"""
from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime, timedelta, timezone

ZONA = timezone(timedelta(hours=-3))

DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]

# Hasta cuántos días adelante tiene sentido que alguien avise. Más lejos es más
# probable que sea un error de interpretación que una intención real.
DIAS_MAXIMOS = 60

PREFIJOS = ("el ", "este ", "esta semana ", "para el ", "para ", "el dia ", "dia ")


def hoy() -> date:
    """La fecha del taller, no la del servidor (que en producción corre en UTC)."""
    return datetime.now(timezone.utc).astimezone(ZONA).date()


def _plano(texto: str) -> str:
    """Minúsculas, sin acentos y con espacios simples."""
    sin_acentos = unicodedata.normalize("NFD", str(texto or "").lower())
    sin_acentos = "".join(c for c in sin_acentos if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", sin_acentos).strip()


def _limpiar(texto: str) -> str:
    limpio = _plano(texto)
    for prefijo in PREFIJOS:
        if limpio.startswith(prefijo):
            limpio = limpio[len(prefijo):]
    return limpio.strip().rstrip(".!")


def describir(fecha: date) -> str:
    """'sábado 29/11'."""
    return f"{DIAS[fecha.weekday()]} {fecha:%d/%m}"


def _es_ese_dia(texto: str, nombre: str) -> bool:
    """Coincide el nombre del día, o sus primeras cuatro letras ('mierc', 'saba')."""
    return texto == nombre or (len(texto) >= 4 and nombre.startswith(texto[:4]))


def parsear(texto: str, *, referencia: date | None = None) -> date:
    """
    Convierte lo que escribió el cliente en una fecha.

    Lanza ValueError con un mensaje pensado para repetirle al cliente, no para un log.
    """
    base = referencia or hoy()
    crudo = str(texto or "").strip()
    limpio = _limpiar(crudo)

    if not limpio:
        raise ValueError("No me dijiste qué día podés traerla.")

    if limpio in ("hoy", "ahora", "hoy mismo"):
        fecha = base
    elif limpio in ("manana", "maniana"):
        fecha = base + timedelta(days=1)
    else:
        fecha = None
        for indice, nombre in enumerate(DIAS):
            if _es_ese_dia(limpio, _plano(nombre)):
                # Próxima aparición de ese día, contando hoy si coincide.
                fecha = base + timedelta(days=(indice - base.weekday()) % 7)
                break
        if fecha is None:
            fecha = _por_formato(limpio, base)
        if fecha is None:
            raise ValueError(
                f"No entendí '{crudo}' como fecha. Decime el día de la semana "
                "o la fecha como DD/MM."
            )

    fecha = _validar(fecha, base)
    return fecha


def _por_formato(texto: str, base: date) -> date | None:
    for formato in ("%Y-%m-%d", "%d/%m/%Y", "%d/%m", "%d-%m-%Y", "%d-%m", "%Y/%m/%d"):
        try:
            fecha = datetime.strptime(texto, formato).date()
        except ValueError:
            continue
        if fecha.year == 1900:
            # Vino de un formato sin año (29/11): se asume el año en curso. Si ya pasó,
            # _validar decide si tiene sentido el año que viene.
            fecha = fecha.replace(year=base.year)
        return fecha
    return None


def _validar(fecha: date, base: date) -> date:
    """
    Ajusta una fecha sin año que ya pasó y valida que esté en la ventana razonable.

    Si alguien escribe "03/01" en diciembre, quiere decir enero del año que viene: se
    corre un año. Pero si escribe "03/11" a fines de noviembre está confundido, y
    decirle "esa fecha es muy lejana" confunde más que decirle que esa fecha ya pasó.
    """
    if fecha >= base:
        if fecha > base + timedelta(days=DIAS_MAXIMOS):
            raise ValueError("Esa fecha es muy lejana. ¿Cuál es el próximo día que podés traerla?")
        return fecha

    siguiente = fecha.replace(year=fecha.year + 1)
    if siguiente <= base + timedelta(days=DIAS_MAXIMOS):
        return siguiente

    raise ValueError(f"El {describir(fecha)} ya pasó. ¿Qué otro día te viene bien?")
