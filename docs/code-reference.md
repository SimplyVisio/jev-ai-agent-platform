# Referencia de código

Este documento describe las funciones, clases y contratos del backend. El código usa
docstrings en español; esta referencia explica cómo encajan las piezas y qué
responsabilidad tiene cada una. Se actualiza al cerrar cada fase.

## Mapa de módulos

| Ruta | Responsabilidad |
|---|---|
| `jev_ai/main.py` | Construye la app y gestiona el ciclo de vida del engine |
| `jev_ai/config.py` | Configuración tipada desde entorno y `.env` |
| `jev_ai/security.py` | Hashing de API keys |
| `jev_ai/api/deps.py` | Sesión de BD y autenticación por API key |
| `jev_ai/api/v1/endpoints/` | Endpoints HTTP |
| `jev_ai/modules/organizations/` | Entidades y consultas de organizaciones |
| `jev_ai/ai/jev/` | Intenciones, QueryPlan, clasificador y políticas |
| `jev_ai/ai/llm/` | `LLMProvider`, mock y traductor offline |
| `jev_ai/ai/chat.py` | Orquestación del flujo de chat |
| `jev_ai/infrastructure/database/` | Base declarativa, engine y sesiones |
| `scripts/create_api_key.py` | Procedimiento de alta de organización y clave |
| `scripts/seed.py` | Datos sintéticos reproducibles |
| `scripts/chat_cli.py` | Cliente de chat por terminal |

## Configuración

### `Settings`

Clase Pydantic que valida la configuración al arrancar. Campos:

| Campo | Origen | Uso |
|---|---|---|
| `app_name` | `APP_NAME` | Título de OpenAPI |
| `database_url` | `DATABASE_URL` | DSN async de SQLAlchemy |

`Settings` no acepta campos extra (`extra="ignore"` descarta las variables de Compose
que no le incumben).

### `get_settings()`

Devuelve una instancia cacheada con `lru_cache`. Evita releer el entorno en cada
petición. Los tests no deben modificarla: inyectan `Settings` en `create_app`.

## Seguridad

### `hash_api_key(api_key)`

Calcula SHA-256 y devuelve 64 caracteres hexadecimales. Es la única transformación
que sufre la clave antes de persistirse. El texto plano nunca se guarda ni se registra.

## Persistencia

### `Base`

Clase declarativa de SQLAlchemy 2.x. Centraliza los metadatos que Alembic usa para
autogenerar migraciones.

### `create_database_engine(database_url)`

Crea un `AsyncEngine` con `pool_pre_ping=True`. No abre conexiones hasta la primera
consulta. El engine se construye en el lifespan y se libera con `dispose()`.

### `create_session_factory(engine)`

Devuelve un `async_sessionmaker[AsyncSession]` con `expire_on_commit=False`, para que
las entidades sigan disponibles después de un commit sin consultas implícitas.

### `Organization` (modelo ORM)

Representa a la empresa cliente. Campos: `id` (UUID), `name`, `currency_code` y
`created_at`. Relación uno-a-muchos con `ApiKey` y borrado en cascada.

### `ApiKey` (modelo ORM)

Credencial de una organización. Campos: `id`, `organization_id`, `key_hash` y
`created_at`. `key_hash` es único. No existe columna para la clave en texto plano.

### `find_api_key_by_hash(session, key_hash)`

Consulta la entidad `ApiKey` por hash. Devuelve `None` si no existe. La verificación en
tiempo constante (`hmac.compare_digest`) se hace en la capa HTTP, no en el repositorio.

## Modelo de marketing

Vive en `modules/marketing/models.py`. Solo métricas base; los ratios se calculan en
analytics.

### Enums de vocabulario

`CampaignObjective`, `CampaignStatus` y `AdStatus` son `StrEnum`. Las columnas son
`VARCHAR`, así que PostgreSQL no valida el catálogo; lo harán los schemas de la fase 5.

### `Campaign`

Campaña de una organización: `id`, `organization_id`, `name`, `objective`, `status`
(por defecto `active`) y `created_at`. Relación uno-a-muchos con `Ad`, borrado en
cascada.

### `Ad`

Anuncio de una campaña: `id`, `campaign_id`, `organization_id` desnormalizado, `name`,
`status` y `created_at`. Relación uno-a-muchos con `AdInsight`, borrado en cascada.

### `AdInsight`

Métricas base de un anuncio para un día: `id`, `ad_id`, `organization_id`, `date` y las
ocho métricas base. Restricciones:

| Restricción | Propósito |
|---|---|
| `UNIQUE(ad_id, date)` | Una fila por anuncio y día |
| `ix_ad_insights_organization_id_date` | Filtrar por organización y rango de fechas |
| `ix_ad_insights_ad_id` | Consultar métricas de un anuncio |
| `ck_ad_insights_*` | Impedir métricas negativas |

`spend` y `revenue` usan `NUMERIC(12,2)` y se leen como `Decimal`.

## CRUD de marketing

### Schemas (`schemas.py`)

| Schema | Uso |
|---|---|
| `CampaignCreate` / `CampaignUpdate` | Entrada para crear / actualizar campaña |
| `CampaignRead` | Respuesta de campaña |
| `AdCreate` / `AdUpdate` | Entrada para crear / actualizar anuncio |
| `AdRead` | Respuesta de anuncio |

`Name` normaliza espacios y exige entre 1 y 120 caracteres. Los enums de los schemas
son los mismos `StrEnum` del modelo. `CampaignUpdate` y `AdUpdate` son parciales.

### Repository (`repository.py`)

| Función | Responsabilidad |
|---|---|
| `list_campaigns` | Filtra por organización, estado y objetivo; ordena y pagina |
| `get_campaign` | Busca una campaña por id y organización |
| `find_campaign_by_name` | Busca por nombre exacto sin distinguir mayúsculas |
| `list_ads` | Filtra anuncios por organización, campaña y estado |
| `get_ad` | Busca un anuncio por id, campaña y organización |

Todas las consultas incluyen `organization_id`; no existe una búsqueda global por id.

### Service (`service.py`)

| Función | Regla |
|---|---|
| `list_campaigns` / `get_campaign` | Lectura acotada a la organización |
| `find_campaign_by_name` | Busca por nombre exacto; `None` si no existe |
| `create_campaign` / `update_campaign` | Valida vía schemas y hace commit |
| `archive_campaign` | Cambia `status` a `archived`; idempotente |
| `list_ads` / `get_ad` | Exige que la campaña pertenezca a la organización |
| `create_ad` / `update_ad` | Crea o modifica anuncios dentro de la campaña |
| `archive_ad` | Cambia `status` a `archived`; idempotente |

`MarketingNotFoundError` representa un recurso ausente o ajeno. El handler registrado
en `create_app` lo convierte en `404` con `{"detail": "..."}`.

### Endpoints

| Método y ruta | Función |
|---|---|
| `GET /api/v1/campaigns` | Listar campañas |
| `POST /api/v1/campaigns` | Crear campaña |
| `GET /api/v1/campaigns/{id}` | Consultar campaña |
| `PATCH /api/v1/campaigns/{id}` | Actualizar campaña |
| `DELETE /api/v1/campaigns/{id}` | Archivar campaña |
| `GET /api/v1/campaigns/{id}/ads` | Listar anuncios |
| `POST /api/v1/campaigns/{id}/ads` | Crear anuncio |
| `GET /api/v1/campaigns/{id}/ads/{ad_id}` | Consultar anuncio |
| `PATCH /api/v1/campaigns/{id}/ads/{ad_id}` | Actualizar anuncio |
| `DELETE /api/v1/campaigns/{id}/ads/{ad_id}` | Archivar anuncio |

## Analítica

### Schemas (`analytics/schemas.py`)

| Schema | Uso |
|---|---|
| `DateRange` | Query obligatoria `date_from`/`date_to`; valida el orden |
| `TrendGranularity` | `day`, `week` o `month` |
| `BaseMetrics` | Ocho métricas base; `reach` puede ser `null` |
| `Metrics` | Métricas base más `frequency`, `ctr`, `cpc`, `cpm`, `cpl`, `conversion_rate` y `roas` |
| `OverviewRead` | `Metrics` más el rango consultado |
| `CampaignPerformance` | Id, nombre y métricas de una campaña |
| `AdPerformance` | Id, nombre, campaña y métricas de un anuncio |
| `TrendPoint` | Periodo (`period_start`/`period_end`) y métricas |

Los importes son `Decimal` y se serializan como cadena. Los ratios son `float`
redondeados a seis decimales o `null` si el denominador es cero.

### Repository (`analytics/repository.py`)

Devuelve dataclasses (`BaseAggregate`, `CampaignAggregate`, `AdAggregate`,
`TrendAggregate`) con sumas base y sin calcular ratios.

| Función | Responsabilidad |
|---|---|
| `get_overview` | Suma todas las filas de la organización en el rango |
| `get_campaign_performance` | Agrega una sola campaña o devuelve `None` |
| `list_campaigns` | Agrupa por campaña; ordena por gasto |
| `list_ads` | Agrupa por anuncio; filtro opcional de campaña |
| `list_trends` | Agrupa por día, semana o mes |

Todas las consultas filtran por `AdInsight.organization_id` y por el rango inclusivo.

### Service (`analytics/service.py`)

| Función | Responsabilidad |
|---|---|
| `calculate_metrics` | Deriva ratios desde sumas base; evita promediar ratios |
| `get_overview` | Construye `OverviewRead`; `reach` siempre `null` |
| `get_campaign_performance` | Métricas de una campaña o `None` sin datos |
| `list_campaign_performance` | Convierte agregados por campaña en schemas |
| `list_ad_performance` | Informa `reach`/`frequency` solo si el rango es de un día |
| `list_trends` | Calcula el fin de cada periodo y lo recorta al rango |

### Endpoints

| Método y ruta | Función |
|---|---|
| `GET /api/v1/analytics/overview` | Resumen de la organización |
| `GET /api/v1/analytics/campaigns` | Rendimiento por campaña |
| `GET /api/v1/analytics/ads` | Rendimiento por anuncio |
| `GET /api/v1/analytics/trends` | Serie temporal por periodo |

## Capa de IA offline

### `Intent`, `IntentResult` e `IntentClassifier`

`Intent` es el catálogo cerrado de intenciones: `top_ads_by_metric`,
`campaign_performance`, `compare_periods`, `help` y `unknown`. `IntentClassifier` es la
interfaz async; `RuleBasedClassifier` implementa reglas priorizadas (comparación, top
de anuncios, campaña, ayuda). Cada resultado incluye intención, confianza y motivo.

### `QueryPlan`

Vive en `ai/jev/plans.py`. Es una unión discriminada por `operation`:

| Clase | Campos propios |
|---|---|
| `TopAdsByMetricPlan` | `metric`, `limit` |
| `CampaignPerformancePlan` | `campaign_id` o `campaign_name` |
| `ComparePeriodsPlan` | `comparison_date_from`, `comparison_date_to` |

Todas validan fechas y prohíben campos extra. `parse_query_plan` convierte el texto del
LLM en un plan tipado y lanza `PlanParseError` si no cumple el contrato.

### `validate_query_plan(plan, expected_intent)`

Aplica políticas deterministas: coincidencia intención/operación, rango máximo de 366
días, rechazo de `reach`/`frequency` para ordenar anuncios y nombre de campaña no
vacío. Devuelve `PlanDecision` con la lista de violaciones.

### `LLMProvider` y `MockLLMProvider`

`LLMProvider` declara `async generate(prompt) -> str`. `MockLLMProvider` devuelve
respuestas fijas por patrón o un plan JSON generado por `build_plan_from_message`.
Puede simular latencia y errores de conexión o timeout. No hay proveedor real todavía.

### `build_plan_from_message(message, today=None)`

Traductor determinista: reconoce métricas, meses en español, fechas ISO, “este mes”,
“mes pasado”, “últimos N días”, límites y nombres de campaña. Devuelve un diccionario o
`None` si no puede proponer un plan.

### `ChatStatus`

`StrEnum` con `ok`, `needs_clarification` y `error`. Lo comparten el grafo, el servicio
y el endpoint.

### `ChatState`

`TypedDict` con el mensaje, `organization_id`, `dry_run`, ids de conversación/usuario,
intención, confianza, plan, datos, respuesta, estado y errores. Cada nodo actualiza
solo sus claves.

### `ChatNodes` y `build_chat_graph`

`ChatNodes` agrupa los nodos y las rutas condicionales; `build_chat_graph` los conecta
con `StateGraph` y compila el flujo:

| Nodo | Función |
|---|---|
| `classify_intent` | Ejecuta el clasificador |
| `help` / `clarify` / `error` | Respuestas terminales |
| `propose_plan` | Llama al LLM y parsea el plan |
| `validate_plan` | Aplica políticas y gestiona `dry_run` |
| `execute_service` | Ejecuta el plan con la sesión de la invocación |
| `generate_response` | Renderiza la respuesta |

La sesión viaja en `config["configurable"]["session"]`; el grafo se compila una vez en
`ChatService` y no usa checkpointer.

### `ChatService.handle(...)`

Construye el estado inicial, invoca el grafo y convierte el estado final en
`ChatResult` (`status`, `intent`, `confidence`, `reply`, `query_plan`, `data`). No
persiste estado.

### `execute_query_plan(session, organization_id, plan)`

Ejecuta el plan con los servicios de analytics y marketing, siempre acotado por la
organización autenticada. `top_ads_by_metric` ordena agregados ya calculados y usa
`LOWER_IS_BETTER` para CPC, CPM y CPL.

### `render_reply(plan, data)`

Genera el texto final con plantillas y los datos validados; no deja que el LLM invente
cifras. `HELP_TEXT` documenta ejemplos de uso.

## Capa HTTP

### `OrganizationContext`

Dataclass inmutable con `organization_id`. Es el contexto de seguridad que reciben los
endpoints. No se construye desde datos del cliente.

### `get_session(request)`

Dependencia de FastAPI que abre una sesión desde `request.app.state.session_factory` y
la cierra al terminar la petición.

### `get_current_organization(api_key, session)`

Flujo de autenticación:

1. Lee la cabecera `X-API-Key`.
2. Calcula su hash SHA-256.
3. Busca la entidad `ApiKey`.
4. Compara hashes con `hmac.compare_digest`.
5. Devuelve `OrganizationContext` o lanza `401`.

La cabecera ausente y la clave inválida producen la misma respuesta para no filtrar
información.

### `HealthResponse` y `health()`

`GET /health` devuelve `{"status": "ok"}`. Es un liveness check: valida que el proceso
HTTP responde, no la base de datos.

### `OrganizationResponse` y `me()`

`GET /api/v1/auth/me` devuelve la organización autenticada. Es un endpoint de
diagnóstico y la prueba viva del contrato de autenticación.

### `create_app(settings=None)`

Factory de la aplicación. Si no recibe `Settings`, usa `get_settings()`. Define el
lifespan que crea y libera el engine, registra los routers y mapea
`MarketingNotFoundError` a `404`. Uvicorn la invoca con `--factory`.

### `ChatRequest`, `ChatResponse` y `chat()`

`POST /api/v1/chat` valida el mensaje (1–1000 caracteres), inyecta la organización
autenticada y delega en un `ChatService` que ejecuta el grafo de LangGraph con
`RuleBasedClassifier` y `MockLLMProvider.default()`. `ChatResponse` expone estado, intención, confianza,
respuesta, plan y datos.

## Scripts y procedimientos

### `get_or_create_organization(session, name, currency_code)`

Busca por nombre y crea la organización si no existe. No modifica la moneda de una
organización existente.

### `create_api_key(organization_name, currency_code, raw_key)`

Genera la clave si no se proporciona, guarda solo el hash y la imprime una vez. Rechaza
claves menores de 16 caracteres y duplicados.

### `parse_args()`

Define `--organization`, `--currency` y `--key`. Pasar la clave por argumento deja
rastro en el historial del shell; se recomienda omitir `--key`.

### `seed(organization_name, reset=False)`

Genera tres campañas y siete anuncios con métricas diarias reproducibles (semilla 42)
del 1 de septiembre al 13 de noviembre de 2026. Sin `--reset` no duplica datos; con
`--reset` borra solo las campañas de demo de esa organización. No crea API keys.

### `scripts/chat_cli.py`

Cliente HTTP de terminal basado en `urllib`. Acepta `--api-key` o `JEV_API_KEY`,
`--message`, `--dry-run` y `--show-plan`. Sin `--message` abre un bucle interactivo.

## Clases abstractas e interfaces

Ahora existen dos interfaces porque el flujo necesita sustituir implementaciones sin
tocar el resto del sistema:

| Interfaz | Implementaciones actuales | Implementaciones previstas |
|---|---|---|
| `IntentClassifier` | `RuleBasedClassifier` | TF-IDF, embeddings, híbrido |
| `LLMProvider` | `MockLLMProvider` | proveedor real |

Además, Pydantic (`Settings`, `QueryPlan`, `ChatRequest`, `ChatResponse`) valida los
contratos y OpenAPI (`/openapi.json`) publica el esquema HTTP. No se mantiene un espejo
TypeScript manual.

## Contratos de API

Pydantic valida los datos y FastAPI publica el esquema en `/openapi.json`. Es la única
fuente de verdad. No existe un espejo TypeScript en el repositorio: si se construye un
frontend, sus tipos se generarán desde OpenAPI.
