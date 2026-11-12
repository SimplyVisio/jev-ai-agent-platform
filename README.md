# JEV AI

Backend de inteligencia comercial y automatización de marketing. Expone una API de
analítica para campañas y anuncios, y una capa de IA que consulta esos resultados de
forma controlada.

El proyecto se construye en dos hitos: primero un backend de analítica verificable
sin IA; después el chatbot y el motor de decisiones JEV AI. La lógica de negocio y los
cálculos de métricas son deterministas y deben funcionar con el chatbot apagado.

## Estado

Fase 3 completada: API FastAPI con configuración tipada, autenticación por API key
contra PostgreSQL y migraciones con Alembic. El modelo de marketing y la capa de IA
llegan en las fases siguientes.

Consulta el roadmap y las decisiones del proyecto en [`AGENTS.md`](AGENTS.md).

## Stack

| Tecnología | Uso |
|---|---|
| Python 3.12 | Lenguaje |
| uv | Paquetes y entornos |
| Ruff | Lint y formato |
| pytest + pytest-asyncio | Tests |
| Docker + Docker Compose | PostgreSQL y Redis locales |
| FastAPI + Pydantic | API REST |
| SQLAlchemy async + Alembic + asyncpg | Persistencia y migraciones |
| testcontainers | Tests de integración con PostgreSQL real |
| LangGraph + LLM | Capa de IA (fases siguientes) |

## Requisitos

- Python 3.12
- [uv](https://docs.astral.sh/uv/)
- Docker con Docker Compose

## Puesta en marcha

```bash
cp .env.example .env    # ajusta POSTGRES_PASSWORD y DATABASE_URL
uv sync
docker compose up -d --wait
uv run alembic upgrade head
uv run python scripts/create_api_key.py --organization "Demo"
uv run uvicorn jev_ai.main:create_app --factory --reload
```

La API queda en `http://127.0.0.1:8000` y la documentación interactiva en `/docs`.
Cada llamada privada requiere la cabecera `X-API-Key` con la clave generada.

## API

| Endpoint | Autenticación | Función |
|---|---|---|
| `GET /health` | No | Estado del servicio |
| `GET /api/v1/auth/me` | `X-API-Key` | Organización asociada a la clave |

Las claves se guardan solo como hash SHA-256 y se muestran una única vez al crearlas.
En esta fase se crean con `scripts/create_api_key.py`; el CRUD administrativo llega
más adelante.

## Servicios locales

| Servicio | Dirección | Credenciales |
|---|---|---|
| PostgreSQL | `localhost:5433` | `.env` (`POSTGRES_*`) |
| Redis | `localhost:6379` | sin autenticación (solo local) |

Los puertos se publican únicamente en `127.0.0.1`. El 5433 evita el choque con un
PostgreSQL instalado en el host. Los contenedores tienen límites de recursos:
PostgreSQL 1 CPU / 512 MB y Redis 0.5 CPU / 256 MB.

```bash
docker compose ps                              # estado y healthchecks
docker compose logs -f postgres                # logs
docker compose exec postgres psql -U jev_ai -d jev_ai
docker compose exec redis redis-cli ping
docker compose down                            # detener
docker compose down -v                         # detener y borrar datos
```

## Comandos

```bash
uv run pytest                              # tests (requiere Docker por testcontainers)
uv run ruff check .                        # lint
uv run ruff format --check .               # comprobar formato
uv run ruff format .                       # aplicar formato
uv run alembic upgrade head                # aplicar migraciones
uv run alembic revision -m "descripción"   # crear migración
uv run uvicorn jev_ai.main:create_app --factory --reload
```

## Estructura

```text
src/jev_ai/          paquete de la aplicación
  api/               routers y dependencias HTTP
  modules/           dominios de negocio
  infrastructure/    base de datos y sesiones
alembic/             migraciones
scripts/             utilidades de desarrollo
tests/unit/          tests unitarios
tests/integration/   tests con infraestructura real
tests/e2e/           tests de extremo a extremo
docs/                documentación de arquitectura y métricas
compose.yaml         PostgreSQL y Redis locales
.github/workflows/   integración continua
```

## Documentación

- [`AGENTS.md`](AGENTS.md): decisiones, reglas y roadmap.
- [`docs/architecture.md`](docs/architecture.md): arquitectura del backend.

## Git

Flujo de ramas: `main` ← `develop` ← `feature/*`. Los commits siguen la convención
`feat:`, `fix:`, `test:`, `docs:`, `chore:` y `refactor:`.
