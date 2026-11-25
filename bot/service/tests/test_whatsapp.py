# bot/service/tests/test_whatsapp.py
"""Pruebas del adaptador de WhatsApp, sin tocar la red ni Meta.

Lo que se verifica es justamente lo que no se puede probar a mano: que la firma se
valide bien, que un reintento de Meta no mande la respuesta dos veces, y que el mensaje
llegue al asistente con el teléfono en el formato que espera la base.

    python -m unittest discover -s bot/service/tests -t . -v
"""
from __future__ import annotations

import hashlib
import hmac
import json
import unittest

from bot.service import config, whatsapp


def payload(telefono="595995622412", texto="hola tenes camaras 26?", mensaje_id="wamid.ABC123"):
    """Un webhook con la misma forma que manda Meta."""
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "123456",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {"phone_number_id": "999"},
                            "contacts": [{"profile": {"name": "Ana"}, "wa_id": telefono}],
                            "messages": [
                                {
                                    "from": telefono,
                                    "id": mensaje_id,
                                    "timestamp": "1700000000",
                                    "type": "text",
                                    "text": {"body": texto},
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }


class FirmaTest(unittest.TestCase):
    def setUp(self):
        self.original = config.META_APP_SECRET

    def tearDown(self):
        config.META_APP_SECRET = self.original

    def _firmar(self, cuerpo: bytes, secreto: str) -> str:
        return "sha256=" + hmac.new(secreto.encode(), cuerpo, hashlib.sha256).hexdigest()

    def test_firma_correcta(self):
        config.META_APP_SECRET = "secreto-de-prueba"
        cuerpo = b'{"hola":"mundo"}'
        self.assertTrue(whatsapp.verificar_firma(cuerpo, self._firmar(cuerpo, "secreto-de-prueba")))

    def test_firma_de_otro_secreto_se_rechaza(self):
        config.META_APP_SECRET = "secreto-de-prueba"
        cuerpo = b'{"hola":"mundo"}'
        self.assertFalse(whatsapp.verificar_firma(cuerpo, self._firmar(cuerpo, "otro")))

    def test_cuerpo_alterado_se_rechaza(self):
        config.META_APP_SECRET = "secreto-de-prueba"
        firma = self._firmar(b'{"hola":"mundo"}', "secreto-de-prueba")
        self.assertFalse(whatsapp.verificar_firma(b'{"hola":"mundo!"}', firma))

    def test_sin_cabecera_se_rechaza(self):
        config.META_APP_SECRET = "secreto-de-prueba"
        self.assertFalse(whatsapp.verificar_firma(b"{}", None))
        self.assertFalse(whatsapp.verificar_firma(b"{}", ""))

    def test_cabecera_sin_el_prefijo_se_rechaza(self):
        config.META_APP_SECRET = "secreto-de-prueba"
        cuerpo = b"{}"
        firma = self._firmar(cuerpo, "secreto-de-prueba").removeprefix("sha256=")
        self.assertFalse(whatsapp.verificar_firma(cuerpo, firma))

    def test_sin_secreto_configurado_acepta_todo(self):
        """Modo prueba: se acepta pero se avisa en el log."""
        config.META_APP_SECRET = ""
        self.assertTrue(whatsapp.verificar_firma(b"{}", None))


class NormalizarTest(unittest.TestCase):
    def test_agrega_el_mas(self):
        self.assertEqual(whatsapp.normalizar_telefono("595995622412"), "+595995622412")

    def test_no_duplica_el_mas(self):
        self.assertEqual(whatsapp.normalizar_telefono("+595995622412"), "+595995622412")

    def test_limpia_espacios_y_guiones(self):
        self.assertEqual(whatsapp.normalizar_telefono("+595 995-622-412"), "+595995622412")

    def test_vacio(self):
        self.assertEqual(whatsapp.normalizar_telefono(""), "")


class ExtraerTest(unittest.TestCase):
    def test_saca_un_mensaje_de_texto(self):
        mensajes = whatsapp.extraer_mensajes(payload())
        self.assertEqual(len(mensajes), 1)
        self.assertEqual(mensajes[0]["telefono"], "+595995622412")
        self.assertEqual(mensajes[0]["texto"], "hola tenes camaras 26?")
        self.assertEqual(mensajes[0]["mensaje_id"], "wamid.ABC123")

    def test_ignora_lo_que_no_es_texto(self):
        datos = payload()
        datos["entry"][0]["changes"][0]["value"]["messages"][0]["type"] = "image"
        self.assertEqual(whatsapp.extraer_mensajes(datos), [])

    def test_ignora_estados_de_entrega(self):
        solo_estados = {
            "entry": [{"changes": [{"value": {"statuses": [{"id": "x", "status": "read"}]}}]}]
        }
        self.assertEqual(whatsapp.extraer_mensajes(solo_estados), [])

    def test_payload_vacio(self):
        self.assertEqual(whatsapp.extraer_mensajes({}), [])

    def test_ignora_texto_vacio(self):
        datos = payload(texto="   ")
        self.assertEqual(whatsapp.extraer_mensajes(datos), [])

    def test_varios_mensajes_en_un_payload(self):
        datos = payload()
        valor = datos["entry"][0]["changes"][0]["value"]
        valor["messages"].append(
            {"from": "595111111111", "id": "wamid.OTRO", "type": "text", "text": {"body": "hola"}}
        )
        self.assertEqual(len(whatsapp.extraer_mensajes(datos)), 2)


class AtenderTest(unittest.TestCase):
    def setUp(self):
        whatsapp.limpiar_vistos()
        self.enviados = []
        self.consultas = []

    def _responder(self, texto, historial, telefono):
        self.consultas.append((telefono, texto))
        return {"respuesta": f"eco: {texto}", "intencion": "buscar_producto", "imagen": None}

    def _enviar(self, telefono, resultado):
        self.enviados.append((telefono, resultado["respuesta"]))
        return True

    def atender(self, datos, enviar=None):
        return whatsapp.atender(
            datos, responder=self._responder, enviar=enviar or self._enviar
        )

    def test_responde_al_cliente(self):
        procesados = self.atender(payload())
        self.assertEqual(len(procesados), 1)
        self.assertEqual(self.enviados, [("+595995622412", "eco: hola tenes camaras 26?")])

    def test_el_telefono_llega_normalizado_al_asistente(self):
        self.atender(payload())
        self.assertEqual(self.consultas[0][0], "+595995622412")

    def test_un_reintento_de_meta_no_responde_dos_veces(self):
        """Meta reintenta el mismo evento hasta 7 veces si tarda en llegar el 200."""
        self.atender(payload())
        self.atender(payload())  # mismo mensaje_id
        self.assertEqual(len(self.enviados), 1, "respondió dos veces el mismo mensaje")

    def test_mensajes_distintos_si_se_responden(self):
        self.atender(payload(mensaje_id="wamid.1"))
        self.atender(payload(mensaje_id="wamid.2"))
        self.assertEqual(len(self.enviados), 2)

    def test_si_falla_el_envio_se_permite_reintentar(self):
        """Si no se pudo mandar, el reintento de Meta tiene que volver a intentarlo."""
        self.atender(payload(), enviar=lambda t, r: False)
        self.atender(payload())  # mismo id, pero el envío anterior falló
        self.assertEqual(len(self.enviados), 1, "el reintento se descartó por duplicado")

    def test_si_el_asistente_falla_no_se_cae_todo(self):
        def responder_roto(texto, historial, telefono):
            raise RuntimeError("boom")

        procesados = whatsapp.atender(
            payload(), responder=responder_roto, enviar=self._enviar
        )
        self.assertEqual(procesados, [])
        self.assertEqual(self.enviados, [])


class EnviarRespuestaTest(unittest.TestCase):
    """Con foto va como imagen con pie; si la imagen falla, se manda el texto solo."""

    def setUp(self):
        self.original = (whatsapp.enviar_imagen, whatsapp.enviar_texto)
        self.llamadas = []

    def tearDown(self):
        whatsapp.enviar_imagen, whatsapp.enviar_texto = self.original

    def _espia(self, imagen_ok=True, texto_ok=True):
        def imagen(telefono, url, pie=""):
            self.llamadas.append(("imagen", url, pie))
            return imagen_ok

        def texto(telefono, cuerpo):
            self.llamadas.append(("texto", cuerpo))
            return texto_ok

        whatsapp.enviar_imagen = imagen
        whatsapp.enviar_texto = texto

    def test_con_foto_manda_imagen_con_el_texto_de_pie(self):
        self._espia()
        resultado = {"respuesta": "Tenemos esta cámara", "imagen": {"url": "https://cdn/x.jpg"}}
        self.assertTrue(whatsapp.enviar_respuesta("+595995622412", resultado))
        self.assertEqual(self.llamadas[0][0], "imagen")
        self.assertEqual(self.llamadas[0][2], "Tenemos esta cámara")

    def test_sin_foto_manda_solo_texto(self):
        self._espia()
        self.assertTrue(whatsapp.enviar_respuesta("+595995622412", {"respuesta": "Hola"}))
        self.assertEqual([c[0] for c in self.llamadas], ["texto"])

    def test_si_la_foto_falla_manda_el_texto(self):
        self._espia(imagen_ok=False)
        resultado = {"respuesta": "Tenemos esta cámara", "imagen": {"url": "https://cdn/x.jpg"}}
        self.assertTrue(whatsapp.enviar_respuesta("+595995622412", resultado))
        self.assertEqual([c[0] for c in self.llamadas], ["imagen", "texto"])

    def test_el_pie_se_recorta_a_1024(self):
        """WhatsApp corta los pies de foto en 1024: se recorta acá y no se pierde el envío."""
        capturado = {}
        original = whatsapp._post_grafo

        def falso(cuerpo):
            capturado.update(cuerpo)
            return True, ""

        whatsapp._post_grafo = falso
        try:
            whatsapp.enviar_imagen("+595995622412", "https://cdn/x.jpg", "x" * 2000)
        finally:
            whatsapp._post_grafo = original

        self.assertEqual(capturado["type"], "image")
        self.assertLessEqual(len(capturado["image"]["caption"]), 1024)


class ConfiguracionTest(unittest.TestCase):
    def test_sin_credenciales_no_esta_configurado(self):
        original = (config.META_ACCESS_TOKEN, config.META_PHONE_NUMBER_ID, config.META_APP_SECRET)
        try:
            config.META_ACCESS_TOKEN = ""
            config.META_PHONE_NUMBER_ID = ""
            config.META_APP_SECRET = ""
            self.assertFalse(config.whatsapp_configurado())
            self.assertIn("META_ACCESS_TOKEN", config.falta_para_whatsapp())
        finally:
            config.META_ACCESS_TOKEN, config.META_PHONE_NUMBER_ID, config.META_APP_SECRET = original

    def test_con_las_tres_esta_configurado(self):
        original = (config.META_ACCESS_TOKEN, config.META_PHONE_NUMBER_ID, config.META_APP_SECRET)
        try:
            config.META_ACCESS_TOKEN = "t"
            config.META_PHONE_NUMBER_ID = "1"
            config.META_APP_SECRET = "s"
            self.assertTrue(config.whatsapp_configurado())
            self.assertEqual(config.falta_para_whatsapp(), "")
        finally:
            config.META_ACCESS_TOKEN, config.META_PHONE_NUMBER_ID, config.META_APP_SECRET = original


if __name__ == "__main__":
    unittest.main()
