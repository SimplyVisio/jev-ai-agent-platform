# Chat y QueryPlan

El chat permite consultar campañas y anuncios en lenguaje natural. Por defecto usa un
proveedor mock determinista, sin API key externa ni coste; también admite un proveedor
OpenAI-compatible configurado por entorno. La ejecución, las políticas y las respuestas
siguen siendo deterministas: el LLM solo propone el plan.

## Flujo

```text
START
  → classify_intent       RuleBasedClassifier (JEV AI)
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

## Traza para depuración

`POST /api/v1/chat` y `POST /api/v1/conversations/{id}/messages` aceptan
`"debug": true`. La respuesta incluye `trace`, construida con los updates reales de
`graph.astream(..., stream_mode="updates")`:

```text
1. classify_intent   intent, confianza y regla
2. propose_plan      plan propuesto o motivo de aclaración
3. validate_plan     aceptado o violaciones de JEV AI
4. execute_service   consulta real a PostgreSQL vía SQLAlchemy
5. generate_response respuesta desde plantilla
```

La CLI lo muestra con `--debug`. No se añade un paso de caché porque el backend no
cachea resultados todavía; Redis está disponible en Compose pero no participa en este
flujo. Tampoco se exponen filas completas ni el `organization_id`.

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
| `classify_intent` | Clasifica el mensaje y guarda intención/confianza |
| `help` / `clarify` / `error` | Cierran el flujo con el texto adecuado |
| `propose_plan` | Pide el plan al LLM y lo parsea con Pydantic |
| `validate_plan` | Aplica las políticas de JEV AI; corta en `dry_run` |
| `execute_service` | Ejecuta el plan con la sesión y la organización autenticada |
| `generate_response` | Redacta desde plantilla con los datos validados |

Las rutas condicionales están en `ChatNodes.route_after_*`. Los nodos no calculan
métricas ni permisos: delegan en los servicios existentes.

## Proveedores LLM

`LLMProvider` es la interfaz única. `build_llm_provider(Settings)` elige la
implementación al arrancar la aplicación:

- `LLM_PROVIDER=mock` (predeterminado): `MockLLMProvider`, sin red ni API key.
- `LLM_PROVIDER=openai`: `OpenAICompatibleProvider`, que llama a
  `{LLM_BASE_URL}/chat/completions` con `LLM_API_KEY` y `LLM_MODEL`.

La app construye `ChatService` y `PersistentChatService` una vez y los expone como
dependencias de FastAPI. Cambiar de proveedor no cambia el grafo ni los endpoints.

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
