# JEV AI

Backend de inteligencia comercial y automatización de marketing. Expone una API de
analítica para campañas y anuncios, y una capa de IA que consulta esos resultados de
forma controlada.

El proyecto se construye en dos hitos: primero un backend de analítica verificable
sin IA; después el chatbot y el motor de decisiones JEV AI. La lógica de negocio y los
cálculos de métricas son deterministas y deben funcionar con el chatbot apagado.

## Estado

Fases 1 a 6 completadas: API FastAPI con configuración tipada, autenticación por API
key contra PostgreSQL, migraciones con Alembic, modelo de marketing (`campaigns`,
`ads` y `ad_insights`), CRUD de campañas y anuncios y API de analítica con métricas
agregadas.

Además, hay un **chat offline** que traduce lenguaje natural a un `QueryPlan`
validado y lo ejecuta con SQLAlchemy. Funciona sin API key de ningún proveedor LLM y
sin túnel: el LLM es un mock determinista. Redis, memoria de conversación y LangGraph
quedan para la siguiente fase.

Consulta el roadmap y las decisiones del proyecto en [`AGENTS.md`](AGENTS.md).

## Stack

| Tecnología | Uso |
|---|---|
| Python 3.12 | Lenguaje |
| uv | Paquetes y entornos |
| Ruff | Lint y formato |
| import-linter | Contratos de dependencias entre capas |
| pytest + pytest-asyncio | Tests |
| Docker + Docker Compose | Backend, PostgreSQL y Redis |
| FastAPI + Pydantic | API REST |
| SQLAlchemy async + Alembic + asyncpg | Persistencia y migraciones |
| testcontainers | Tests de integración con PostgreSQL real |
| LLM mock determinista | Capa de IA offline (QueryPlan + políticas JEV AI) |
| LangGraph + LLM real | Capa de IA completa (fases siguientes) |

## Requisitos

- Python 3.12
- [uv](https://docs.astral.sh/uv/)
- Docker con Docker Compose

## Puesta en marcha

```bash
cp .env.example .env    # ajusta POSTGRES_PASSWORD
uv sync
docker compose up -d --build --wait
docker compose run --rm backend alembic upgrade head
docker compose run --rm backend python scripts/create_api_key.py --organization "Demo"
docker compose run --rm backend python scripts/seed.py --organization "Demo"
```

El último comando siembra datos sintéticos reproducibles (tres campañas, siete
anuncios y métricas diarias) para poder probar el chat y la analítica con contenido
real. Usa `--reset` para regenerarlos.

La API queda en `http://127.0.0.1:8000` y la documentación interactiva en `/docs`.
Cada llamada privada requiere la cabecera `X-API-Key` con la clave generada.

## Aislamiento de infraestructura

El backend corre dentro de Compose. PostgreSQL y Redis **no publican puertos en el
host**: solo son accesibles desde la red interna `data`. La red `edge` publica
únicamente la API en `127.0.0.1` para que puedas usar Bruno o el navegador.

```text
host ──127.0.0.1:8000──> backend ──data──> postgres
                                   └────> redis
```

Por eso los comandos de migración y creación de claves se ejecutan dentro del
contenedor del backend. Los tests usan testcontainers y no dependen de esta red.

## API

| Endpoint | Autenticación | Función |
|---|---|---|
| `GET /health` | No | Estado del servicio |
| `GET /api/v1/auth/me` | `X-API-Key` | Organización asociada a la clave |
| `GET/POST /api/v1/campaigns` | `X-API-Key` | Listar / crear campañas |
| `GET/PATCH/DELETE /api/v1/campaigns/{id}` | `X-API-Key` | Consultar / actualizar / archivar |
| `GET/POST /api/v1/campaigns/{id}/ads` | `X-API-Key` | Listar / crear anuncios |
| `GET/PATCH/DELETE /api/v1/campaigns/{id}/ads/{ad_id}` | `X-API-Key` | Consultar / actualizar / archivar |
| `GET /api/v1/analytics/overview` | `X-API-Key` | Resumen de la organización |
| `GET /api/v1/analytics/campaigns` | `X-API-Key` | Rendimiento por campaña |
| `GET /api/v1/analytics/ads` | `X-API-Key` | Rendimiento por anuncio |
| `GET /api/v1/analytics/trends` | `X-API-Key` | Evolución por día, semana o mes |
| `POST /api/v1/chat` | `X-API-Key` | Lenguaje natural → QueryPlan → datos |

Las claves se guardan solo como hash SHA-256 y se muestran una única vez al crearlas.
En esta fase se crean con `scripts/create_api_key.py`.

Los listados aceptan `limit` (1–100, por defecto 50), `offset` y filtros de estado u
objetivo. `DELETE` archiva el recurso (`status=archived`) sin borrar anuncios ni
métricas.

Los endpoints de analítica requieren `date_from` y `date_to` (inclusivos). Las
fórmulas, la regla de sumar métricas base antes de calcular ratios y el tratamiento
de `reach` están documentados en [`docs/metrics.md`](docs/metrics.md).

El endpoint de chat es stateless: no guarda conversaciones ni usa Redis. Clasifica la
intención, valida el `QueryPlan` con las políticas de JEV AI y ejecuta la consulta con
los mismos servicios que la API de analítica. El contrato completo está en
[`docs/api.md`](docs/api.md) y el flujo en [`docs/chat.md`](docs/chat.md).

El esquema OpenAPI en `/openapi.json` es el contrato fuente de la API. Si más adelante
se construye un frontend TypeScript, sus tipos se generarán desde ese esquema; no se
mantiene un espejo manual.

## Chat offline

```bash
curl -s http://127.0.0.1:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $JEV_API_KEY" \
  -d '{"message": "¿Cuáles son los 3 mejores anuncios por ROAS en octubre de 2026?"}'
```

La respuesta trae el estado, la intención, la confianza, el texto, el `query_plan`
validado y los datos. Los mensajes ambiguos devuelven `needs_clarification` con una
petición de aclaración; `dry_run: true` valida el plan sin consultar la base de datos.

Cliente de terminal, sin dependencias extra:

```bash
JEV_API_KEY="jev_..." python scripts/chat_cli.py
JEV_API_KEY="jev_..." python scripts/chat_cli.py --message "Compara este mes con el mes pasado"
JEV_API_KEY="jev_..." python scripts/chat_cli.py --show-plan
```

Colección HTTP para Bruno en [`bruno/jev-ai`](bruno/jev-ai): importa la carpeta,
selecciona el entorno `Local` y sustituye `apiKey` por tu clave.

## Compose

| Servicio | Acceso |
|---|---|
| API | `localhost:8000` (solo `127.0.0.1`) |
| PostgreSQL | Red interna `data`, sin puerto en el host |
| Redis | Red interna `data`, sin puerto en el host |

```bash
docker compose ps                              # estado y healthchecks
docker compose logs -f backend                 # logs
docker compose exec postgres psql -U jev_ai -d jev_ai
docker compose exec redis redis-cli ping
docker compose down                            # detener
docker compose down -v                         # detener y borrar datos
```

Los contenedores tienen límites de recursos: PostgreSQL 1 CPU / 512 MB, Redis
0.5 CPU / 256 MB y backend 1 CPU / 512 MB.

## Comandos

```bash
uv run pytest                              # tests (requiere Docker por testcontainers)
uv run lint-imports                        # contratos de dependencias entre capas
uv run ruff check .                        # lint
uv run ruff format --check .               # comprobar formato
uv run ruff format .                       # aplicar formato

docker compose run --rm backend alembic upgrade head
docker compose run --rm backend python scripts/create_api_key.py --organization "Demo"
docker compose run --rm backend python scripts/seed.py --organization "Demo"
docker compose up -d --build --wait        # reconstruir tras cambiar código o migraciones
```

## Estructura

```text
src/jev_ai/          paquete de la aplicación
  api/               routers y dependencias HTTP
  modules/           dominios de negocio
  ai/                capa de IA: JEV AI, LLM mock y chat
  infrastructure/    base de datos y sesiones
alembic/             migraciones
mocks/datasets/      dataset de mensajes e intenciones
bruno/               colección HTTP para Bruno
scripts/             utilidades de desarrollo
tests/unit/          tests unitarios
tests/integration/   tests con infraestructura real
tests/e2e/           tests de extremo a extremo
docs/                arquitectura, API, chat, métricas y decisiones
compose.yaml         backend, PostgreSQL y Redis
Dockerfile           imagen del backend
.github/workflows/   integración continua
```

## Documentación

- [`AGENTS.md`](AGENTS.md): decisiones, reglas y roadmap.
- [`docs/architecture.md`](docs/architecture.md): arquitectura del backend.
- [`docs/api.md`](docs/api.md): contrato HTTP de todos los endpoints.
- [`docs/chat.md`](docs/chat.md): flujo de chat, QueryPlan, políticas y mocks.
- [`docs/metrics.md`](docs/metrics.md): fórmulas y reglas de agregación.
- [`docs/code-reference.md`](docs/code-reference.md): funciones, clases y contratos.
- [`docs/decisions/`](docs/decisions): ADR de decisiones clave.

## Git

Flujo de ramas: `main` ← `develop` ← `feature/*`. Los commits siguen la convención
`feat:`, `fix:`, `test:`, `docs:`, `chore:` y `refactor:`.
