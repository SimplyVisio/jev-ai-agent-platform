# ADR 0005: cliente TypeSafe JEV y contrato de decisiones

- Estado: aceptada
- Fecha: 2026-11-14

## Contexto

JEV AI necesita un motor de decisiones medible para clasificar intenciones y validar
propuestas. TypeSafe expone `POST /v1/systemone`, que recibe un estado y preguntas
tipadas (`noul`, `choice`, `score`; `box` desde 1.14) y devuelve respuestas con
probabilidades. No es un
LLM de texto libre y no debe compartir la interfaz `LLMProvider`.

La documentación oficial actualizada (2026-11-14) confirma el endpoint, los límites de
32 MiB y 64 niveles, los reintentos para `429`/`529`, el timeout de referencia de 120 s
y `box` en Jev 1.14. Los SDKs oficiales existen, pero el proyecto mantiene `httpx` para
controlar transporte, reintentos y telemetría. El prefijo de la clave y la forma exacta
del JSON de error siguen sin confirmarse.

## Decisión

1. Crear `DecisionProvider` como puerto independiente de `LLMProvider`.
2. Modelar la petición y la respuesta con Pydantic, con unión discriminada por `type`
   para `noul`, `choice`, `score` y `box`; `legend` se tipa como mapa nivel → texto.
3. Fijar `jev-1.13.0` como modelo por defecto para reproducibilidad; permitir
   `jev-latest` o una versión explícita. `box` requiere 1.14+.
4. Implementar `TypeSafeJevProvider` con `httpx`, sin SDK, timeout de 120 s, transporte
   inyectable en tests y reintentos para `429`/`529` con backoff y `Retry-After`.
5. Validar localmente el body: 32 MiB, 64 niveles, números finitos y UTF-8 sin BOM.
6. Traducir timeout, red, HTTP y respuestas inválidas a errores de dominio. Conservar
   `x-typesafe-request-id` y `Retry-After` en `JevAPIError`.
7. Instrumentar las llamadas con `InstrumentedDecisionProvider`, usando
   `call_type="decision"` en `model_calls`.
8. Conectar Jev al nodo `classify_intent` mediante `JevIntentClassifier`, con
   `MockDecisionProvider` por defecto y `RuleBasedClassifier` como fallback. La
   evaluación de Jev real contra el dataset queda como siguiente paso.

## Consecuencias

- El cliente se puede probar sin red ni gastar tokens con `httpx.MockTransport`.
- El resto del sistema no depende de la forma concreta de TypeSafe.
- La clasificación por Jev es una implementación de `IntentClassifier`; el grafo no
  cambia y el fallback mantiene disponible el flujo si TypeSafe falla.
- `box` está en el contrato, pero `assets` y la cabecera de imágenes quedan fuera hasta
  que exista un caso de uso.
- Los reintentos viven en el cliente y cubren solo `429`/`529`; no se reintentan errores
  de validación ni de autenticación.
- El coste de Jev solo se estima para `jev-1.13.0`; versiones nuevas, incluida 1.14.0,
  devuelven `null` hasta registrar su tarifa.
- No se implementa compresión gzip/zstd aunque la API la acepte.

## Alternativas descartadas

- Reutilizar `LLMProvider`: mezcla generación de texto con decisiones estructuradas y
  rompe la separación entre interpretar y decidir.
- Enviar diccionarios sin Pydantic: no valida tipos, opciones ni probabilidades y
  traslada errores al flujo del chat.
- Integrar TypeSafe directamente en `ChatService`: acopla el grafo a un proveedor y
  dificulta sustituirlo o evaluarlo.
- Implementar ya `box` y `assets`: añade complejidad sin un caso de uso actual.