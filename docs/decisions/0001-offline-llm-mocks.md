# ADR 0001: mocks offline para el chat y QueryPlan

- Estado: aceptada
- Fecha: 2026-11-13

## Contexto

El desarrollo no dispone de una API key de un proveedor LLM ni de un túnel para
exponer el servicio. Aun así, necesitamos demostrar el flujo completo —lenguaje
natural, plan validado y consulta real a PostgreSQL— en tests, Bruno y una demo local.

## Decisión

1. `LLMProvider` es una interfaz abstracta y `MockLLMProvider` es la implementación
   por defecto.
2. El mock propone un `QueryPlan` con un traductor determinista de vocabulario cerrado.
   También puede devolver respuestas fijas y simular errores o latencia.
3. El chat es stateless: `POST /api/v1/chat` no crea conversaciones ni usa Redis.
4. JEV AI valida el plan con reglas deterministas antes de ejecutar.
5. La ejecución reutiliza los servicios de analytics y marketing; no hay SQL en la
   capa de IA.
6. La respuesta se genera con plantillas a partir de los datos validados.

## Consecuencias

- La demo y los tests no dependen de red, credenciales ni coste.
- El comportamiento es reproducible y fácil de evaluar.
- Añadir un proveedor real no cambia el contrato: solo se implementa `LLMProvider`.
- La calidad lingüística está limitada al vocabulario reconocido; los mensajes fuera
  del catálogo piden aclaración.
- La memoria conversacional y LangGraph se posponen.

## Alternativas descartadas

- Proveedor real con clave de desarrollo: bloquea el trabajo sin credenciales.
- Respuestas hardcodeadas por mensaje: no demuestran la ejecución real de consultas.
- SQL libre generado por el LLM: riesgo de fuga entre organizaciones y de consultas
  costosas; el catálogo cerrado es más seguro y verificable.
- Guardar conversaciones en Redis antes de tener el flujo estable: añade complejidad
  sin resolver el problema actual.
