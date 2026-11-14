# ADR 0003: proveedor LLM real OpenAI-compatible

- Estado: aceptada
- Fecha: 2026-11-13

## Contexto

El hito 2 quedó funcional con `MockLLMProvider`, pero faltaba comprobar el flujo con un
modelo real. El LLM solo debe proponer un `QueryPlan`; la validación, la ejecución y
la redacción final siguen siendo deterministas y no dependen de él. Tampoco queremos
introducir una dependencia pesada ni llamadas pagadas en CI.

## Decisión

1. Añadir `OpenAICompatibleProvider`, un cliente HTTP mínimo con `httpx`, sin SDK.
2. Seleccionar el proveedor con `LLM_PROVIDER`: `mock` por defecto, `openai` opcional.
3. Configurar `LLM_API_KEY`, `LLM_MODEL`, `LLM_BASE_URL` y `LLM_TIMEOUT_SECONDS`.
4. Pedir JSON con `response_format={"type": "json_object"}` y temperatura 0. El
   contenido se valida con `parse_query_plan`; el modelo no ejecuta nada.
5. Traducir timeout, red, HTTP y respuestas malformadas a errores de dominio.
6. Inyectar el proveedor una vez en `create_app`; `ChatService` y
   `PersistentChatService` se guardan en `app.state` y se exponen como dependencias.
7. Los tests usan `httpx.MockTransport`; CI nunca llama a un proveedor externo.
8. Mantener las respuestas por plantilla. No se pide al modelo que redacte cifras.
9. No agregar checkpointer en esta fase.

## Consecuencias

- El flujo completo se puede probar con un modelo real sin cambiar endpoints ni grafo.
- El mock sigue siendo el camino reproducible de tests, demos y desarrollo offline.
- Si `LLM_PROVIDER=openai` y falta la clave, la app falla al arrancar: no hay fallback
  silencioso que oculte una configuración incompleta.
- El proveedor real añade latencia, coste y disponibilidad externa; el mock no.
- La calidad del plan depende del prompt y del modelo, pero JEV AI rechaza cualquier
  plan fuera del catálogo o de las políticas.
- La respuesta final sigue sin poder inventar cifras porque se renderiza desde datos
  ya calculados.
- Sin checkpointer no se reanudan ejecuciones interrumpidas; el transcript ya se
  persiste en PostgreSQL.

## Alternativas descartadas

- SDK oficial de OpenAI: añade dependencia y superficie para un único endpoint; el
  cliente HTTP permite además bases compatibles.
- Usar el LLM para redactar la respuesta final: obligaría a validar texto libre contra
  la base y aumentaría el riesgo de cifras inventadas.
- Fallback automático a mock ante error del proveedor: ocultaría fallos de
  configuración y mezclaría resultados simulados con datos reales.
- Checkpointer para cerrar el hito: duplica la persistencia actual y no hay
  human-in-the-loop ni reanudación de ejecuciones.