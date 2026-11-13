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

Formato: `{"detail": "..."}`.

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
  "dry_run": false
}
```

`message` tiene entre 1 y 1000 caracteres. `dry_run=true` valida el plan sin ejecutar
la consulta.

### Respuesta

```json
{
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

Cada mensaje del asistente guarda `intent`, `confidence`, `status` y `query_plan` para
auditoría. El `data` completo de la respuesta no se duplica en la tabla: se devuelve
en el POST y puede reproducirse desde el plan. Usuario y asistente se confirman en una
sola transacción y `sequence` garantiza el orden del transcript.

`GET /api/v1/conversations` devuelve una lista ordenada por `updated_at` descendente.
`GET /api/v1/conversations/{id}/messages` devuelve una lista ordenada por `sequence`;
cada elemento incluye `role`, `content`, `intent`, `confidence`, `status`,
`query_plan` y `created_at`. Ambos listados aceptan `limit` y `offset`.

### Memoria acotada

El chat persistente carga como máximo **10 mensajes** y **4000 caracteres** de
historial. Se conservan los mensajes más recientes; el contexto no crece sin límite.
El mock resuelve seguimientos deterministas como “¿Y en septiembre?” o “¿Y el CTR?”
reutilizando el último plan válido; las comparaciones requieren dos periodos
explícitos. Un proveedor LLM real recibirá el mismo contexto acotado en
`LLMProvider.generate(..., context=...)`.

## Ejemplo con curl

```bash
curl -s http://127.0.0.1:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $JEV_API_KEY" \
  -d '{"message": "Compara este mes con el mes pasado"}'
```

Para probar gráficamente, abre la colección [`bruno/jev-ai`](../bruno/jev-ai) en Bruno y
selecciona el entorno `Local`.
