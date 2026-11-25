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

## Foto del producto

Cuando el cliente pregunta por un producto, el servicio elige **una** foto de los resultados y la
devuelve junto con la respuesta.

- Elige el primer resultado con imagen que **no** esté agotado. Si todos lo están, manda el primero
  igual: a veces el cliente quiere ver el modelo justamente para encargarlo.
- Reusa los parámetros de tamaño de la tienda. La foto original del CDN pesa hasta 350 KB; con
  `?quality=85&fit=bounds&height=800&width=800` queda en **~60 KB**, que es lo que conviene mandar.
- Le avisa al modelo qué producto muestra la foto (`DATOS.imagen`), para que la respuesta hable de
  ese y no de otro de la lista.
- Manda **una** sola foto, no cinco: con una lista larga, cinco imágenes seguidas en WhatsApp se
  siente spam.

En el chat local se ve debajo del mensaje. **En WhatsApp todavía no se envía**: el servicio ya
devuelve `imagen: {producto, url}` y el adaptador del webhook tiene que mandarla como mensaje aparte
—por Cloud API, `type: "image"` con `link`, o subiéndola antes con `POST /media` y usando `media_id`.

> ⚠️ **Las fotos son de Ciclovía.** Mandárselas a clientes es uso comercial de material de terceros:
> es la condición #1 del `PLAN.md` (autorización escrita). Hasta tenerla, la tienda ya las muestra
> "como referencia" desde su CDN; decidí vos si el bot también.

## Pruebas

```powershell
python -m unittest discover -s bot/service/tests -t . -v
```

Son 99 pruebas con dobles del modelo y del catálogo: no necesitan API key, ni red, ni base
de datos. Verifican el contrato que importa —entre otras, que **sin resultados no se llame
al modelo**, que la foto se elija bien y que la URL de la imagen no duplique parámetros.

## Conectar WhatsApp

El servicio ya habla con la Cloud API de Meta. Sin credenciales funciona igual en el navegador; con
ellas empieza a atender mensajes reales.

### 1. Sacar el número de la app de WhatsApp

Un número no puede estar en la app y en la API a la vez (salvo coexistencia, que requiere verificación
de negocio). Si el número está en uso:

> **Desinstalar la app NO libera el número.** Hay que eliminarlo desde adentro:
> WhatsApp → Ajustes → Cuenta → **Eliminar mi cuenta**. Se pierden los chats de ese número.

### 2. Sacar las credenciales en Meta

1. [developers.facebook.com](https://developers.facebook.com) → **Crear app** → tipo **Business**.
2. En la app: **Agregar producto → WhatsApp**.
3. **API Setup**: agregar el número, verificar el código por SMS o llamada y ponerle nombre visible.
4. De ahí salen **Phone Number ID** y un **token temporal de 24 h**.
5. **Configuración de la app → Básica** → **Clave secreta** (el App Secret).

### 3. Exponer el webhook

Meta necesita una URL pública con HTTPS. Para probar alcanza un túnel:

```powershell
ngrok http 8790
```

Te da una URL tipo `https://algo.ngrok-free.app`. El webhook completo es esa URL + `/webhook`.

### 4. Configurar el webhook en Meta

En **WhatsApp → Configuración → Webhook**:

- **Callback URL**: `https://algo.ngrok-free.app/webhook`
- **Verify token**: el mismo que pongas en `META_VERIFY_TOKEN`

Al guardar, Meta hace un `GET` con un desafío y el servicio lo responde solo. Después hay que
**suscribir el campo `messages`**, que es el que trae los mensajes entrantes.

### 5. Completar el .env y reiniciar

```
META_PHONE_NUMBER_ID=
META_ACCESS_TOKEN=
META_APP_SECRET=
META_VERIFY_TOKEN=jaka-bici-2026
```

`/health` te dice qué falta si algo no está: `"whatsapp": "falta META_ACCESS_TOKEN"`.

> **El token temporal dura 24 horas.** Para un piloto sirve; para dejarlo andando hace falta un token
> permanente de un **System User** (Business Settings → Usuarios del sistema → generar token con
> `whatsapp_business_messaging`).

### Cómo queda el flujo

```
Meta → POST /webhook → verifica firma → contesta 200 YA → hilo aparte
   → asistente (clasificar, catálogo, redactar)
   → envía respuesta: foto con el texto de pie, o texto si la foto falla
   → guarda la conversación en PostgreSQL
```

Meta espera el 200 en unos 5 segundos y reintenta hasta 7 veces. Por eso se contesta primero y se
procesa después, y por eso los reintentos se deduplican por id de mensaje.

## Pedidos y turnos

Además de contestar, el bot puede cerrar dos cosas. Las dos se guardan en PostgreSQL y las dos
respetan la misma regla: **el bot no confirma nada por su cuenta**.

**Pedido.** Cuando el cliente dice que quiere comprar algo, el bot resuelve cada producto contra el
catálogo (precio y disponibilidad reales), arma el pedido como `pending_confirmation` y **pasa la
conversación a una persona**, que es la que cierra la venta. El mensaje muestra cantidades, precios y
total.

**Turno.** Cuando dice que quiere traer la bici para un service, el bot confirma **qué mantenimiento y
qué día**, y le dice las dos cosas que necesita saber para venir: **dónde es** y que el mantenimiento
lleva **entre 24 y 48 hs**. No hay horarios ni cupos: la recepción es en el mostrador, así que dos
clientes el mismo día no se pisan. El turno queda `pendiente` y no deriva la conversación.

Si el pedido o el turno no se pudieron guardar (base caída, falta de datos), el mensaje **no dice que
quedó anotado**: le pide al cliente que escriba al taller. Mentir con eso sería peor que fallar.

## Lo que todavía no hace

- **Falta cargar las credenciales de Meta.** El adaptador está hecho y probado con payloads simulados, pero sin `META_*` no manda ni recibe nada real.
- **No hay aviso real al taller.** El pedido queda en la base y la conversación se marca como
  `human`, pero nadie recibe una notificación: hay que mirar la base.
- **No pregunta la cantidad de a una.** Si el cliente dice "quiero cámaras", asume 1.
- **No cobra ni gestiona envíos.** El total es de productos; el envío se coordina aparte.
- **No hay n8n.** Se reemplazó por este servicio para la etapa local.

## Probarlo con curl

```powershell
$body = '{"texto":"hola tenes camaras 26?","telefono":"+595981234567"}'
Invoke-RestMethod -Uri http://127.0.0.1:8790/mensaje -Method Post -Body $body -ContentType 'application/json'
```

Devuelve `respuesta`, `intencion`, los `datos` que se consultaron y los milisegundos.
