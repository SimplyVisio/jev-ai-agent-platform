# AGENTS.md — JEV AI

Guía para el agente de IA (opencode) que acompaña el desarrollo de este proyecto. Resume TODAS las decisiones tomadas hasta ahora. Léelo completo al iniciar cada sesión y respétalo. Si una decisión debe cambiar, discútela con el usuario y registra el cambio en la sección "Registro de decisiones".

---

## 1. Cómo debes trabajar con el usuario

**Rol:** eres el guía técnico. El usuario (Santiago) implementa; tú orientas, explicas y revisas.

- Idioma: español. Respuestas breves y concisas, a menos que el usuario pida detalle.
- No entregues implementaciones enormes para copiar y pegar. Da piezas pequeñas, explica la responsabilidad de cada clase/función y por qué se usa ese patrón.
- Antes de implementar una funcionalidad, discute: qué problema resuelve, qué componentes participan y cómo se relacionan.
- Ante un error, primero analiza la causa y propón el diagnóstico; después cambia código.
- Usa documentación oficial cuando haya que profundizar y cítala.
- Sé crítico y honesto: señala sobreingeniería, riesgos y errores aunque el usuario no pregunte. No halagues por defecto.
- Cuando una decisión de arquitectura evolucione, revisa las anteriores y actualiza este archivo.
- Objetivo de aprendizaje triple: **cómo** se construye, **por qué** se construye así y **cómo se trabaja profesionalmente** (Git, tests, migraciones, documentación, CI).
- Al terminar cada fase el usuario debe poder explicar con sus palabras los conceptos clave (ej.: diferencia entre sesión y conexión, qué hace un Repository, cómo funcionan las transacciones y qué pasa si falla una a la mitad).

**Entorno del usuario:** Ubuntu, VS Code (con extensión de SQL, sin pgAdmin), Bruno para probar HTTP, Docker, Git. Base técnica autodidacta; está estudiando Ingeniería en IA y Análisis de Datos.

---

## 2. Qué es JEV AI

Plataforma backend de **inteligencia comercial y automatización de marketing**, pensada como **proyecto de portafolio** para puestos de Backend Developer, AI Automation Engineer y Data Engineer.

Dos capacidades centrales:

1. **Chatbot inteligente:** consulta en lenguaje natural de campañas, anuncios, resultados y métricas.
2. **API de analítica:** endpoints REST que alimentarán un dashboard frontend (el frontend se construirá en otro proyecto, después).

**"JEV AI" también es el nombre del motor de decisiones** (concepto del usuario): una capa independiente de los LLM tradicionales que clasifica intenciones, evalúa propuestas y valida salidas. Los LLM tradicionales interpretan lenguaje y redactan respuestas; JEV AI controla y valida.

Principio central:

> Primero construimos un backend de analítica que funcione y produzca resultados verificables. Después construimos una capa de IA que pueda consultar esos resultados de forma controlada. El proyecto debe demostrar valor aunque se elimine el chatbot.

---

## 3. Estado actual del repositorio

Fase 1 completada (2026-11-12): estructura base, tooling, CI y documentación inicial.

```
jev-ai/
├── .github/workflows/ci.yml   # ruff + pytest
├── .gitignore
├── .python-version            # 3.12
├── AGENTS.md
├── README.md
├── docs/architecture.md
├── pyproject.toml             # ruff, pytest y dev-dependencies
├── uv.lock
├── src/
│   └── jev_ai/
│       └── __init__.py
└── tests/{unit,integration,e2e}/
```

- Paquete raíz: `jev_ai` (importar como `from jev_ai.modules.analytics import ...`).
- Sin dependencias de runtime todavía; dev-dependencies: `ruff` y `pytest` (`pytest-asyncio` se añade cuando existan tests async).
- CI configurado en `.github/workflows/ci.yml`; todavía no hay remoto en GitHub.
- Flujo Git: `main` (commit inicial) ← `develop` ← `feature/*`.

### Decisión resuelta: subpaquete del motor
El subpaquete del motor de decisiones se llamará `src/jev_ai/ai/jev/` para evitar `jev_ai.ai.jev_ai`. Importación: `from jev_ai.ai.jev import ...`.

---

## 4. Reglas de oro (no negociables)

1. **Funcionalidad primero, abstracciones después.** No se agrega abstracción, patrón, servicio o tecnología sin identificar qué problema resuelve.
   - No crear clase abstracta si no hay que intercambiar implementaciones.
   - No crear Repository genérico si complica consultas específicas.
   - No usar Celery para lo que FastAPI resuelve bien.
   - No usar LangGraph para una consulta simple.
   - No usar Redis como sustituto de PostgreSQL.
   - No usar IA para cálculos deterministas.
2. **La lógica de negocio es determinista y está aislada de la IA.** La IA decide *qué* hacer; nunca garantiza reglas de negocio, permisos ni cálculos.
3. **Dependencias:** `ai/` puede usar `modules/`; `modules/` NUNCA importa de `ai/`. Las métricas deben funcionar con el chatbot apagado. Se hará cumplir con `import-linter`.
4. **El chatbot no toca repositorios ni SQL.** Llama a los mismos servicios de aplicación que usan los endpoints del dashboard (una sola fuente de cálculo).
5. **El LLM no genera SQL libre** (ver §8). Propone un `QueryPlan` estructurado de un catálogo cerrado.
6. **El `organization_id` nunca lo decide el LLM:** sale del contexto autenticado del servidor.
7. **Cada fase termina con:** código funcional + tests en verde + commit.
8. **Salidas del LLM se validan de forma determinista** (comparando contra datos de la BD), no solo con otro modelo.
9. **Nada de `float` para dinero:** `NUMERIC` en PostgreSQL y `Decimal` en Python.
10. **Una fase a la vez.** No instalar LangGraph, Celery ni dependencias de IA antes de llegar a su fase.

---

## 5. Arquitectura: monolito modular vertical

Una sola aplicación y un solo dominio de despliegue, con módulos separados por responsabilidad. **Modular no significa un contenedor por módulo.** Solo los procesos que corren independientemente (backend, postgres, redis, worker de Celery) tienen contenedor propio, todos en la misma red de Docker Compose.

Cada módulo tiene solo las capas que realmente necesita (nada de carpetas globales `domain/` y `application/` duplicadas).

### Estructura destino (no crear todo desde el día uno)

```
src/jev_ai/
├── main.py
├── config.py                      # pydantic-settings
├── api/
│   └── v1/
│       ├── router.py
│       └── endpoints/
│           ├── health.py
│           ├── conversations.py
│           ├── campaigns.py
│           ├── ads.py
│           └── analytics.py
├── modules/                       # dominios de negocio (deterministas)
│   ├── marketing/                 # campañas, anuncios, insights
│   │   ├── models.py
│   │   ├── schemas.py
│   │   ├── repository.py
│   │   └── service.py
│   ├── analytics/                 # cálculo y exposición de métricas
│   │   ├── schemas.py
│   │   ├── repository.py
│   │   └── service.py
│   └── conversations/             # conversaciones, mensajes, contexto
├── ai/                            # capa de IA (usa modules/, nunca al revés)
│   ├── jev/                       # clasificador, políticas, validadores
│   ├── llm/                       # interfaces, providers (mock primero), service
│   └── workflows/                 # LangGraph: states, nodes, graphs
├── integrations/
│   └── meta_ads/                  # solo al final; transforma respuestas de Meta al modelo interno
├── infrastructure/
│   ├── database/                  # base, session, migraciones
│   └── redis/
└── workers/                       # Celery (fase opcional)

tests/{unit,integration,e2e}/
mocks/{datasets,fixtures}/         # solo datasets y fixtures; MockLLMProvider vive en el código de la app
alembic/
scripts/seed.py                    # datos sintéticos reproducibles
docs/{architecture.md,metrics.md,decisions/}
.github/workflows/ci.yml
compose.yaml  Dockerfile  .env.example  .dockerignore
```

### Responsabilidades por capa
- **api:** HTTP, routers, dependencias de FastAPI, validación con Pydantic.
- **service:** lógica de aplicación y reglas de negocio (aquí se calculan los ratios).
- **repository:** acceso a datos con SQLAlchemy; ningún modelo de IA lo toca directamente.
- **ai/jev:** clasificación y validación; independiente de LangGraph y de FastAPI.
- **ai/llm:** interfaz `LLMProvider` + `MockLLMProvider` (respuestas deterministas, errores, timeouts, lentitud, estructuradas) + proveedor real futuro.
- **ai/workflows:** orquesta pasos; NO contiene reglas de negocio.

---

## 6. Modelo de datos inicial (4 tablas)

```
organizations 1─N campaigns 1─N ads 1─N ad_insights
```

- **organizations:** empresa cliente. Incluye `currency_code` (una moneda por organización en v1; luego se moverá a `ad_accounts`).
- **campaigns:** campañas de una organización.
- **ads:** anuncios de una campaña.
- **ad_insights:** métricas históricas. **Una fila por anuncio por día**, con `UNIQUE(ad_id, date)`.
- Desnormalizar `organization_id` también en `ads` y `ad_insights`, con índice `(organization_id, date)`, para filtrar por organización sin joins y reducir riesgo de fuga de datos entre clientes.
- No sobrescribir métricas: se guardan registros históricos por periodo (snapshots), para comparar semana actual vs. anterior.

### Campos base de `ad_insights`
| Campo | Tipo |
|---|---|
| impressions | BIGINT |
| reach | BIGINT |
| clicks | BIGINT |
| landing_page_views | BIGINT |
| spend | NUMERIC |
| leads | BIGINT |
| sales | BIGINT |
| revenue | NUMERIC |

**Solo se guardan métricas base.** Los ratios NO se almacenan.

### Tablas futuras (solo cuando se necesiten)
`ad_sets`, `ad_accounts`, `landing_pages`, `landing_events`, `conversations`, `messages`, `users`, `organization_members`.

### Autenticación inicial
API keys asociadas a una organización. Mostrar la clave una sola vez al crearla, guardar su **hash SHA-256** (nunca en texto plano) y compararla con `hmac.compare_digest`. Después se agregarán usuarios y roles. Toda consulta (API y chatbot) filtra por el `organization_id` del token. Debe existir un test que pruebe que una organización no puede ver datos de otra.

---

## 7. Métricas y fórmulas

Se calculan en `analytics/service.py` y se documentan en `docs/metrics.md`.

| Indicador | Fórmula |
|---|---|
| Frequency | impressions / reach |
| CTR | clicks / impressions × 100 |
| CPC | spend / clicks |
| CPM | spend / impressions × 1000 |
| CPL | spend / leads |
| Conversion Rate | leads / landing_page_views × 100 |
| ROAS | revenue / spend |
| ROI | (profit − spend) / spend × 100 |

Reglas:
- Denominador cero → devolver `None` / "no disponible" según el contrato de la API; nunca dividir por cero.
- Para periodos o agregaciones: **sumar primero las métricas base y después calcular el ratio.** Jamás promediar ratios diarios (ej. no promediar CTR diarios).
- **`reach` no es sumable entre días** (son personas únicas): sumarlo sobreestima y rompe Frequency. Calcular frecuencia por día o guardar reach a nivel de periodo si la fuente lo entrega así. Documentarlo.
- **ROAS ≠ ROI.** ROI real requiere beneficio/costos reales, no solo ingresos atribuidos. Dejar ROI fuera del MVP (exponer ROAS), o agregar un campo opcional de costo de producto. Mejor omitir un indicador que mostrar uno engañoso.
- Distinguir visitas registradas por Meta de eventos recolectados en nuestra propia landing.
- Tests obligatorios de casos límite (CTR con 0 impresiones, ROAS con 0 gasto, agregación correcta, etc.).

### Métricas por grupo (contexto de negocio)
- **Anuncios:** Impressions, Reach, Frequency, Clicks, CTR, CPC, CPM, Amount Spent.
- **Landing pages:** Landing Page Views, Sessions, Bounce Rate, Conversion Rate, Leads.
- **Comercial:** Leads, Qualified Leads, Sales, Revenue, CPA, ROAS, ROI.

---

## 8. Capa de IA

### 8.1 Roles
| Componente | Responsabilidad | Naturaleza |
|---|---|---|
| Lógica de negocio / Analytics | Reglas, permisos, cálculos | Determinista |
| JEV AI | Clasificar intenciones, validar propuestas y salidas | Probabilístico + reglas |
| LLM tradicional | Interpretar lenguaje, proponer QueryPlan, redactar respuestas | Probabilístico |
| LangGraph | Orquestar pasos, estado, rutas condicionales | Máquina de estados |
| MCP (opcional, al final) | Exponer herramientas a los modelos | Protocolo |

Regla práctica de cuándo usar IA: sí para identificar qué quiere el usuario, generar un QueryPlan desde lenguaje natural y redactar explicaciones; no para validar permisos, calcular métricas, ejecutar consultas ni guardar resultados.

### 8.2 JEV AI como clasificador medible
- Interfaz `IntentClassifier(ABC)` con `async classify(message) -> IntentResult`.
- Empezar con `RuleBasedClassifier` (keywords/patrones). Después experimentar con TF-IDF, embeddings, similitud coseno, clasificadores híbridos.
- **Catálogo cerrado de intenciones** (el clasificador no puede inventar operaciones).
- Dataset de prueba versionado en `mocks/datasets/` (mensaje → intención esperada). Medir accuracy, precision, recall y F1; correr la evaluación en CI para detectar regresiones.
- Política de confianza inicial (a calibrar con datos): ≥ 0.90 acepta; 0.70–0.89 pide validación adicional; < 0.70 pide aclaración. La confianza **no** equivale a permiso.
- Pregunta abierta para más adelante: si JEV AI será un modelo propio, un clasificador estadístico o un sistema híbrido. La interfaz debe permitir intercambiar implementaciones.

### 8.3 QueryPlan y catálogo cerrado de operaciones
El LLM **no genera SQL libre**. Produce un `QueryPlan` validado con Pydantic. Operaciones iniciales:

| Operación | Función |
|---|---|
| `top_ads_by_metric` | Mejores anuncios según una métrica |
| `campaign_performance` | Resultados de una campaña |
| `compare_periods` | Comparar dos periodos |

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

JEV AI valida: operación existente, métrica permitida, fechas válidas, límite dentro del rango, y que la organización corresponda al usuario autenticado. Luego Analytics ejecuta la operación vía servicios y SQLAlchemy construye la consulta.

Generación de SQL libre solo como experimento posterior, con `sqlglot`, usuario de solo lectura, allowlist de tablas/columnas, límites de filas y timeout.

### 8.4 Flujo del chatbot
```
Usuario → FastAPI → Pydantic → JEV AI (clasificación)
  → LangGraph → LLM (propone QueryPlan) → JEV AI (valida plan)
  → Analytics Service → SQLAlchemy → PostgreSQL → resultados estructurados
  → LLM (genera respuesta) → validación determinista del output → Usuario
```

Validación de la respuesta: pedir respuesta estructurada (Pydantic) y comparar de forma determinista nombres, cantidades e identificadores contra el resultado de la BD. Alternativa más segura: generar el texto desde plantilla y usar el LLM solo para redactar. No depender únicamente de otro LLM para verificar.

### 8.5 LangGraph
- Primer grafo mínimo: `classify_intent → route_request → execute_service → generate_response`.
- Estado tipado (`TypedDict`) con: user/organization/conversation ids, mensaje original, intent y confianza, query plan, resultado de BD, respuesta generada, validaciones, status y errores.
- Cada nodo actualiza solo lo que le corresponde. Aprender luego: conditional edges, nodos paralelos, reintentos, checkpointing, human-in-the-loop.
- LangGraph orquesta; no contiene reglas de negocio.

### 8.6 MockLLM
Los LLM de pago no se usan durante el desarrollo. `LLMProvider(ABC)` con `async generate(prompt) -> str`; implementaciones: `MockLLMProvider` (determinista) y proveedor real futuro. El mock debe poder simular respuestas correctas, inválidas, estructuradas, errores de conexión, timeouts y lentitud.

---

## 9. Datos sintéticos (componente de primera clase)

`scripts/seed.py` con **semilla fija** para datos reproducibles. Debe incluir: varias organizaciones, campañas con distintos objetivos, anuncios con distintos presupuestos, tendencias de crecimiento/declive, variación por día de la semana, estacionalidad, **un anuncio claramente ganador**, anuncios con muchos clics y pocas conversiones, y campañas con gasto alto y bajo rendimiento. Permite demos y tests de IA reproducibles. No conectar Meta Ads real hasta el final.

---

## 10. API REST (pensada para un dashboard futuro)

Versionada bajo `/api/v1`. Paginación, filtros y excepciones HTTP consistentes.

| Endpoint | Función |
|---|---|
| `GET /health` | Estado del servicio |
| `GET /campaigns`, `GET /campaigns/{id}` | Listar / consultar campañas |
| `GET /ads` | Listar anuncios |
| `GET /analytics/overview` | Resumen general |
| `GET /analytics/campaigns` | Rendimiento por campaña |
| `GET /analytics/ads` | Rendimiento por anuncio |
| `GET /analytics/trends` | Evolución por periodo |
| `POST /conversations` | Crear conversación |
| `POST /conversations/{id}/messages` | Enviar mensaje al chatbot |

---

## 11. Async y Celery (cuando lleguen)

- App: `async def` en endpoints, SQLAlchemy `AsyncSession` + `asyncpg`, `httpx.AsyncClient` para APIs externas.
- Async no acelera trabajo de CPU. No ejecutar tareas largas dentro de un endpoint HTTP.
- Celery usa procesos (pool `prefork`), no hilos. Su interfaz de tareas es síncrona: separar la entrada del worker de los casos de uso asíncronos y manejar con cuidado el event loop y las conexiones de SQLAlchemy entre procesos.
- Redis: broker/caché/buffer; **nunca única fuente de verdad**.
- Antes de Celery: observabilidad básica (`request_id` por petición propagado a logs y tareas, logs estructurados con `structlog`).

### Idea opcional: batching de conversaciones con Redis
Agrupar mensajes consecutivos de un usuario (ej. 5 mensajes en pocos segundos) en un solo lote antes de ejecutar un workflow: buffer en Redis (Lists o Streams) con clave tipo `conversation:{id}:messages`, TTL, debounce de 2–5 s, límite de mensajes por lote, orden preservado, idempotencia, control de concurrencia por conversación, y persistencia de mensajes importantes en PostgreSQL (posible patrón Inbox/Outbox). Distinguir *Conversation Buffer* (agrupar entrantes) de *Conversation Memory* (contexto previo). Solo en la fase opcional.

---

## 12. Stack

| Tecnología | Uso |
|---|---|
| Python 3.12 | Lenguaje |
| uv | Paquetes y entornos |
| FastAPI + Uvicorn | API REST (ASGI) |
| Pydantic + pydantic-settings | Validación, tipado, configuración |
| SQLAlchemy 2.x + asyncpg | ORM async |
| Alembic | Migraciones |
| PostgreSQL | Persistencia |
| Redis | Caché / broker (fase opcional) |
| Celery | Tareas en segundo plano (opcional) |
| LangGraph | Workflows (fase 9) |
| pytest + pytest-asyncio + HTTPX | Testing |
| testcontainers | Integración con infraestructura real |
| Faker | Datos ficticios |
| structlog | Logging estructurado |
| Ruff | Lint y formato |
| import-linter | Hacer cumplir reglas de dependencias |
| sqlglot | Solo para experimentos futuros de SQL generado |
| Bruno | Cliente HTTP |
| Docker / Docker Compose | Contenedores |
| GitHub Actions | CI (ruff + pytest desde la fase 1) |

---

## 13. Entorno de desarrollo

Híbrido: **Python local con `uv`** (depuración sencilla en VS Code) + **Docker Compose para PostgreSQL y Redis**. Más adelante se agregan backend y worker a Compose. Contenedores finales: `backend`, `postgres`, `redis`, `celery_worker` en una misma red privada. Variables de entorno en `.env` (nunca commiteado) con `.env.example` versionado.

---

## 14. Git y metodología

- Trabajar con Git desde el día uno; nada se desarrolla directo en `main`.
- Ramas: `main` ← `develop` ← `feature/*` (ej. `feature/initial-architecture`, `feature/database-setup`, `feature/analytics-api`).
- Commits semánticos: `feat:`, `fix:`, `test:`, `docs:`, `chore:`, `refactor:`.
- Pull requests aunque se trabaje solo; tags de versión; `.gitignore` y secretos fuera del repo.
- Cada fase cierra con: código funcional + tests en verde + commit.

---

## 15. Roadmap

### Hito 1 — Backend de analítica (demostrable sin IA)
| Fase | Objetivo |
|---|---|
| 1 | Entorno, Git, uv, estructura mínima, `pyproject.toml`, CI (ruff + pytest), documentación inicial |
| 2 | Docker Compose, PostgreSQL y Redis |
| 3 | FastAPI, Pydantic y autenticación por organización (API keys) |
| 4 | SQLAlchemy async, Alembic y modelo de marketing |
| 5 | CRUD de campañas y anuncios |
| 6 | Analytics API, métricas y tests |

### Hito 2 — Inteligencia artificial
| Fase | Objetivo |
|---|---|
| 7 | Interfaces, MockLLM y datasets |
| 8 | Clasificador JEV AI y evaluación (accuracy/F1) |
| 9 | LangGraph y chatbot funcional |
| 10 | QueryPlan, validación y comprobación determinista de respuestas |

### Extensiones opcionales
Celery + Redis (sincronizaciones y procesos de fondo), batching de conversaciones, integración real con Meta Ads, MCP, observabilidad avanzada, despliegue. Las fases 1–10 ya forman un proyecto sólido para entrevistas.

### Fase 1 — checklist inmediata
- [x] Crear directorio `jev-ai` y `git init`
- [x] `uv init` (layout `src/`, Python 3.12)
- [x] Completar `pyproject.toml` (descripción, ruff, pytest, dependencias de desarrollo)
- [x] Crear estructura mínima de carpetas (`tests/`, `docs/`, etc.)
- [x] Crear `ci.yml` (ruff + pytest) y un primer test trivial en verde
- [x] README inicial y `docs/architecture.md`
- [x] Primer commit (`feat: initialize project`) y rama `develop`
- No instalar LangGraph, Celery ni dependencias de IA todavía.

---

## 16. Entregables de portafolio (objetivo final)

1. README: propósito, arquitectura, tecnologías, cómo ejecutarlo.
2. Diagrama de arquitectura (API, analytics, IA, BD).
3. `docs/metrics.md`: fórmulas y definiciones.
4. ADRs en `docs/decisions/` (3–4 decisiones clave).
5. Tests: cálculos, aislamiento entre organizaciones y validación de respuestas.
6. Demo: `docker compose up` con datos sintéticos reproducibles.
7. Video corto: una consulta al chatbot y sus resultados, más los endpoints del dashboard.

---

## 17. Registro de decisiones (resumen histórico)

Evolución del proyecto, para no repetir debates:

1. **Origen:** ejercicio de práctica con inventario (productos, repisas, sillas) y un motor genérico de workflows con chatbot.
2. **Monolito modular, no contenedor por módulo.** Contenedores separados solo para procesos independientes.
3. **Estructura simplificada:** se eliminaron capas globales `domain/` y `application/` duplicadas; cada módulo tiene sus propias capas. Se separó `ai/` de `modules/`.
4. **LLM no genera SQL libre** → `QueryPlan` estructurado con catálogo cerrado. SQL generado queda como experimento posterior con `sqlglot`, usuario solo lectura y allowlist.
5. **Validación de salida del LLM:** determinista contra datos de la BD (no solo con otro modelo).
6. **JEV AI** debe ser un clasificador **medible** (empezar con reglas, dataset y métricas), no una caja negra con "95% de confianza" sin evaluar.
7. **MCP** pospuesto al final (aporta complejidad de protocolo sin enseñar tanto si ya se controlan los servicios).
8. **Redis batching y Celery** pospuestos a fases opcionales.
9. **Cambio de dominio:** de inventario a **inteligencia comercial/marketing** (campañas y anuncios estilo Meta Ads) por valor de portafolio. Inventario ya no es el dominio.
10. **Modelo de datos reducido a 4 tablas** (organizations, campaigns, ads, ad_insights); auth con API keys por organización.
11. **Datos sintéticos primero;** Meta Ads real solo al final. **Sin frontend** por ahora.
12. **Roadmap reducido a dos hitos** (analítica sin IA, luego IA), con extensiones opcionales.
13. **Herramientas:** `uv`, `pytest-asyncio`, `testcontainers`, `structlog`, `ruff`, `import-linter`, CI desde la fase 1.
14. **Layout real del repo:** `src/jev_ai/` con `uv_build` (en lugar de `app/`).
15. **Subpaquete del motor (2026-11-12):** `src/jev_ai/ai/jev/`, confirmado con el usuario; evita la colisión `jev_ai.ai.jev_ai`.

Cuando se tome una decisión nueva, agrégala aquí con fecha.
