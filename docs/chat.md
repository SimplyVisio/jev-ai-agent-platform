# Chat offline y QueryPlan

El chat permite consultar campañas y anuncios en lenguaje natural sin proveedor LLM de
pago, sin API key externa y sin túnel. Todo el flujo es determinista y se puede probar
con pytest, Bruno o el cliente de terminal.

## Flujo

```text
START
  → classify_intent       RuleBasedClassifier (JEV AI)
  → route_request         help | clarify | plan
  → propose_plan          MockLLMProvider / plan_builder + parse_query_plan
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

Un futuro proveedor LLM recibe el contexto en
`LLMProvider.generate(..., context=LLMContext)`, con los mensajes y el último plan.

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

## Mock LLM

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

El endpoint usa `MockLLMProvider.default()` en `api/v1/endpoints/chat.py`. Cambiar a un
proveedor real solo requiere implementar `LLMProvider` e inyectarlo en `ChatService`.

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
- Sin proveedor LLM real.
- Las respuestas se generan con plantillas; el LLM solo propone el plan.
- `compare_periods` compara el resumen de la organización, no una campaña concreta.
