# Servicio local del chatbot

El asistente de Jaka funcionando **en tu computadora**, sin WhatsApp y sin n8n. Sirve para
ver si contesta bien antes de meter a Meta, los tokens y el webhook en el medio.

```
Navegador  ──►  este servicio (127.0.0.1:8790)
                     │
                     ├─► Gemini (clasifica el mensaje y redacta)
                     ├─► API de catálogo (127.0.0.1:8787)  ← precios y stock reales
                     └─► PostgreSQL (opcional)             ← historial
```

## Requisitos

- Python 3.10 o superior.
- Una API key **gratis** de Gemini: [aistudio.google.com/apikey](https://aistudio.google.com/apikey)
  (no pide tarjeta).
- La API de catálogo, que ya está en este repo.

Para que guarde el historial en PostgreSQL hace falta además:

```powershell
py -3 -m pip install -r bot/db/requirements.txt
```

Sin eso el servicio arranca igual: guarda el historial en memoria y lo pierde al cerrar.
El `/health` te dice cuál de los dos modos está usando y por qué.

## Puesta en marcha

**1. Configurar la key.** Crear `bot/service/.env` (está en `.gitignore`, no se sube):

```
GEMINI_API_KEY=tu_key_de_aistudio
CATALOG_API_URL=http://127.0.0.1:8787
```

**2. Levantar la API de catálogo**, en una terminal:

```powershell
python bot/api/server.py
```

**3. Levantar el servicio**, en otra:

```powershell
python -m bot.service.server
```

**4. Abrir** <http://127.0.0.1:8790> y chatear. Ese servidor sólo escucha en loopback: no
queda expuesto a la red ni a internet.

Opcional, para el historial en PostgreSQL: levantarlo según `bot/db/README.md`, definir
`$env:DATABASE_URL` **antes** de arrancar el servicio y listo; no hay que tocar código.

## Variables

| Variable | Por defecto | Para qué |
|---|---|---|
| `GEMINI_API_KEY` | — | Obligatoria. Sin ella el servicio no arranca |
| `GEMINI_MODEL` | `gemini-3.1-flash-lite` | Modelo. Ver la nota de abajo antes de cambiarlo |
| `CATALOG_API_URL` | `http://127.0.0.1:8787` | Dónde está la API de catálogo |
| `SERVICE_HOST` / `SERVICE_PORT` | `127.0.0.1` / `8790` | Dónde escucha el servicio |
| `MAX_HISTORIAL` | `10` | Cuántos mensajes previos ve el modelo |
| `DATABASE_URL` | — | Si está, guarda en PostgreSQL |

**Sobre el modelo:** el default está medido, no elegido por gusto. En esta máquina,
`gemini-3.5-flash` tardó entre 17 y 35 s por respuesta y `gemini-3.8-flash` devolvió 503;
`gemini-3.1-flash-lite` responde en 1–2 s, que es lo que necesita un chat. Si lo cambiás,
medí la latencia antes de dejarlo.

## Cómo piensa

Dos llamadas al modelo, en este orden:

1. **Clasificar** — el modelo sólo decide qué quiere el cliente y qué buscar. Devuelve un
   JSON con la intención y las palabras clave (esquema fijo, no texto libre).
2. **Consultar** — el servicio va a la API de catálogo y trae precios, stock y servicios.
3. **Redactar** — el modelo escribe la respuesta con **esos** datos, y sólo con esos.

La regla que sostiene todo: **el modelo nunca contesta de memoria**. Si la búsqueda no
devuelve nada, no se lo llama para redactar: se responde con una plantilla honesta. Por eso
no puede inventar un precio que no exista.

Las respuestas de datos fijos (ubicación, envíos, "quiero hablar con una persona") se arman
con plantillas: gastan cero llamadas y no pueden equivocarse.

Si la consulta no encuentra nada, el servicio vuelve a buscar soltando la última palabra
("camaras 26 para mtb" → "camaras 26" → "camaras"), porque la API exige que coincidan
todas las palabras.

## Pruebas

```powershell
python -m unittest discover -s bot/service/tests -t . -v
```

Son 17 pruebas con dobles del modelo y del catálogo: no necesitan API key, ni red, ni base
de datos. Verifican el contrato que importa —entre otras, que **sin resultados no se llame
al modelo** y que un fallo se convierta en aviso técnico en vez de guardarse como respuesta.

## Lo que todavía no hace

- **No está conectado a WhatsApp.** No recibe ni manda mensajes reales; se prueba por el
  navegador o con `curl`.
- **No agenda turnos.** Puede explicar los planes de service y sus precios, pero no reserva:
  falta conectar las funciones de agenda que ya existen en `bot/db/repository.py`.
- **No arma pedidos.** Igual: `create_pending_order` está listo, pero ningún flujo lo llama.
- **No hay handoff real.** Cuando alguien pide una persona, responde con una plantilla; no
  avisa a nadie ni pausa el bot.
- **No hay n8n.** Se reemplazó por este servicio para la etapa local.

## Probarlo con curl

```powershell
$body = '{"texto":"hola tenes camaras 26?","telefono":"+595981234567"}'
Invoke-RestMethod -Uri http://127.0.0.1:8790/mensaje -Method Post -Body $body -ContentType 'application/json'
```

Devuelve `respuesta`, `intencion`, los `datos` que se consultaron y los milisegundos.
