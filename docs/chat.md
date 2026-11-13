# Chat offline y QueryPlan

El chat permite consultar campañas y anuncios en lenguaje natural sin proveedor LLM de
pago, sin API key externa y sin túnel. Todo el flujo es determinista y se puede probar
con pytest, Bruno o el cliente de terminal.

## Flujo

```text
mensaje
  → RuleBasedClassifier (JEV AI)
  → MockLLMProvider / plan_builder (propone QueryPlan)
  → parse_query_plan (Pydantic, catálogo cerrado)
  → validate_query_plan (JEV AI)
  → execute_query_plan (servicios de analytics y marketing)
  → render_reply (plantilla con datos reales)
```

`POST /api/v1/chat` no persiste conversaciones ni mensajes. La memoria, Redis y
LangGraph quedan para una fase posterior.

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

## Mock LLM

`MockLLMProvider` implementa `LLMProvider` y puede:

- proponer un plan con el traductor determinista `build_plan_from_message`;
- devolver respuestas fijas por patrón (`MockResponse`);
- simular latencia (`delay`);
- lanzar `LLMConnectionError` o `LLMTimeoutError`.

El traductor reconoce meses en español, fechas ISO, rangos como “últimos 7 días”,
“este mes”, “mes pasado”, métricas (`ROAS`, `CPL`, `CTR`, etc.), límites y nombres de
campaña entre comillas o tras la palabra “campaña”.

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

## Dataset de evaluación

[`mocks/datasets/query_plans.json`](../mocks/datasets/query_plans.json) contiene
mensajes, intención esperada y plan esperado. El test
`tests/unit/test_mock_dataset.py` comprueba que clasificador, traductor y políticas
sigan coincidiendo con el dataset.

## Limitaciones actuales

- Sin memoria de conversación ni tablas `conversations`/`messages`.
- Sin LangGraph: el flujo es una secuencia explícita en `ChatService`.
- Sin proveedor LLM real.
- Las respuestas se generan con plantillas; el LLM solo propone el plan.
- `compare_periods` compara el resumen de la organización, no una campaña concreta.
