# bot/service/asistente.py
"""El asistente: entiende el mensaje, consulta el catálogo y redacta la respuesta.

La regla que ordena todo el módulo: **el modelo nunca contesta con datos de memoria.**
Se parte en dos llamadas, como pide la especificación de la etapa 2:

  1. CLASIFICAR — el modelo solo decide qué necesita y qué buscar. Devuelve JSON.
  2. CONSULTAR — el servicio va a la API de catálogo y trae precios y stock reales.
  3. REDACTAR — el modelo escribe la respuesta usando ÚNICAMENTE esos datos.

Si la búsqueda no devuelve nada, no se llama al modelo para redactar: se responde con
una plantilla honesta. Es más rápido y hace imposible que invente un precio.

Las respuestas que no necesitan IA (ubicación, envíos, "quiero hablar con alguien") se
arman con plantillas, porque son datos fijos: gastar una llamada ahí suma latencia sin
mejorar nada.
"""
from __future__ import annotations

import json
import logging
import re
import time
import unicodedata

from bot.service import catalogo, config, gemini, negocio

logger = logging.getLogger("jaka.asistente")

INTENCIONES = [
    "buscar_producto",
    "consultar_disponibilidad",
    "servicio_tecnico",
    "envio",
    "ubicacion",
    "pedido",
    "humano",
    "fuera_de_alcance",
]

# Las intenciones que se resuelven buscando en el catálogo.
INTENCIONES_DE_CATALOGO = {"buscar_producto", "consultar_disponibilidad", "pedido"}

ESQUEMA_PLAN = {
    "type": "object",
    "properties": {
        "intencion": {"type": "string", "enum": INTENCIONES},
        "consulta": {
            "type": "string",
            "description": (
                "Texto para buscar en el catálogo: producto, marca o medida. "
                "Sin saludos ni el nombre del negocio. Vacío si no aplica."
            ),
        },
        "tipo": {
            "type": "string",
            "enum": ["todos", "bicicletas", "motos"],
            "description": "Filtrar por rubro solo si el cliente lo dejó claro.",
        },
    },
    "required": ["intencion", "consulta", "tipo"],
}

SISTEMA_CLASIFICADOR = """\
Sos el clasificador de mensajes de WhatsApp de una bicicletería y taller en Capiatá, Paraguay.
Recibís un mensaje de un cliente y devolvés SOLO el JSON del esquema. No contestás al cliente.

Intenciones:
- buscar_producto: pregunta por un producto, si lo tenés o cuánto sale.
- consultar_disponibilidad: pregunta si hay stock, si puede pasar hoy, si lo tenés para ver.
- servicio_tecnico: turnos, service, reparaciones, precio de mantenimiento.
- envio: costos, zonas o formas de entrega.
- ubicacion: dónde están, cómo llegar, horarios de atención.
- pedido: quiere comprar o encargar algo concreto.
- humano: pide hablar con una persona, reclama, o está enojado.
- fuera_de_alcance: no tiene nada que ver con la bicicletería.

Reglas:
- Si menciona un producto concreto (cámara, casco, cubierta, bicicleta, repuesto), es buscar_producto.
- "consulta" lleva SOLO las palabras que identifican al producto: marca, medida o tipo.
  Nada de "para mtb", "de ruta", "buena", "barata" ni el nombre del negocio.
  Ejemplos: "camara 26", "casco scott", "cubierta 29", "service".
- Si pide varias cosas, quedate con la primera.
- Ante la duda entre humano y otra cosa, elegí humano solo si pide explícitamente una persona o reclama.
"""

SISTEMA_REDACTOR = """\
Sos Jaka, el asistente de WhatsApp de Jaka Bicicletería, un taller y tienda de bicicletas
en Capiatá, Paraguay. Le escribís a un cliente.

Cómo escribís:
- Español paraguayo informal y cordial: voseo ("tenés", "querés"), sin exagerar.
- Mensajes cortos de WhatsApp: 1 a 3 oraciones. Sin markdown, sin títulos, sin viñetas.
- Terminá con una pregunta corta cuando tenga sentido.

Lo que NO podés hacer:
- Inventar productos, precios, stock, marcas ni plazos. Solo podés usar lo que venga en DATOS.
- Ofrecer un producto que no aparezca en DATOS.
- Decir que hay stock: el catálogo solo dice que el producto figura, y la disponibilidad se
  confirma en el local. Si DATOS dice "a confirmar" o "sin stock", decilo.
- Prometer envíos gratis ni plazos de entrega.

Cómo usás DATOS:
- DATOS.productos son los productos que encontré. Si hay varios, decí cuántos tenés y nombrá
  hasta 3 con su precio. No te quedes con uno solo cuando hay más.
- DATOS.total es cuántos hay en total y DATOS.mostrados cuántos te pasé. Si total es mayor que
  mostrados, aclaralo: "tengo N, te muestro algunos".
- La foto que acompaña tu mensaje es de "imagen.producto". Nombrá ese producto como uno de los
  que tenés, pero no le atribuyas una medida, color ni marca que no esté en su nombre.
- No digas "te mando una foto" ni "acá va la imagen": la foto ya llega, mencionarla suena raro.

Lo que NO podés hacer:
- Inventar productos, precios, stock, marcas ni plazos. Solo podés usar lo que venga en DATOS.
- Ofrecer un producto que no aparezca en DATOS.
- Decir que hay stock: el catálogo solo dice que el producto figura, y la disponibilidad se
  confirma en el local. Si DATOS dice "a confirmar" o "sin stock", decilo.
- Prometer envíos gratis ni plazos de entrega.

Si DATOS viene vacío o no alcanza, decí que no lo tenés a mano y ofrecé pasarlo al WhatsApp
del taller. No rellenes con suposiciones.
"""

FALLBACK_CORTO = "Disculpá, no te entendí. ¿Me contás un poco más qué necesitás?"
PLANTILLA_HUMANO = (
    "Ya le aviso a alguien del taller para que te responda. "
    "Si es urgente, escribinos al {whatsapp}."
)
PLANTILLA_SIN_RESULTADO = (
    "No lo tengo listado en el catálogo ahora mismo, pero puede ser que lo tengamos en el local. "
    "Escribinos al {whatsapp} y te confirmamos."
)
PLANTILLA_FUERA_DE_ALCANCE = (
    "Ahí no te puedo ayudar, soy el asistente de la bicicletería. "
    "¿Te doy una mano con alguna bici, repuesto o service?"
)


def _whatsapp() -> str:
    datos = negocio.cargar()
    return datos.get("whatsapp") or datos.get("whatsapp_numeros") or "el WhatsApp del taller"


def _transcripcion(historial: list[dict]) -> str:
    """Los últimos turnos como texto plano, para que el clasificador tenga contexto."""
    lineas = []
    for mensaje in (historial or [])[-config.MAX_HISTORIAL:]:
        quien = "Cliente" if mensaje.get("role") == "user" else "Asistente"
        contenido = (mensaje.get("content") or "").strip().replace("\n", " ")
        if contenido:
            lineas.append(f"{quien}: {contenido[:300]}")
    return "\n".join(lineas)


def clasificar(texto: str, historial: list[dict] | None = None, *, cliente=None) -> dict:
    """Decide qué quiere el cliente y qué hay que buscar. Una sola llamada al modelo."""
    cliente = cliente or gemini
    partes = []
    contexto = _transcripcion(historial or [])
    if contexto:
        partes.append("Conversación previa:\n" + contexto)
    partes.append("Mensaje nuevo del cliente: " + texto)

    try:
        plan = cliente.generar_json(
            SISTEMA_CLASIFICADOR,
            [{"role": "user", "content": "\n\n".join(partes)}],
            ESQUEMA_PLAN,
            max_tokens=200,
        )
    except gemini.ErrorGemini:
        raise
    except Exception as e:  # noqa: BLE001
        raise gemini.ErrorGemini(f"No se pudo clasificar el mensaje: {e}") from e

    if plan.get("intencion") not in INTENCIONES:
        plan["intencion"] = "fuera_de_alcance"
    if plan.get("tipo") not in ("bicicletas", "motos"):
        plan["tipo"] = "todos"
    plan["consulta"] = (plan.get("consulta") or "").strip()
    return plan


def _normalizar(texto: str) -> str:
    """Minúsculas, sin acentos y sin puntuación, para comparar nombres con consultas."""
    plano = unicodedata.normalize("NFD", str(texto or "").lower())
    sin_acentos = "".join(c for c in plano if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", sin_acentos).strip()


def _puntaje_coincidencia(nombre: str, consulta: str) -> float:
    """
    Qué tanto se parece el nombre del producto a lo que pidió el cliente.

    Cuenta qué proporción de las palabras de la consulta aparecen en el nombre. Sirve
    para desempatar la elección de la foto: si alguien pide "cubierta 29" y la lista
    trae 27.5 y 29, la foto tiene que ser la 29 aunque la 27.5 aparezca primero.
    """
    buscado = _normalizar(consulta)
    palabras = [p for p in buscado.split() if len(p) > 1]
    if not palabras:
        return 0.0
    nombre_plano = _normalizar(nombre)
    acertadas = sum(1 for p in palabras if p in nombre_plano)
    return acertadas / len(palabras)


def _elegir_foto(productos: list[dict], consulta: str = "") -> dict | None:
    """
    Elige de qué producto se manda la foto.

    Dos criterios, en este orden:

    1. **Que coincida con lo que pidió el cliente.** Si pidió una cubierta 29 y la lista
       trae 27.5 y 29, mandar la 27.5 mientras el mensaje habla de la 29 es un error que
       el cliente nota enseguida.
    2. **Que no esté agotado.** Si el primero figura sin stock, mandar esa foto mientras se
       le ofrece otra cosa confunde. Si todos están agotados igual se manda la mejor
       coincidencia: a veces quiere ver el modelo justamente para encargarlo.
    """
    con_imagen = [p for p in productos if p.get("imagen")]
    if not con_imagen:
        return None

    def clave(producto: dict) -> tuple[float, int]:
        disponible = 0 if "sin stock" in (producto.get("disponibilidad") or "").lower() else 1
        return (_puntaje_coincidencia(producto.get("nombre", ""), consulta), disponible)

    return max(con_imagen, key=clave)


def _buscar_productos(api, consulta: str, tipo: str | None) -> tuple[dict, str]:
    """
    Busca, y si no hay nada va soltando la última palabra.

    La API de catálogo exige que coincidan TODAS las palabras de la consulta, y el
    clasificador a veces agrega modificadores: "camaras 26 para mtb" no encuentra
    nada porque ninguna cámara se llama "mtb". Soltar la última palabra imita lo que
    hace una persona: "camaras 26 para mtb" -> "camaras 26" -> "camaras".

    Son consultas locales a un servidor en loopback: cada intento cuesta milisegundos.
    """
    palabras = consulta.split()
    candidatas = [" ".join(palabras[:i]) for i in range(len(palabras), 0, -1)]

    for intento in candidatas[:3]:
        if len(intento) < 2:
            continue
        respuesta = api.buscar(intento, tipo, config.MAX_PRODUCTOS_CONTEXTO)
        if respuesta.get("items"):
            if intento != consulta:
                logger.info(f"'{consulta}' no dio resultados; se buscó '{intento}'")
            return respuesta, intento

    return {"items": [], "total": 0}, consulta


def ejecutar(plan: dict, *, api=None) -> dict:
    """Consulta la fuente de verdad que corresponda según la intención."""
    api = api or catalogo
    intencion = plan.get("intencion")

    if intencion in INTENCIONES_DE_CATALOGO:
        consulta = plan.get("consulta") or ""
        if len(consulta) < 2:
            return {"tipo": "sin_consulta"}
        tipo = plan.get("tipo") if plan.get("tipo") in ("bicicletas", "motos") else None
        respuesta, usada = _buscar_productos(api, consulta, tipo)
        productos = [api.resumir_producto(i) for i in (respuesta.get("items") or [])]
        datos = {
            "tipo": "productos",
            "consulta": consulta,
            "consulta_usada": usada,
            "total": respuesta.get("total", 0),
            "mostrados": len(productos),
            "productos": productos,
        }
        foto = _elegir_foto(productos, consulta)
        if foto:
            # Va aparte de "productos" para que el modelo sepa cuál es la foto que
            # acompaña al mensaje y hable de ese producto, no de otro de la lista.
            datos["imagen"] = {"producto": foto["nombre"], "url": foto["imagen"]}
        return datos

    if intencion == "servicio_tecnico":
        return {"tipo": "servicios", "servicios": api.resumir_servicios(api.servicios())}

    if intencion == "ubicacion":
        datos = negocio.cargar()
        return {
            "tipo": "ubicacion",
            "direccion": "Capiatá, Departamento Central, Paraguay",
            "mapa": datos.get("ubicacion"),
            "horario": "lunes a sábado de 8:00 a 18:00",
        }

    if intencion == "envio":
        datos = negocio.cargar()
        return {
            "tipo": "envio",
            "envio": datos.get("nota_envio"),
            "retiro": datos.get("nota_retiro"),
            "whatsapp": datos.get("whatsapp"),
        }

    return {"tipo": "ninguno"}


def redactar(texto: str, datos: dict, historial: list[dict] | None = None, *, cliente=None) -> str:
    """El modelo escribe la respuesta usando solo `datos`."""
    cliente = cliente or gemini
    contexto = _transcripcion(historial or [])

    partes = []
    if contexto:
        partes.append("Conversación previa:\n" + contexto)
    partes.append("Mensaje nuevo del cliente: " + texto)
    partes.append("DATOS:\n" + json.dumps(datos, ensure_ascii=False))
    partes.append(negocio.resumen_para_prompt())

    return cliente.generar(
        SISTEMA_REDACTOR,
        [{"role": "user", "content": "\n\n".join(p for p in partes if p)}],
        temperatura=0.4,
        max_tokens=250,
    )


def responder(
    texto: str,
    historial: list[dict] | None = None,
    *,
    api=None,
    cliente=None,
) -> dict:
    """
    Resuelve un mensaje de punta a punta.

    Devuelve {"respuesta", "intencion", "datos", "ms"} y, si algo falló,
    "error": True para que el servidor sepa que es un aviso técnico y no lo guarde
    en el historial como si fuera una respuesta del agente.
    """
    arranque = time.time()
    texto = (texto or "").strip()

    if len(texto) < 2:
        return _resultado(FALLBACK_CORTO, None, None, arranque, error=False)

    try:
        plan = clasificar(texto, historial, cliente=cliente)
        intencion = plan["intencion"]

        if intencion == "humano":
            return _resultado(
                PLANTILLA_HUMANO.format(whatsapp=_whatsapp()), plan, None, arranque
            )

        if intencion == "fuera_de_alcance":
            return _resultado(PLANTILLA_FUERA_DE_ALCANCE, plan, None, arranque)

        datos = ejecutar(plan, api=api)

        if datos["tipo"] == "sin_consulta":
            # Preguntó por un producto sin decir cuál. Se le pide precisión.
            return _resultado(
                "Decime qué producto buscás y te digo si lo tenemos. "
                "¿Es para bici o para moto?",
                plan,
                datos,
                arranque,
            )

        if datos["tipo"] == "productos" and not datos["productos"]:
            # No hay resultados: no se llama al modelo, así no puede inventar.
            return _resultado(
                PLANTILLA_SIN_RESULTADO.format(whatsapp=_whatsapp()), plan, datos, arranque
            )

        if datos["tipo"] in ("ubicacion", "envio"):
            return _resultado(_plantilla_fija(datos), plan, datos, arranque)

        respuesta = redactar(texto, datos, historial, cliente=cliente)
        return _resultado(respuesta, plan, datos, arranque)

    except gemini.ErrorGemini as e:
        logger.error(f"Falla del modelo: {e}")
        return _resultado(
            "Perdoná, estoy con un problema técnico. "
            f"Escribinos al {_whatsapp()} y te atendemos al toque.",
            None,
            None,
            arranque,
            error=True,
        )
    except catalogo.ErrorCatalogo as e:
        logger.error(f"Falla del catálogo: {e}")
        return _resultado(
            "No puedo consultar el catálogo en este momento. "
            f"Escribinos al {_whatsapp()} y te respondemos.",
            None,
            None,
            arranque,
            error=True,
        )


def _plantilla_fija(datos: dict) -> str:
    """Respuestas que son puro dato: no hace falta redactarlas con el modelo."""
    if datos["tipo"] == "ubicacion":
        partes = [f"Estamos en {datos['direccion']}."]
        if datos.get("horario"):
            partes.append(f"Atendemos {datos['horario']}.")
        if datos.get("mapa"):
            partes.append(f"Te dejo el mapa: {datos['mapa']}")
        partes.append("¿Querés que te ayude con algo más?")
        return " ".join(partes)

    nota_envio = (datos.get("envio") or "").strip()
    nota_retiro = (datos.get("retiro") or "").strip()

    partes = ["Sí, hacemos envíos." if nota_envio else "Hacemos envíos."]
    if nota_envio:
        partes.append(nota_envio)
    else:
        partes.append("El costo se coordina por WhatsApp según la zona.")
    if nota_retiro:
        partes.append(f"También podés retirar en el local. {nota_retiro}")
    partes.append("¿Te paso el total?")
    return " ".join(partes)


def _resultado(
    respuesta: str,
    plan: dict | None,
    datos: dict | None,
    arranque: float,
    *,
    error: bool = False,
) -> dict:
    return {
        "respuesta": respuesta,
        "intencion": (plan or {}).get("intencion"),
        "plan": plan,
        "datos": datos,
        "imagen": (datos or {}).get("imagen"),
        "ms": int((time.time() - arranque) * 1000),
        "error": error,
    }
