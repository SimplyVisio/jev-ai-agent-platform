# Cliente TypeSafe JEV

JEV AI usa el endpoint nativo de TypeSafe System One para hacer preguntas
estructuradas sobre un estado, no para generar texto libre. El proveedor está aislado
detrás de `DecisionProvider`; `JevIntentClassifier` lo usa para clasificar mensajes y
`MockDecisionProvider` es el proveedor offline predeterminado.

## Contrato

`src/jev_ai/ai/jev/contracts.py` define los modelos Pydantic de petición y respuesta:

| Elemento | Uso |
|---|---|
| `DecisionRequest` | `state`, `questions` y `model` opcional |
| `NoulQuestion` | Pregunta de sí/no con probabilidad 0–1 |
| `ChoiceQuestion` | Clasificación con un mapa de opciones |
| `ScoreQuestion` | Escala ordinal de 2 a 10 niveles; `legend` es `dict[str, str]` |
| `BoxQuestion` | Localización de una región en una imagen (Jev 1.14+) |
| `DecisionResponse` | Modelo resuelto, respuestas y usage |
| `DecisionProvider` | Puerto para clientes de decisiones |

Las respuestas `score` aceptan fracciones y su `legend` se valida como un mapa de
nivel a descripción. `BoxAnswer` normaliza `top`, `bottom`, `left` y `right` entre 0 y 1.

Las preguntas usan una unión discriminada por `type`. La petición rechaza campos
desconocidos; la respuesta ignora campos nuevos para tolerar evoluciones del
proveedor. `model` se omite si se usa el modelo configurado en el cliente.

## Cliente

`TypeSafeJevProvider` envía `POST {base_url}/v1/systemone` con autenticación
`Authorization: Bearer <key>`. Por defecto usa `jev-1.13.0` para que las respuestas sean
reproducibles, timeout de 120 s y un `transport` de `httpx` inyectable en tests.

El cliente reintenta automáticamente `429` y `529` (dos reintentos por defecto, con
backoff exponencial) y respeta `Retry-After` cuando viene en segundos. Antes de enviar,
valida el body: máximo 32 MiB, 64 niveles de anidación, números finitos y UTF-8 sin BOM.

```python
from jev_ai.ai.jev.client import TypeSafeJevProvider
from jev_ai.ai.jev.contracts import ChoiceQuestion, DecisionRequest

client = TypeSafeJevProvider(api_key="...")
result = await client.decide(
    DecisionRequest(
        state="Help! My payouts have been failing for 3 days.",
        questions={
            "department": ChoiceQuestion(
                instructions="Which team should handle this?",
                criteria={
                    "billing": "Payments, invoicing, refunds",
                    "technical": "Bugs, outages, integrations",
                },
            )
        },
    )
)
answer = result.response.answers["department"]
```

El `request_id` de la cabecera `x-typesafe-request-id` se conserva en
`DecisionResult` para soporte. El uso de tokens se normaliza a `TokenUsage`.

## Errores

| Error | Cuándo |
|---|---|
| `JevRequestError` | La petición local incumple tamaño, anidación o números finitos |
| `JevTimeoutError` | Se agota el timeout de un intento |
| `JevConnectionError` | Falla la conexión |
| `JevAPIError` | HTTP 4xx/5xx; incluye estado, `detail`, `request_id` y `Retry-After` |
| `JevResponseError` | JSON inválido o respuesta fuera del contrato |

Los reintentos cubren solo `429` y `529`. Un `4xx` de validación no se reintenta. Al
agotar los intentos, `JevAPIError` conserva `request_id`, `retry_after` y el detalle del
último error recibido.

## Mock y selección de proveedor

`ai/jev/mock.py` implementa `MockDecisionProvider`. Para preguntas `choice` llamadas
`intent` con el catálogo completo, responde con las mismas reglas que
`RuleBasedClassifier`; el resto de preguntas recibe una respuesta válida trivial. Es
determinista, no mide la calidad de un Jev real y existe para desarrollo y tests.

`ai/jev/factory.py` selecciona el proveedor al arrancar:

| `JEV_PROVIDER` | Resultado |
|---|---|
| `mock` (predeterminado) | `MockDecisionProvider` |
| `typesafe` | `TypeSafeJevProvider`; exige `TYPESAFE_API_KEY` |

`JevIntentClassifier` valida que la opción devuelta esté en el catálogo. Si Jev falla o
devuelve una opción inválida, usa `RuleBasedClassifier` como fallback y lo deja escrito
en `intent_reason` (`jev_fallback:...`). La traza del CLI muestra ese motivo en el nodo
`classify_intent`.

## Instrumentación

`InstrumentedDecisionProvider` registra latencia, tokens y coste estimado como
`call_type="decision"` en `model_calls`. Solo existe tarifa registrada para
`jev-1.13.0`; una versión desconocida deja el coste en `null`.

## Límites actuales

- Integrado en `ChatService` a través de `JevIntentClassifier`; no se usa en las
  políticas ni en la ejecución de planes.
- `box` existe en el contrato, pero no hay helpers de `assets` ni la cabecera
  `TypeSafe-Danger-Zone-Images`; para usarlo hay que enviar las imágenes en `state` y
  elegir un modelo 1.14+.
- Sin streaming; TypeSafe no lo soporta en este endpoint. Tampoco se implementa
  compresión gzip/zstd: el body se envía sin comprimir.
- El formato exacto del JSON de error y el prefijo de la API key siguen sin confirmarse;
  el cliente lee `detail`, `error` o `message` y no asume un prefijo concreto.
- El timeout de 120 s es una recomendación del cookbook, no un límite publicado.
