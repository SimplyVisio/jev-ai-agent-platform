# Chat y QueryPlan

El chat permite consultar campañas y anuncios en lenguaje natural. Por defecto usa
mocks deterministas para Jev y para el LLM, sin API key externa ni coste; también
admite TypeSafe JEV y un proveedor OpenAI-compatible configurados por entorno. La
ejecución, las políticas y las respuestas siguen siendo deterministas: Jev clasifica y
el LLM solo propone el plan.

## Flujo

```text
START
  → classify_intent       JevIntentClassifier (mock o TypeSafe)
  → route_request         help | clarify | plan
  → propose_plan          LLMProvider (mock u OpenAI) + parse_query_plan
  → validate_plan         validate_query_plan (JEV AI)
  → execute_service       execute_query_plan (analytics + marketing)
  → generate_response     render_reply (plantilla con datos reales)
  → END
```

El grafo vive en `ai/workflows/graph.py` y se compila una sola vez en `ChatService`.
La sesión de base de datos se pasa por invocación en
`config["configurable"]["session"]`; el estado (`ChatState`) lleva el mensaje, la
intención, la confianza, el plan, los datos, la respuesta, el estado, los errores y el
contexto acotado de la conversación. No hay checkpointer: el grafo no reanuda
ejecuciones, pero el transcript sí se persiste con los endpoints de conversaciones.

## Persistencia y memoria

`POST /api/v1/chat` sigue siendo stateless. Para conservar el hilo se usan:

```text
POST   /api/v1/conversations
POST   /api/v1/conversations/{id}/messages
GET    /api/v1/conversations
GET    /api/v1/conversations/{id}
GET    /api/v1/conversations/{id}/messages
```

`PersistentChatService` bloquea la conversación (`SELECT ... FOR UPDATE`), asigna
`sequence`, carga el contexto, ejecuta el mismo grafo y guarda usuario y asistente en
una sola transacción. Cada respuesta del asistente conserva `intent`, `confidence`,
`status` y `query_plan`; el `data` de analítica no se duplica en la tabla.

La memoria es explícita y acotada:

- últimos **10 mensajes** y **4000 caracteres** (`ai/memory.py`);
- si el mensaje más reciente no cabe, se recorta; los antiguos se descartan;
- el último `QueryPlan` válido se usa para seguimientos deterministas como
  “¿Y en septiembre?” o “¿Y el CTR?”;
- las comparaciones no se infieren: requieren dos periodos explícitos;
- el `organization_id` de la conversación sale siempre de la API key.

El proveedor LLM recibe el contexto en
`LLMProvider.generate(..., context=LLMContext)`, con los mensajes y el último plan.

## Trazas y observabilidad

Cada petición recibe un `trace_id` UUID y devuelve la cabecera `X-Trace-ID`. El
servidor no confía en un identificador enviado por el cliente. `POST /api/v1/chat` y
`POST /api/v1/conversations/{id}/messages` aceptan `"debug": true`; en ese caso la
respuesta también incluye `trace`, construida con los updates reales de
`graph.astream(..., stream_mode="updates")`:

```text
1. classify_intent   intent, confianza, proveedor/modelo y motivo
2. propose_plan      plan propuesto o motivo de aclaración
3. validate_plan     aceptado o violaciones de JEV AI
4. execute_service   consulta real a PostgreSQL vía SQLAlchemy
5. generate_response respuesta desde plantilla
```

La traza operativa se persiste siempre, incluso sin `debug`:

- `traces`: estado, intención, error, duración y detalles acotados (`dry_run`,
  `message_chars`, `span_count`, `model_call_count`).
- `spans`: nodos del grafo, duración y detalle operativo.
- `model_calls`: proveedor, modelo, estado, latencia, tokens y coste estimado. En un
  turno normal hay una llamada `decision` de Jev y, si hay plan, una `generation` del
  LLM.

No se guardan prompts, mensajes ni respuestas completas. La telemetría se escribe en
una sesión independiente y es best-effort; si falla, se registra el error y la
respuesta del chat no cambia. En el chat persistente, la traza se guarda **después**
de confirmar el turno de negocio para no retener el bloqueo de la conversación.

`messages.trace_id` enlaza ambos mensajes del turno con su traza, sin FK para que un
fallo de telemetría no condicione la transacción. El coste se calcula con `Decimal`,
se etiqueta con `price_version` y es una estimación, no una factura. Solo se estima
`service_tier="standard"`; cualquier modelo o tier desconocido devuelve `null`.

La CLI lo muestra con `--debug` e imprime el `trace_id` de cada respuesta. Para
consultar lo persistido sin abrir `psql`:

```bash
docker compose run --rm backend python scripts/report.py --organization Demo
docker compose run --rm backend python scripts/report.py --trace <trace_id>
```

El reporte agrupa costes por proveedor/modelo/tipo y, con `--organization`, añade el
overview y las campañas con más gasto. Las llamadas sin tarifa conocida aparecen como
«sin precio», no como coste cero. No se añade un paso de caché porque el backend
no cachea resultados todavía; Redis está disponible en Compose pero no participa en
este flujo. Tampoco se exponen filas completas ni el `organization_id`.

## Catálogo cerrado

| Operación | Parámetros | Función |
|---|---|---|
| `top_ads_by_metric` | `metric`, `date_from`, `date_to`, `limit` | Mejores anuncios por métrica |
| `campaign_performance` | `campaign_id` o `campaign_name`, fechas | Métricas de una campaña |
| `compare_periods` | Dos rangos de fechas | Compara resúmenes |

Ejemplo:

```json
{
  "operation": "top_ads_by_metric",
  "metric": "roas",
  "date_from": "2026-10-01",
  "date_to": "2026-10-31",
  "limit": 5
}
```

El plan usa una unión discriminada de Pydantic con `extra="forbid"`. Si el LLM intenta
enviar `organization_id` o una operación fuera del catálogo, el plan no se parsea.

## Políticas JEV AI

Antes de ejecutar, `validate_query_plan` comprueba:

- La operación coincide con la intención clasificada.
- El rango no supera 366 días.
- `reach` y `frequency` no se usan para ordenar anuncios: no son aditivos entre días.
- El nombre de campaña no está vacío.
- El plan cumple el esquema (fechas ordenadas, límite entre 1 y 20, etc.).

La confianza del clasificador no concede permisos. El `organization_id` siempre sale
del contexto autenticado.

## Grafo y estado

| Nodo | Responsabilidad |
|---|---|
| `classify_intent` | Pregunta a Jev y guarda intención/confianza/proveedor |
| `help` / `clarify` / `error` | Cierran el flujo con el texto adecuado |
| `propose_plan` | Pide el plan al LLM y lo parsea con Pydantic |
| `validate_plan` | Aplica las políticas de JEV AI; corta en `dry_run` |
| `execute_service` | Ejecuta el plan con la sesión y la organización autenticada |
| `generate_response` | Redacta desde plantilla con los datos validados |

Las rutas condicionales están en `ChatNodes.route_after_*`. Los nodos no calculan
métricas ni permisos: delegan en los servicios existentes.

## Clasificación con Jev

`JevIntentClassifier` construye una pregunta `choice` con el catálogo cerrado de
intenciones y la envía a `DecisionProvider`. El resultado se valida antes de usarlo:
una opción fuera del catálogo o un error de Jev activa el `RuleBasedClassifier` como
fallback determinista. El motivo de la traza queda como `jev:proveedor:modelo` o
`jev_fallback:motivo:regla`.

Configuración:

| Variable | Uso |
|---|---|
| `JEV_PROVIDER` | `mock` (predeterminado) o `typesafe` |
| `TYPESAFE_API_KEY` | Obligatoria con `JEV_PROVIDER=typesafe` |
| `JEV_MODEL` | Modelo de Jev (`jev-1.13.0` por defecto) |
| `JEV_BASE_URL` | Raíz de TypeSafe |
| `JEV_TIMEOUT_SECONDS` | Timeout por intento |
| `JEV_MAX_RETRIES` | Reintentos para 429/529 |

`MockDecisionProvider` responde con las mismas reglas que `RuleBasedClassifier` para
las preguntas de intención. Sirve para desarrollo y tests; no estima la calidad de un
Jev real. `InstrumentedDecisionProvider` registra la llamada como `call_type="decision"`.

## Proveedores LLM

`LLMProvider` es la interfaz única y devuelve `LLMResult` (`content`, `usage`,
`service_tier`). `build_llm_provider(Settings)` elige la implementación al arrancar:

- `LLM_PROVIDER=mock` (predeterminado): `MockLLMProvider`, sin red ni API key.
- `LLM_PROVIDER=openai`: `OpenAICompatibleProvider`, que llama a
  `{LLM_BASE_URL}/chat/completions` con `LLM_API_KEY` y `LLM_MODEL`.

La app envuelve el proveedor con `InstrumentedLLMProvider`, que mide latencia y
registra tokens/coste sin alterar el resultado. `ChatService` y
`PersistentChatService` se construyen una vez y se exponen como dependencias de
FastAPI. Cambiar de proveedor no cambia el grafo ni los endpoints.

### Mock

`MockLLMProvider` implementa `LLMProvider` y puede:

- proponer un plan con el traductor determinista `build_plan_from_message`;
- devolver respuestas fijas por patrón (`MockResponse`);
- simular latencia (`delay`);
- lanzar `LLMConnectionError` o `LLMTimeoutError`.

El traductor reconoce meses en español, fechas ISO, rangos como “últimos 7 días”,
“este mes”, “mes pasado”, métricas (`ROAS`, `CPL`, `CTR`, etc.), límites y nombres de
campaña entre comillas o tras la palabra “campaña”.

Cuando recibe un `LLMContext`, el mock intenta primero el mensaje actual y, si no
produce plan, reutiliza el último plan válido para cambiar periodo o métrica. Es una
memoria determinista y limitada, no una comprensión semántica completa.

### OpenAI-compatible

`OpenAICompatibleProvider` envía el catálogo cerrado en el prompt del sistema y pide
`response_format={"type": "json_object"}` con temperatura 0. Devuelve el contenido tal
cual; `parse_query_plan` lo valida con Pydantic. Los errores HTTP, de red y de timeout
se traducen a `LLMError`, `LLMConnectionError` o `LLMTimeoutError`.

Configuración:

```bash
LLM_PROVIDER=openai
LLM_API_KEY=sk-...
LLM_MODEL=gpt-4o-mini
LLM_BASE_URL=https://api.openai.com/v1
LLM_TIMEOUT_SECONDS=30
```

Los tests no llaman a OpenAI: usan `httpx.MockTransport`. La respuesta final se sigue
generando con plantillas, no con texto libre del modelo.

## Datos de demo

```bash
docker compose run --rm backend python scripts/seed.py --organization "Demo"
docker compose run --rm backend python scripts/seed.py --organization "Demo" --reset
```

El seed es reproducible (semilla fija) y crea tres campañas, siete anuncios y métricas
diarias del 1 de septiembre al 13 de noviembre de 2026, incluyendo un ganador claro y
anuncios con mucho clic y poca conversión. No crea API keys.

## Cliente de terminal

```bash
JEV_API_KEY="jev_..." python scripts/chat_cli.py
JEV_API_KEY="jev_..." python scripts/chat_cli.py --message "Top 3 anuncios por ROAS"
JEV_API_KEY="jev_..." python scripts/chat_cli.py --show-plan
```

Escribe `salir` para terminar. `--dry-run` valida el plan sin ejecutarlo.

## Datasets

- [`mocks/datasets/query_plans.json`](../mocks/datasets/query_plans.json): mensajes,
  intención esperada y plan esperado. El test `tests/unit/test_mock_dataset.py`
  comprueba que clasificador, traductor y políticas sigan coincidiendo.
- [`mocks/datasets/intents.json`](../mocks/datasets/intents.json): 72 mensajes para
  medir accuracy, precision, recall y F1. Se ejecuta con
  `uv run python scripts/evaluate_classifier.py` y en CI.

Ver [`evaluation.md`](evaluation.md) para métricas, umbrales y limitaciones.

## Limitaciones actuales

- Sin checkpointer: el grafo no reanuda ejecuciones interrumpidas.
- La memoria es un contexto acotado; no hay resumen ni memoria semántica completa.
- Los seguimientos de comparación necesitan periodos explícitos.
- El proveedor real requiere API key, red y presupuesto; el mock sigue siendo el
  predeterminado.
- Las respuestas se generan con plantillas; el LLM solo propone el plan.
- `compare_periods` compara el resumen de la organización, no una campaña concreta.
