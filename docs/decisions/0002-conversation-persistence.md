# ADR 0002: persistencia y memoria acotada de conversaciones

- Estado: aceptada
- Fecha: 2026-11-13

## Contexto

`POST /api/v1/chat` era stateless. Para un dashboard y para auditar el comportamiento
del motor hacía falta guardar los turnos, sin convertir el chat en una caja negra ni
duplicar los datos de analítica. Además, el usuario pidió memoria basada en los
últimos mensajes.

## Decisión

1. Añadir `conversations` y `messages`, ambas con `organization_id`.
2. Mantener `/chat` stateless y crear endpoints explícitos bajo `/conversations`.
3. `sequence` es monotónica por conversación; la conversación se bloquea con
   `SELECT ... FOR UPDATE` antes de calcularla. Usuario y asistente se confirman en una
   sola transacción.
4. Guardar en el mensaje del asistente `intent`, `confidence`, `status` y `query_plan`.
   No guardar el `data` de analítica: se reproduce desde el plan.
5. Autogenerar el título con el primer mensaje si no se envió uno.
6. La memoria es un contexto acotado: últimos 10 mensajes y 4000 caracteres. Se
   conservan los más recientes y se recortan los antiguos.
7. El mock resuelve seguimientos de periodo o métrica reutilizando el último plan
   válido. Las comparaciones requieren periodos explícitos.
8. `LLMProvider.generate` acepta un `LLMContext` opcional; los proveedores reales
   podrán incorporar el historial al prompt.

## Consecuencias

- El transcript queda ordenado y aislado por organización; un id ajeno devuelve `404`.
- La conversación se puede reconstruir desde los mensajes y planes guardados.
- La memoria tiene un coste predecible y no crece con el hilo.
- Los seguimientos que no son de periodo/métrica pueden requerir aclaración.
- Sigue sin haber checkpointer ni reanudación de grafos; Redis no es necesario.
- El `data` no se conserva, así que una respuesta histórica se reproduce ejecutando
  su plan contra la base actual.

## Alternativas descartadas

- Persistir todo en `/chat` con un `conversation_id` opcional: dos caminos para la
  misma operación y ambigüedad sobre cuándo se crea el hilo.
- Guardar el resultado completo de analítica en cada mensaje: duplica datos y crece
  rápido; el plan ya es la fuente reproducible.
- Memoria sin límite: coste y latencia impredecibles, además de riesgo de arrastrar
  contexto irrelevante.
- Ordenar solo por `created_at`: dos mensajes de la misma transacción pueden compartir
  timestamp; `sequence` es estable.
- Redis para el historial: PostgreSQL ya es la fuente de verdad y el volumen actual no
  justifica otra infraestructura.
