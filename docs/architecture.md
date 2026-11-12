# Arquitectura

JEV AI es un **monolito modular vertical**: una sola aplicación y un solo dominio de
despliegue, con módulos separados por responsabilidad. Modular no significa un
contenedor por módulo; solo los procesos que corren de forma independiente (backend,
PostgreSQL, Redis, worker) tendrán su propio contenedor.

## Estructura destino

```text
src/jev_ai/
├── main.py
├── config.py
├── security.py             hashing de API keys
├── api/
│   ├── deps.py             sesión y autenticación
│   └── v1/endpoints/       HTTP, routers y dependencias de FastAPI
├── modules/                dominios de negocio deterministas
│   ├── organizations/      organizaciones y API keys
│   ├── marketing/          campañas, anuncios e insights (fase 4)
│   ├── analytics/          cálculo y exposición de métricas
│   └── conversations/      conversaciones, mensajes y contexto
├── ai/                     capa de IA (usa modules/, nunca al revés)
│   ├── jev/                clasificación y validación del motor JEV AI
│   ├── llm/                interfaz LLMProvider y proveedores
│   └── workflows/          orquestación con LangGraph
├── integrations/meta_ads/  transformación de datos externos (fase final)
└── infrastructure/         base de datos, Redis
```

Cada módulo crea solo las capas que necesita: `models.py`, `schemas.py`,
`repository.py` y `service.py`.

## Capas y responsabilidades

- **api:** HTTP, validación con Pydantic y dependencias de FastAPI.
- **service:** lógica de aplicación, reglas de negocio y cálculo de ratios.
- **repository:** acceso a datos con SQLAlchemy.
- **ai/jev:** clasificación de intenciones y validación de planes; independiente de
  LangGraph y FastAPI.
- **ai/llm:** interfaz `LLMProvider`, mock determinista y proveedor real futuro.
- **ai/workflows:** orquesta pasos y rutas; no contiene reglas de negocio.

## Reglas de dependencias

1. `modules/` nunca importa de `ai/`. Las métricas funcionan con el chatbot apagado.
2. `ai/` puede importar de `modules/`.
3. El chatbot no toca repositorios ni SQL: usa los mismos servicios que la API.
4. El LLM no genera SQL libre; propone un `QueryPlan` de un catálogo cerrado.
5. El `organization_id` sale del contexto autenticado, nunca del LLM.

La regla 1 se hará cumplir con `import-linter` cuando exista la capa de IA.

## Autenticación

La API usa API keys por organización en la cabecera `X-API-Key`. Cada clave se guarda
como hash SHA-256 en la tabla `api_keys`; el texto plano solo se muestra al crearla. La
dependencia de FastAPI resuelve la organización y la inyecta en los endpoints. Todas
las consultas de negocio filtran por ese `organization_id`.

## Modelo de datos

```text
organizations 1─N api_keys
organizations 1─N campaigns 1─N ads 1─N ad_insights   (fase 4)
```

`organizations` y `api_keys` ya existen. La migración inicial está en
`alembic/versions/`. En fase 4 se agrega el modelo de marketing.

`ad_insights` guardará una fila por anuncio y día, con `UNIQUE(ad_id, date)`, y solo
métricas base (impressions, reach, clicks, landing_page_views, spend, leads, sales,
revenue). Los ratios se calculan en `analytics/service.py`; nunca se almacenan ni se
promedian entre días.

## Principios de diseño

- Funcionalidad primero, abstracciones después.
- Lógica de negocio determinista y aislada de la IA.
- Nada de `float` para dinero: `NUMERIC` en PostgreSQL y `Decimal` en Python.
- Salidas del LLM validadas de forma determinista contra la base de datos.
- Una fase a la vez, con tests en verde y commit al cerrar.
