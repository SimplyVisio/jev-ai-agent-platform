# ADR 0004: observabilidad y coste de modelos en PostgreSQL

- Estado: aceptada
- Fecha: 2026-11-13

## Contexto

El chat ya tenía una traza de depuración construida con los updates reales de
LangGraph, pero solo se devolvía con `debug=true` y se perdía al terminar la petición.
No había forma de investigar un error por `trace_id`, medir latencia por nodo ni
estimar el coste de un proveedor real. Tampoco se quería introducir LangSmith u otra
plataforma externa antes de tener claro el volumen y la política de datos.

## Decisión

1. Generar un `trace_id` UUID4 en el servidor por petición; ignorar el que envíe el
   cliente. Propagar el id con contextvars y structlog, y devolverlo en `X-Trace-ID`.
2. Persistir en PostgreSQL `traces`, `spans` y `model_calls`, con `organization_id`
   desnormalizado, índices por organización/fecha y borrado en cascada.
3. Mantener `messages.trace_id` sin FK: el turno de negocio no debe depender de que la
   telemetría se escriba correctamente.
4. Escribir la telemetría en una sesión independiente y best-effort. Un fallo se
   registra como `trace_persist_failed` y no cambia la respuesta del chat.
5. En el chat persistente, persistir la traza **después** del commit del turno. Así se
   evita que el insert de la traza espere el `SELECT ... FOR UPDATE` de la conversación.
6. No guardar prompts, mensajes ni respuestas completas. Guardar solo detalles
   acotados (`dry_run`, `message_chars`, contadores y estado).
7. Usar `model_calls` en lugar de `llm_calls`: la tabla también registra modelos de
   decisión como Jev, que no son LLM generativos.
8. Normalizar `TokenUsage` y estimar el coste con `Decimal` y una versión de tarifas
   (`price_version`). No estimar modelos o niveles de servicio desconocidos.

## Consecuencias

- Un incidente se puede localizar desde el `trace_id` devuelto al cliente.
- La latencia por nodo, el estado y el coste estimado quedan disponibles sin depender
  de un servicio externo.
- La telemetría añade escrituras y conexiones; en chat persistente puede usar una
  segunda conexión por petición. Es aceptable para la fase actual y se revisará con
  volumen real.
- El coste es una estimación, no una factura. Los precios y los tiers deben revisarse
  cuando cambien los proveedores.
- No se pueden reconstruir conversaciones desde las trazas; el transcript sigue siendo
  la fuente de verdad.
- La retención y el particionado mensual quedan pendientes para producción.

## Alternativas descartadas

- LangSmith u otra plataforma externa: buena herramienta, pero añade dependencia,
  coste y salida de datos antes de conocer el volumen.
- Guardar prompts y respuestas completas: facilita depurar pero multiplica el riesgo
  de fuga de datos y el tamaño de la base.
- Reutilizar la sesión del turno para la telemetría: mezcla la transacción de negocio
  con una escritura best-effort y puede revertir el turno por un fallo de traza.
- Redis o Pub/Sub para la ingesta: Pub/Sub no es una cola fiable; si hace falta
  desacoplar, se usará Redis Streams o un worker con persistencia.
- Escribir la traza antes del commit en el chat persistente: provoca espera por la FK
  de `conversation_id` mientras la conversación está bloqueada.