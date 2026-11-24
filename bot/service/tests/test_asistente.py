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
    "precio_origen": 269565,
    "disponibilidad": "Figura en catálogo; confirmar disponibilidad",
    "categoria": "bicicletas",
    "link": "https://example.test/p/442954",
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
