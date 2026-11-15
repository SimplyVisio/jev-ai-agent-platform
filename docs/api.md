# API REST

Base local: `http://127.0.0.1:8000`. Todas las rutas privadas exigen la cabecera
`X-API-Key`; el `organization_id` sale de esa clave y nunca del cuerpo de la petición.
La fuente de verdad del contrato es `/openapi.json` y la documentación interactiva está
en `/docs`.

## Autenticación

```http
X-API-Key: jev_...
```

Las claves se crean con `scripts/create_api_key.py`. Se guarda solo su hash SHA-256.
Una cabecera ausente o una clave inválida devuelven `401` con el mismo mensaje.

## Errores

| Código | Cuándo |
|---|---|
| `401` | Falta la API key o no es válida |
| `404` | El recurso no existe o pertenece a otra organización |
| `422` | El cuerpo o los parámetros no cumplen el esquema |
| `500` | Error no controlado; incluye `trace_id` para localizar el log |

Formato: `{"detail": "..."}`. Las respuestas `500` añaden `trace_id`:

```json
{"detail": "Internal server error", "trace_id": "1cb74557-e7bd-4e35-a531-0d494081f35e"}
```

Todas las respuestas incluyen la cabecera `X-Trace-ID`. El identificador lo genera el
servidor; si el cliente envía `X-Trace-ID`, se ignora.

## Endpoints

| Método y ruta | Función |
|---|---|
| `GET /health` | Liveness público |
| `GET /api/v1/auth/me` | Organización autenticada |
| `GET/POST /api/v1/campaigns` | Listar / crear campañas |
| `GET/PATCH/DELETE /api/v1/campaigns/{id}` | Consultar / actualizar / archivar |
| `GET/POST /api/v1/campaigns/{id}/ads` | Listar / crear anuncios |
| `GET/PATCH/DELETE /api/v1/campaigns/{id}/ads/{ad_id}` | Consultar / actualizar / archivar |
| `GET /api/v1/analytics/overview` | Resumen de la organización |
| `GET /api/v1/analytics/campaigns` | Rendimiento por campaña |
| `GET /api/v1/analytics/ads` | Rendimiento por anuncio |
| `GET /api/v1/analytics/trends` | Serie temporal |
| `POST /api/v1/chat` | Chat offline stateless: lenguaje natural → QueryPlan → datos |
| `GET/POST /api/v1/conversations` | Listar / abrir conversaciones |
| `GET /api/v1/conversations/{id}` | Consultar una conversación |
| `GET /api/v1/conversations/{id}/messages` | Listar el transcript |
| `POST /api/v1/conversations/{id}/messages` | Enviar mensaje y persistir el turno |

Los listados aceptan `limit` (1–100, por defecto 50), `offset` y filtros de estado u
objetivo. `DELETE` archiva (`status=archived`), no borra datos.

Los endpoints de analítica exigen `date_from` y `date_to` inclusivos. `trends` acepta
`granularity=day|week|month`; las semanas empiezan en lunes. Fórmulas y semántica de
`reach` en [`metrics.md`](metrics.md).

## Formato de números

- Dinero: `Decimal` serializado como cadena con dos decimales (`"180.00"`).
- Ratios: `float` redondeado a seis decimales (`7.222222`) o `null` si el denominador
  es cero.

## Chat

`POST /api/v1/chat` es stateless: no guarda conversación ni usa Redis. LangGraph
orquesta la clasificación de intención, la propuesta de `QueryPlan`, la validación con
JEV AI y la ejecución con los servicios de analítica y marketing. Para guardar el
historial, usa los endpoints de conversaciones.

### Petición

```json
{
  "message": "¿Cuáles son los 3 mejores anuncios por ROAS en octubre de 2026?",
  "dry_run": false,
  "debug": false
}
```

`message` tiene entre 1 y 1000 caracteres. `dry_run=true` valida el plan sin ejecutar
la consulta. `debug=true` añade `trace`, la secuencia real de nodos del grafo con
tiempos y detalles acotados; sin él, `trace` es `null`. La traza operativa se persiste
siempre en `traces`, `spans` y `model_calls`; `debug` solo controla si se devuelve en
la respuesta.

### Respuesta

```json
{
  "trace_id": "1cb74557-e7bd-4e35-a531-0d494081f35e",
  "status": "ok",
  "intent": "top_ads_by_metric",
  "confidence": 0.95,
  "reply": "Top 3 anuncios por ROAS (2026-10-01 a 2026-10-31): ...",
  "query_plan": {
    "operation": "top_ads_by_metric",
    "metric": "roas",
    "date_from": "2026-10-01",
    "date_to": "2026-10-31",
    "limit": 3
  },
  "data": [
    {
      "ad_id": "00000000-0000-0000-0000-000000000000",
      "ad_name": "Prospecting Winner",
      "campaign_name": "Demo Prospecting",
      "metrics": {
        "impressions": 26400,
        "reach": null,
        "clicks": 1716,
        "landing_page_views": 1338,
        "spend": "1451.20",
        "leads": 240,
        "sales": 48,
        "revenue": "4560.00",
        "frequency": null,
        "ctr": 6.5,
        "cpc": 0.845,
        "cpm": 54.97,
        "cpl": 6.05,
        "conversion_rate": 17.94,
        "roas": 3.142
      }
    }
  ]
}
```

`status` puede ser:

| Valor | Significado |
|---|---|
| `ok` | Respondió con datos o validó un `dry_run` |
| `needs_clarification` | Intención ambigua, plan inválido o campaña inexistente |
| `error` | El proveedor LLM falló |

`query_plan` se incluye cuando existe un plan, incluso si fue rechazado. `data` es
`null` cuando no se ejecutó ninguna consulta.

Con `debug=true`, `trace` contiene elementos como:

```json
[
  {"node": "classify_intent", "detail": "intent=top_ads_by_metric; confidence=0.95; reason=jev:mock:deterministic", "duration_ms": 0.12},
  {"node": "propose_plan", "detail": "plan={...}", "duration_ms": 0.45},
  {"node": "validate_plan", "detail": "plan aceptado por las políticas de JEV AI", "duration_ms": 0.08},
  {"node": "execute_service", "detail": "consultando PostgreSQL con SQLAlchemy: top_ads_by_metric ...", "duration_ms": 8.21},
  {"node": "generate_response", "detail": "generando respuesta desde plantilla; caracteres=120", "duration_ms": 0.03}
]
```

Detalles del flujo, catálogo y políticas en [`chat.md`](chat.md).

## Conversaciones persistentes

Cada conversación pertenece a la organización de la API key. Un id de otra
organización devuelve `404`, igual que uno inexistente. El título es opcional: si no
se envía, se autogenera con el primer mensaje.

```http
POST /api/v1/conversations
Content-Type: application/json

{"title": "Análisis de octubre"}
```

```json
{
  "id": "3f4d2c1a-...",
  "organization_id": "39f20b86-...",
  "title": "Análisis de octubre",
  "created_at": "2026-11-13T16:30:00Z",
  "updated_at": "2026-11-13T16:30:00Z"
}
```

```http
POST /api/v1/conversations/{id}/messages
Content-Type: application/json

{"message": "Top 3 anuncios por ROAS en octubre de 2026"}
```

```json
{
  "conversation_id": "3f4d2c1a-...",
  "trace_id": "1cb74557-e7bd-4e35-a531-0d494081f35e",
  "user_message_id": "9a1e...",
  "assistant_message_id": "7b2c...",
  "status": "ok",
  "intent": "top_ads_by_metric",
  "confidence": 0.95,
  "reply": "Top 3 anuncios por ROAS (2026-10-01 a 2026-10-31): ...",
  "query_plan": {
    "operation": "top_ads_by_metric",
    "metric": "roas",
    "date_from": "2026-10-01",
    "date_to": "2026-10-31",
    "limit": 3
  },
  "data": []
}
```

El POST del mensaje también acepta `"debug": true`; la respuesta incluye `trace` con
los mismos pasos que `/chat`. La traza operativa se persiste en las tablas de
observabilidad; `debug` solo decide si también se devuelve en el cuerpo.

Cada mensaje del asistente guarda `intent`, `confidence`, `status` y `query_plan` para
auditoría. El `data` completo de la respuesta no se duplica en la tabla: se devuelve
en el POST y puede reproducirse desde el plan. Usuario y asistente se confirman en una
sola transacción y `sequence` garantiza el orden del transcript.

`GET /api/v1/conversations` devuelve una lista ordenada por `updated_at` descendente.
`GET /api/v1/conversations/{id}/messages` devuelve una lista ordenada por `sequence`;
cada elemento incluye `role`, `content`, `intent`, `confidence`, `status`,
`query_plan`, `trace_id` y `created_at`. Ambos listados aceptan `limit` y `offset`.

### Memoria acotada

El chat persistente carga como máximo **10 mensajes** y **4000 caracteres** de
historial. Se conservan los mensajes más recientes; el contexto no crece sin límite.
El mock resuelve seguimientos deterministas como “¿Y en septiembre?” o “¿Y el CTR?”
reutilizando el último plan válido; las comparaciones requieren dos periodos
explícitos. Un proveedor LLM real recibirá el mismo contexto acotado en
`LLMProvider.generate(..., context=...)`.

## Trazas y costes

Cada petición recibe un `trace_id` UUID generado en el servidor. El middleware abre el
contexto de structlog, añade `X-Trace-ID` a la respuesta y registra una línea
`http_request` con método, ruta, estado y duración. Los errores no controlados
registran `unhandled_exception` y devuelven el mismo `trace_id` al cliente.

El chat persiste, en una transacción independiente:

- `traces`: estado, intención, error, duración y detalles acotados (`dry_run`,
  `message_chars`, `span_count`, `model_call_count`). No guarda el mensaje ni la
  respuesta.
- `spans`: nodos del grafo con duración y detalle operativo.
- `model_calls`: proveedor, modelo, estado, latencia, tokens y coste estimado.

El coste es una estimación, no una factura. Se calcula con `Decimal` y una versión de
tarifas (`price_version`). Solo se estima el nivel de servicio `standard`; modelos o
tiers desconocidos devuelven `null`. La telemetría es best-effort: un fallo al
persistirla se registra en logs y no cambia la respuesta del chat.

Configuración relacionada:

| Variable | Uso |
|---|---|
| `LOG_LEVEL` | `DEBUG`, `INFO` (predeterminado), `WARNING`, `ERROR` o `CRITICAL` |
| `LLM_PROVIDER` | `mock` (predeterminado) u `openai` |
| `LLM_MODEL` | Modelo usado para estimar tokens y coste |
| `JEV_PROVIDER` | `mock` (predeterminado) o `typesafe` |
| `TYPESAFE_API_KEY` | Clave obligatoria con `JEV_PROVIDER=typesafe` |
| `JEV_MODEL` | Modelo de Jev (`jev-1.13.0` por defecto) |

## Ejemplo con curl

```bash
curl -s http://127.0.0.1:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $JEV_API_KEY" \
  -d '{"message": "Compara este mes con el mes pasado"}'
```

Para probar gráficamente, abre la colección [`bruno/jev-ai`](../bruno/jev-ai) en Bruno y
selecciona el entorno `Local`.
