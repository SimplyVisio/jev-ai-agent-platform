# Evaluación del clasificador

El motor JEV AI no se valida con una cifra de confianza inventada: se mide contra un
dataset versionado y se ejecuta en CI. El objetivo es detectar regresiones cuando
cambian las reglas, el vocabulario o el futuro clasificador estadístico.

## Dataset

[`mocks/datasets/intents.json`](../mocks/datasets/intents.json) contiene 72 mensajes
con una única intención esperada del catálogo cerrado:

| Intención | Ejemplos |
|---|---|
| `top_ads_by_metric` | “Top 5 anuncios por ROAS”, “Ranking de ads por CPC” |
| `campaign_performance` | “¿Cómo va la campaña Demo?”, “Métricas de campaña” |
| `compare_periods` | “Compara este mes con el mes pasado”, “Octubre vs septiembre” |
| `help` | “Hola”, “¿Qué puedes hacer?”, “¿Cómo funciona el chatbot?” |
| `unknown` | “Dame un café”, “Elimina la campaña Demo” |

`unknown` incluye acciones no soportadas (crear, borrar, pausar, cambiar, exportar).
Así el clasificador no confunde una orden de escritura con una consulta de lectura.

## Métricas

`evaluate_classifier` calcula, por intención y en macro:

- **Accuracy**: aciertos sobre el total.
- **Precision**: de lo que predije como X, cuánto era X.
- **Recall**: de todo lo que era X, cuánto encontré.
- **F1**: media armónica de precision y recall.

También guarda la matriz de confusión y los casos fallidos con su confianza. La
matriz es más útil que accuracy sola: muestra qué intenciones se confunden entre sí.

## Ejecución

```bash
uv run python scripts/evaluate_classifier.py
uv run python scripts/evaluate_classifier.py --min-accuracy 0.95 --min-macro-f1 0.90
docker compose run --rm backend python scripts/evaluate_classifier.py
```

Umbrales por defecto en CI: accuracy ≥ 90% y macro F1 ≥ 85%. Si el clasificador baja
de ahí, el script sale con código 1 y el pipeline falla.

## Resultado actual

Con el dataset actual, el clasificador por reglas obtiene 100% de accuracy y macro F1.
Eso **no significa** que generalice a cualquier frase: el dataset está curado para el
vocabulario cerrado de las reglas y comparte sus términos. La métrica sirve para
detectar regresiones, no como estimación de producción.

## Limitaciones y siguientes pasos

- El dataset es pequeño y está escrito por la misma persona que las reglas; hay sesgo
  de confirmación.
- Los mensajes fuera del vocabulario caen en `unknown` y piden aclaración; eso es
  seguro, pero limita la cobertura.
- El siguiente paso es ampliar con mensajes reales anonimizados y comparar contra
  TF-IDF/embeddings con el mismo dataset y umbrales.
- La confianza del clasificador no otorga permisos: las políticas de JEV AI y el
  `organization_id` autenticado siguen siendo obligatorios.
