# bot/service/tests/test_asistente.py
"""Pruebas del asistente sin red: dobles del modelo y de la API de catálogo.

Lo que se verifica acá es el contrato que evita que el bot invente datos:

- Cuando no hay resultados, NO se llama al modelo para redactar: se responde con la
  plantilla honesta. Es la garantía más importante del módulo.
- El teléfono y el historial viajan por el servicio, no por lo que diga el modelo.
- Las intenciones de datos fijos no gastan una llamada de redacción.
- Un fallo del modelo o del catálogo se convierte en un aviso técnico marcado como
  `error`, para que el servidor no lo guarde en el historial.

Corre sin API key y sin PostgreSQL:

    python -m unittest discover -s bot/service/tests -t . -v
"""
from __future__ import annotations

import unittest

from bot.service import asistente, catalogo, gemini


class ClienteFalso:
    """Doble de gemini: devuelve lo que se le configure y anota las llamadas."""

    def __init__(self, plan=None, texto="Respuesta redactada.", error=None):
        self.plan = plan or {
            "intencion": "buscar_producto",
            "consulta": "camara 26",
            "tipo": "todos",
        }
        self.texto = texto
        self.error = error
        self.clasificaciones = 0
        self.redacciones = 0
        self.ultimo_contexto = None

    def generar_json(self, sistema, mensajes, esquema, **kwargs):
        if self.error:
            raise self.error
        self.clasificaciones += 1
        self.ultimo_contexto = mensajes
        return dict(self.plan)

    def generar(self, sistema, mensajes, **kwargs):
        if self.error:
            raise self.error
        self.redacciones += 1
        self.ultimo_contexto = mensajes
        return self.texto


class ApiFalsa:
    """Doble de catalogo."""

    def __init__(self, productos=None, total=None, error=None):
        self.productos = productos if productos is not None else []
        self.total = total if total is not None else len(self.productos)
        self.error = error
        self.busquedas = []
        self.pedidos_de_servicios = 0

    def buscar(self, consulta, tipo=None, limite=5):
        if self.error:
            raise self.error
        self.busquedas.append({"consulta": consulta, "tipo": tipo, "limite": limite})
        return {"items": self.productos, "total": self.total}

    def resumir_producto(self, item):
        return item

    def servicios(self):
        self.pedidos_de_servicios += 1
        return {"items": [{"nombre": "Completo", "precio": 120000, "items": ["caja", "ruedas"]}]}

    def resumir_servicios(self, datos):
        return catalogo.resumir_servicios(datos)


PRODUCTO = {
    "id": "442954",
    "nombre": "CÁMARA 26 X 1.50 CALOI",
    "marca": "CALOI",
    "precio": "Gs. 310.000",
    "precio_valor": 310000,
    "precio_origen": 269565,
    "disponibilidad": "Figura en catálogo; confirmar disponibilidad",
    "disponibilidad_codigo": "available_in_catalog",
    "categoria": "bicicletas",
    "link": "https://example.test/p/442954",
    "imagen": "https://cdn.test/camara.jpg?quality=85&fit=bounds",
}

AGOTADO = {
    "id": "442227",
    "nombre": "CASCO SCOTT SUPRA",
    "marca": "SCOTT",
    "precio": "a consultar",
    "precio_origen": None,
    "disponibilidad": "Sin stock según catálogo",
    "categoria": "bicicletas",
    "link": "https://example.test/p/442227",
    "imagen": "https://cdn.test/casco-supra.jpg?quality=85",
}


class ClasificarTest(unittest.TestCase):
    def test_plan_normaliza_tipo_desconocido(self):
        cliente = ClienteFalso(plan={"intencion": "buscar_producto", "consulta": "casco", "tipo": "aviones"})
        plan = asistente.clasificar("tenes cascos?", [], cliente=cliente)
        self.assertEqual(plan["tipo"], "todos")

    def test_plan_normaliza_intencion_desconocida(self):
        cliente = ClienteFalso(plan={"intencion": "comprar_bicicleta", "consulta": "x", "tipo": "todos"})
        plan = asistente.clasificar("hola", [], cliente=cliente)
        self.assertEqual(plan["intencion"], "fuera_de_alcance")

    def test_historial_viaja_en_el_prompt(self):
        cliente = ClienteFalso()
        historial = [
            {"role": "user", "content": "tenes cascos scott?"},
            {"role": "assistant", "content": "Tenemos varios modelos."},
        ]
        asistente.clasificar("y cuanto sale el mas barato?", historial, cliente=cliente)
        texto = cliente.ultimo_contexto[0]["content"]
        self.assertIn("tenes cascos scott?", texto)
        self.assertIn("y cuanto sale el mas barato?", texto)


class EjecutarTest(unittest.TestCase):
    def test_busqueda_pasa_consulta_y_limite(self):
        api = ApiFalsa(productos=[PRODUCTO])
        datos = asistente.ejecutar(
            {"intencion": "buscar_producto", "consulta": "camara 26", "tipo": "bicicletas"},
            api=api,
        )
        self.assertEqual(datos["tipo"], "productos")
        self.assertEqual(len(datos["productos"]), 1)
        self.assertEqual(api.busquedas[0]["consulta"], "camara 26")
        self.assertEqual(api.busquedas[0]["tipo"], "bicicletas")

    def test_tipo_todos_no_filtra(self):
        api = ApiFalsa(productos=[PRODUCTO])
        asistente.ejecutar(
            {"intencion": "buscar_producto", "consulta": "casco", "tipo": "todos"}, api=api
        )
        self.assertIsNone(api.busquedas[0]["tipo"])

    def test_servicios_consulta_la_api(self):
        api = ApiFalsa()
        datos = asistente.ejecutar({"intencion": "servicio_tecnico"}, api=api)
        self.assertEqual(datos["tipo"], "servicios")
        self.assertEqual(api.pedidos_de_servicios, 1)
        self.assertEqual(datos["servicios"][0]["precio"], "Gs. 120.000")


class ResponderTest(unittest.TestCase):
    def test_humano_no_consulta_ni_redacta(self):
        cliente = ClienteFalso(plan={"intencion": "humano", "consulta": "", "tipo": "todos"})
        api = ApiFalsa()
        r = asistente.responder("quiero hablar con una persona", [], api=api, cliente=cliente)
        self.assertEqual(r["intencion"], "humano")
        self.assertIn("alguien del taller", r["respuesta"])
        self.assertEqual(api.busquedas, [])
        self.assertEqual(cliente.redacciones, 0)

    def test_producto_encontrado_se_redacta_con_el_modelo(self):
        cliente = ClienteFalso(texto="Sí, tenemos la cámara Caloi a Gs. 310.000.")
        api = ApiFalsa(productos=[PRODUCTO])
        r = asistente.responder("tenes camara 26?", [], api=api, cliente=cliente)
        self.assertEqual(r["respuesta"], "Sí, tenemos la cámara Caloi a Gs. 310.000.")
        self.assertEqual(cliente.redacciones, 1)
        # El precio tiene que haber viajado en el contexto de la redacción.
        self.assertIn("Gs. 310.000", cliente.ultimo_contexto[0]["content"])

    def test_sin_resultados_no_se_llama_al_modelo(self):
        """La garantía central: sin datos no hay forma de que invente un precio."""
        cliente = ClienteFalso(texto="NO DEBERÍA APARECER")
        api = ApiFalsa(productos=[], total=0)
        r = asistente.responder("tenes una bici voladora laser?", [], api=api, cliente=cliente)
        self.assertEqual(cliente.redacciones, 0, "se llamó al modelo teniendo cero resultados")
        self.assertNotIn("NO DEBERÍA APARECER", r["respuesta"])
        self.assertIn("No lo tengo listado", r["respuesta"])
        self.assertFalse(r["error"])

    def test_sin_consulta_pide_precision(self):
        cliente = ClienteFalso(plan={"intencion": "buscar_producto", "consulta": "", "tipo": "todos"})
        api = ApiFalsa()
        r = asistente.responder("tenes repuestos?", [], api=api, cliente=cliente)
        self.assertEqual(r["datos"]["tipo"], "sin_consulta")
        self.assertIn("qué producto", r["respuesta"])
        self.assertEqual(api.busquedas, [])
        self.assertEqual(cliente.redacciones, 0)

    def test_ubicacion_usa_plantilla(self):
        cliente = ClienteFalso(plan={"intencion": "ubicacion", "consulta": "", "tipo": "todos"})
        r = asistente.responder("donde estan?", [], api=ApiFalsa(), cliente=cliente)
        self.assertIn("Capiatá", r["respuesta"])
        self.assertEqual(cliente.redacciones, 0)

    def test_envio_usa_plantilla_y_no_queda_cortada(self):
        cliente = ClienteFalso(plan={"intencion": "envio", "consulta": "", "tipo": "todos"})
        r = asistente.responder("hacen envios?", [], api=ApiFalsa(), cliente=cliente)
        self.assertIn("envíos", r["respuesta"])
        self.assertNotIn("Hacemos envíos:", r["respuesta"])
        self.assertEqual(cliente.redacciones, 0)

    def test_mensaje_muy_corto_no_gasta_llamadas(self):
        cliente = ClienteFalso()
        api = ApiFalsa()
        r = asistente.responder("a", [], api=api, cliente=cliente)
        self.assertEqual(cliente.clasificaciones, 0)
        self.assertEqual(api.busquedas, [])
        self.assertFalse(r["error"])

    def test_falla_del_modelo_es_aviso_tecnico(self):
        cliente = ClienteFalso(error=gemini.ErrorGemini("cuota agotada"))
        r = asistente.responder("hola tenes camaras?", [], api=ApiFalsa(), cliente=cliente)
        self.assertTrue(r["error"], "un fallo del modelo debe marcarse como error")
        self.assertIn("problema técnico", r["respuesta"])

    def test_falla_del_catalogo_es_aviso_tecnico(self):
        api = ApiFalsa(error=catalogo.ErrorCatalogo("api caída"))
        cliente = ClienteFalso()
        r = asistente.responder("tenes camaras 26?", [], api=api, cliente=cliente)
        self.assertTrue(r["error"])
        self.assertIn("catálogo", r["respuesta"])


class FotoTest(unittest.TestCase):
    """Qué foto se manda cuando el cliente pregunta por un producto."""

    CUBIERTA_275 = {
        "id": "275", "nombre": "CUBIERTA CONTINENTAL 27.5X2.20 RACE KING",
        "precio": "Gs. 319.000", "disponibilidad": "Figura en catálogo; confirmar disponibilidad",
        "imagen": "https://cdn.test/275.jpg",
    }
    CUBIERTA_29 = {
        "id": "29", "nombre": "CUBIERTA CONTINENTAL 29X2.20 RACE KING",
        "precio": "Gs. 335.000", "disponibilidad": "Figura en catálogo; confirmar disponibilidad",
        "imagen": "https://cdn.test/29.jpg",
    }

    def test_prefiere_la_medida_que_pidio_el_cliente(self):
        """El caso real: pedía 29, la lista traía la 27.5 primero y se mandaba esa foto."""
        elegido = asistente._elegir_foto(
            [self.CUBIERTA_275, self.CUBIERTA_29], "cubierta 29"
        )
        self.assertEqual(elegido["id"], "29", "mandó la foto de otra medida")

    def test_sin_consulta_elige_el_primero(self):
        elegido = asistente._elegir_foto([self.CUBIERTA_275, self.CUBIERTA_29])
        self.assertEqual(elegido["id"], "275")

    def test_la_medida_le_gana_al_stock(self):
        """Si la medida que pidió está agotada, manda esa igual: quiere verla."""
        agotada_29 = dict(self.CUBIERTA_29, disponibilidad="Sin stock según catálogo")
        elegido = asistente._elegir_foto([self.CUBIERTA_275, agotada_29], "cubierta 29")
        self.assertEqual(elegido["id"], "29")

    def test_prefiere_un_producto_disponible(self):
        elegido = asistente._elegir_foto([AGOTADO, PRODUCTO])
        self.assertEqual(elegido["id"], PRODUCTO["id"], "eligió un producto sin stock")

    def test_si_todos_estan_agotados_igual_manda_foto(self):
        elegido = asistente._elegir_foto([AGOTADO])
        self.assertEqual(elegido["id"], AGOTADO["id"])

    def test_sin_imagenes_devuelve_none(self):
        self.assertIsNone(asistente._elegir_foto([{"nombre": "sin foto"}]))

    def test_lista_vacia_devuelve_none(self):
        self.assertIsNone(asistente._elegir_foto([]))

    def test_ejecutar_adjunta_la_foto_elegida(self):
        api = ApiFalsa(productos=[AGOTADO, PRODUCTO])
        datos = asistente.ejecutar(
            {"intencion": "buscar_producto", "consulta": "camara 26", "tipo": "todos"}, api=api
        )
        self.assertIn("imagen", datos)
        self.assertEqual(datos["imagen"]["producto"], PRODUCTO["nombre"])
        self.assertTrue(datos["imagen"]["url"].startswith("https://cdn.test/"))

    def test_datos_dicen_cuantos_hay_y_cuantos_se_muestran(self):
        """Para que el bot pueda decir 'tengo 5, te paso algunos' y no mostrar uno solo."""
        api = ApiFalsa(productos=[PRODUCTO, AGOTADO], total=5)
        datos = asistente.ejecutar(
            {"intencion": "buscar_producto", "consulta": "piñon 7v", "tipo": "todos"}, api=api
        )
        self.assertEqual(datos["total"], 5)
        self.assertEqual(datos["mostrados"], 2)

    def test_el_prompt_le_pide_no_quedarse_con_uno_solo(self):
        cliente = ClienteFalso(texto="Tengo 5 opciones: ...")
        api = ApiFalsa(productos=[PRODUCTO, AGOTADO], total=5)
        asistente.responder("tenes piñon de 7 velocidades?", [], api=api, cliente=cliente)
        contexto = cliente.ultimo_contexto[0]["content"]
        self.assertIn('"mostrados": 2', contexto)
        self.assertIn('"total": 5', contexto)

    def test_servicio_tecnico_no_lleva_foto(self):
        datos = asistente.ejecutar({"intencion": "servicio_tecnico"}, api=ApiFalsa())
        self.assertNotIn("imagen", datos)

    def test_la_foto_sale_en_la_respuesta(self):
        cliente = ClienteFalso(texto="Sí, mirá este casco.")
        api = ApiFalsa(productos=[PRODUCTO])
        r = asistente.responder("tenes cascos?", [], api=api, cliente=cliente)
        self.assertEqual(r["imagen"]["producto"], PRODUCTO["nombre"])
        # El modelo tiene que saber qué producto muestra la foto para hablar de ese.
        self.assertIn(PRODUCTO["nombre"], cliente.ultimo_contexto[0]["content"])


class CoincidenciaTest(unittest.TestCase):
    def test_normaliza_acentos_y_mayusculas(self):
        self.assertEqual(asistente._normalizar("CÁMARA 26x1.50"), "camara 26x1 50")

    def test_puntaje_completo_cuando_coincide_todo(self):
        self.assertEqual(asistente._puntaje_coincidencia("CASCO SCOTT DOPPIO", "casco scott"), 1.0)

    def test_puntaje_parcial(self):
        self.assertAlmostEqual(
            asistente._puntaje_coincidencia("CASCO SCOTT DOPPIO", "casco shimano"), 0.5
        )

    def test_sin_consulta_no_puntua(self):
        self.assertEqual(asistente._puntaje_coincidencia("CASCO", ""), 0.0)


class PedidoTest(unittest.TestCase):
    """El bot arma el pedido, lo deja pendiente y deriva la conversación a una persona."""

    def _responder(self, plan, api=None, crear=None, marcar=None, historial=None):
        cliente = ClienteFalso(plan=plan)
        creados = []
        derivadas = []

        def crear_pedido(lineas):
            creados.append(lineas)
            return {"id": "pedido-1", "status": "pending_confirmation"} if crear is None else crear(lineas)

        def marcar_humano():
            derivadas.append(True)

        resultado = asistente.responder(
            "quiero 2 camaras 26",
            historial or [],
            api=api or ApiFalsa(productos=[PRODUCTO]),
            cliente=cliente,
            crear_pedido=crear_pedido,
            marcar_humano=marcar_humano if marcar is None else marcar,
        )
        return resultado, creados, derivadas

    def _plan(self, items, **extra):
        return {"intencion": "armar_pedido", "consulta": "", "tipo": "todos", "items": items, **extra}

    def test_arma_el_pedido_con_cantidad_y_producto(self):
        resultado, creados, _ = self._responder(
            self._plan([{"consulta": "camara 26", "cantidad": 2}])
        )
        self.assertEqual(resultado["intencion"], "armar_pedido")
        self.assertTrue(resultado["datos"]["guardado"])
        self.assertEqual(len(creados), 1)
        self.assertEqual(creados[0][0]["cantidad"], 2)
        self.assertEqual(creados[0][0]["producto"]["id"], PRODUCTO["id"])

    def test_la_respuesta_muestra_cantidad_y_precio(self):
        resultado, _, _ = self._responder(
            self._plan([{"consulta": "camara 26", "cantidad": 2}])
        )
        self.assertIn("2 x", resultado["respuesta"])
        self.assertIn(PRODUCTO["nombre"], resultado["respuesta"])
        # 310.000 x 2
        self.assertIn("620.000", resultado["respuesta"])

    def test_deriva_la_conversacion_a_una_persona(self):
        _, _, derivadas = self._responder(
            self._plan([{"consulta": "camara 26", "cantidad": 1}])
        )
        self.assertEqual(derivadas, [True], "no derivó la conversación")

    def test_varios_productos_en_un_pedido(self):
        api = ApiFalsa(productos=[PRODUCTO])
        resultado, creados, _ = self._responder(
            self._plan(
                [
                    {"consulta": "camara 26", "cantidad": 2},
                    {"consulta": "casco scott", "cantidad": 1},
                ]
            ),
            api=api,
        )
        self.assertEqual(len(creados[0]), 2)

    def test_cantidad_invalida_cae_en_uno(self):
        resultado, creados, _ = self._responder(
            self._plan([{"consulta": "camara 26", "cantidad": 0}])
        )
        self.assertEqual(creados[0][0]["cantidad"], 1)

    def test_si_no_encuentra_nada_no_crea_pedido(self):
        resultado, creados, derivadas = self._responder(
            self._plan([{"consulta": "bici voladora laser", "cantidad": 1}]),
            api=ApiFalsa(productos=[], total=0),
        )
        self.assertEqual(creados, [])
        self.assertEqual(derivadas, [])
        self.assertIn("No lo tengo listado", resultado["respuesta"])

    def test_si_la_base_falla_avisa_en_vez_de_mentir(self):
        resultado, _, _ = self._responder(
            self._plan([{"consulta": "camara 26", "cantidad": 1}]), crear=lambda lineas: None
        )
        self.assertFalse(resultado["datos"]["guardado"])
        self.assertIn("no pude registrarlo", resultado["respuesta"].lower())

    def test_sin_items_pide_que_le_diga_que_quiere(self):
        resultado, creados, _ = self._responder(self._plan([]))
        self.assertEqual(creados, [])
        self.assertIn("¿Qué querés encargar?", resultado["respuesta"])


class TurnoTest(unittest.TestCase):
    """El turno sólo registra qué mantenimiento y qué día: no hay horarios ni cupos."""

    def _responder(self, plan, crear=None):
        cliente = ClienteFalso(plan=plan)
        creados = []

        def crear_turno(servicio, fecha):
            creados.append((servicio, fecha))
            if crear is not None:
                return crear(servicio, fecha)
            return {"id": "turno-1"}

        resultado = asistente.responder(
            "quiero llevar la bici",
            [],
            api=ApiFalsa(),
            cliente=cliente,
            crear_turno=crear_turno,
        )
        return resultado, creados

    def _plan(self, servicio="completo", fecha="el sabado"):
        return {
            "intencion": "agendar_turno",
            "consulta": "",
            "tipo": "todos",
            "servicio": servicio,
            "fecha": fecha,
        }

    def test_crea_el_turno_con_servicio_y_fecha(self):
        resultado, creados = self._responder(self._plan())
        self.assertEqual(len(creados), 1)
        servicio, fecha = creados[0]
        self.assertEqual(servicio, "Completo")
        self.assertEqual(fecha.weekday(), 5, "no cayó en sábado")

    def test_dice_la_duracion_y_la_ubicacion(self):
        resultado, _ = self._responder(self._plan())
        texto = resultado["respuesta"]
        self.assertIn("24 y 48 hs", texto)
        self.assertIn("Capiatá", texto)
        self.assertIn("8:00 a 18:00", texto)

    def test_incluye_el_precio_del_plan(self):
        resultado, _ = self._responder(self._plan())
        self.assertIn("Gs. 120.000", resultado["respuesta"])

    def test_sin_servicio_pregunta_cual(self):
        resultado, creados = self._responder(self._plan(servicio="ninguno"))
        self.assertEqual(creados, [])
        self.assertIn("¿Cuál de los mantenimientos", resultado["respuesta"])

    def test_sin_fecha_pregunta_que_dia(self):
        resultado, creados = self._responder(self._plan(fecha=""))
        self.assertEqual(creados, [])
        self.assertIn("qué día", resultado["respuesta"].lower())

    def test_fecha_que_no_entiende_la_repite(self):
        resultado, creados = self._responder(self._plan(fecha="cuando pueda"))
        self.assertEqual(creados, [])
        self.assertIn("No entendí", resultado["respuesta"])

    def test_si_no_se_guarda_no_dice_que_anoto(self):
        resultado, _ = self._responder(self._plan(), crear=lambda s, f: None)
        self.assertFalse(resultado["datos"]["guardado"])
        self.assertNotIn("anoté", resultado["respuesta"])
        self.assertIn("no pude registrarlo", resultado["respuesta"])

    def test_no_deriva_la_conversacion(self):
        """El turno lo resuelve el bot; no hace falta que lo tome una persona."""
        cliente = ClienteFalso(plan=self._plan())
        derivadas = []
        asistente.responder(
            "quiero llevar la bici",
            [],
            api=ApiFalsa(),
            cliente=cliente,
            crear_turno=lambda s, f: {"id": "t"},
            marcar_humano=lambda: derivadas.append(True),
        )
        self.assertEqual(derivadas, [])


class PlantillaEnvioTest(unittest.TestCase):
    def test_sin_notas_usa_el_texto_por_defecto(self):
        texto = asistente._plantilla_fija({"tipo": "envio", "envio": None, "retiro": None})
        self.assertIn("coordin", texto.lower())

    def test_con_notas_las_incorpora(self):
        texto = asistente._plantilla_fija(
            {
                "tipo": "envio",
                "envio": "El costo se coordina por WhatsApp según la zona.",
                "retiro": "Te confirmamos la dirección por WhatsApp.",
            }
        )
        self.assertIn("según la zona", texto)
        self.assertIn("retirar en el local", texto)


if __name__ == "__main__":
    unittest.main()
