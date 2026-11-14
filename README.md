# JEV AI

Backend de inteligencia comercial y automatización de marketing. Expone una API de
analítica para campañas y anuncios, y una capa de IA que consulta esos resultados de
forma controlada.

El proyecto se construye en dos hitos: primero un backend de analítica verificable
sin IA; después el chatbot y el motor de decisiones JEV AI. La lógica de negocio y los
cálculos de métricas son deterministas y deben funcionar con el chatbot apagado.

## Estado

Hito 1 completo: API FastAPI con configuración tipada, autenticación por API key
contra PostgreSQL, migraciones con Alembic, modelo de marketing (`campaigns`, `ads` y
`ad_insights`), CRUD de campañas y anuncios y API de analítica con métricas agregadas.

Además, hay un chat que traduce lenguaje natural a un `QueryPlan` validado y lo
ejecuta con SQLAlchemy. Por defecto usa un **mock determinista**, sin API key ni coste;
también admite un proveedor **OpenAI-compatible** configurado por entorno. El flujo se
orquesta con LangGraph y el clasificador se evalúa con un dataset versionado
(accuracy, precision, recall y F1); CI falla si baja de los umbrales.

Las conversaciones se persisten en PostgreSQL (`conversations` y `messages`) con
memoria acotada: los últimos 10 mensajes y 4000 caracteres, más el último plan para
resolver seguimientos. Redis sigue fuera de esta fase.

Consulta la arquitectura, el contrato HTTP y las decisiones en [`docs/`](docs/).

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
| LangGraph | Orquestación del flujo de chat |
| LLM mock determinista | Capa de IA offline (QueryPlan + políticas JEV AI) |
| OpenAI-compatible | Proveedor real opcional; misma interfaz que el mock |
| Dataset + métricas | Evaluación del clasificador en CI |

## Requisitos

- Python 3.12
- [uv](https://docs.astral.sh/uv/)
- Docker con Docker Compose

## Puesta en marcha

```bash
cp .env.example .env    # ajusta POSTGRES_PASSWORD; LLM_PROVIDER=mock por defecto
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
| `POST /api/v1/chat` | `X-API-Key` | Lenguaje natural → QueryPlan → datos (stateless) |
| `GET/POST /api/v1/conversations` | `X-API-Key` | Listar / abrir conversaciones |
| `GET /api/v1/conversations/{id}` | `X-API-Key` | Consultar una conversación |
| `GET /api/v1/conversations/{id}/messages` | `X-API-Key` | Listar el transcript |
| `POST /api/v1/conversations/{id}/messages` | `X-API-Key` | Enviar y persistir un turno |

Las claves se guardan solo como hash SHA-256 y se muestran una única vez al crearlas.
En esta fase se crean con `scripts/create_api_key.py`.

Los listados aceptan `limit` (1–100, por defecto 50), `offset` y filtros de estado u
objetivo. `DELETE` archiva el recurso (`status=archived`) sin borrar anuncios ni
métricas.

Los endpoints de analítica requieren `date_from` y `date_to` (inclusivos). Las
fórmulas, la regla de sumar métricas base antes de calcular ratios y el tratamiento
de `reach` están documentados en [`docs/metrics.md`](docs/metrics.md).

El endpoint `/chat` es stateless: clasifica la intención, valida el `QueryPlan` con las
políticas de JEV AI y ejecuta la consulta con los mismos servicios que la API de
analítica. Para conservar el hilo, crea una conversación y envía mensajes a
`/conversations/{id}/messages`. El contrato completo está en [`docs/api.md`](docs/api.md)
y el flujo en [`docs/chat.md`](docs/chat.md).

El esquema OpenAPI en `/openapi.json` es el contrato fuente de la API. Si más adelante
se construye un frontend TypeScript, sus tipos se generarán desde ese esquema; no se
mantiene un espejo manual.

## Chat

```bash
curl -s http://127.0.0.1:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $JEV_API_KEY" \
  -d '{"message": "¿Cuáles son los 3 mejores anuncios por ROAS en octubre de 2026?"}'
```

La respuesta trae el estado, la intención, la confianza, el texto, el `query_plan`
validado y los datos. Los mensajes ambiguos devuelven `needs_clarification` con una
petición de aclaración; `dry_run: true` valida el plan sin consultar la base de datos.

### Proveedor LLM real

El mock es el predeterminado. Para usar OpenAI, define las variables en `.env` y
reconstruye el backend:

```bash
LLM_PROVIDER=openai
LLM_API_KEY=sk-...
LLM_MODEL=gpt-4o-mini
LLM_BASE_URL=https://api.openai.com/v1
```

```bash
docker compose up -d --build --wait backend
```

El proveedor solo propone el `QueryPlan` en JSON; la validación de JEV AI, el acceso a
datos y la respuesta por plantilla no cambian. Los tests usan un transporte HTTP falso:
no consumen la API real. Si la clave falta, la aplicación falla al arrancar en vez de
volver silenciosamente al mock.

### Conversaciones persistentes

```bash
curl -s http://127.0.0.1:8000/api/v1/conversations \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $JEV_API_KEY" \
  -d '{"title": "Análisis de octubre"}'

curl -s http://127.0.0.1:8000/api/v1/conversations/$CONVERSATION_ID/messages \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $JEV_API_KEY" \
  -d '{"message": "Top 3 anuncios por ROAS en octubre de 2026"}'
```

Cada turno guarda la pregunta, la respuesta, la intención, la confianza, el estado y el
plan. La memoria usa los últimos 10 mensajes (4000 caracteres); un seguimiento como
“¿Y en septiembre?” reutiliza el plan anterior con el nuevo periodo. El `data` de
analítica no se duplica en la tabla.

Cliente de terminal, sin dependencias extra. Usa `/chat` (stateless), así que sirve
para probar el proveedor configurado, pero no la memoria persistente:

```bash
JEV_API_KEY="jev_..." python scripts/chat_cli.py
JEV_API_KEY="jev_..." python scripts/chat_cli.py --message "Compara este mes con el mes pasado"
JEV_API_KEY="jev_..." python scripts/chat_cli.py --show-plan
JEV_API_KEY="jev_..." python scripts/chat_cli.py --debug
```

`--debug` muestra la traza real de LangGraph: clasificación, plan, validación,
consulta a PostgreSQL y generación de la respuesta, con tiempos por nodo. No inventa
un paso de caché: hoy el backend no cachea resultados; Redis está levantado pero la
aplicación todavía no lo usa.

Para depurar el mock sin depender de una API externa, deja `LLM_PROVIDER=mock` en
`.env`, reconstruye el backend y ejecuta el mismo CLI:

```bash
docker compose up -d --build --wait backend
JEV_API_KEY="jev_..." uv run python scripts/chat_cli.py \
  --message "Top 2 anuncios por ROAS en octubre de 2026" --debug
```

No hay un CLI separado para el mock: `--debug` sirve tanto para el mock como para
OpenAI y muestra qué regla del clasificador y qué plan se usaron.

Colección HTTP para Bruno en [`bruno/jev-ai`](bruno/jev-ai): importa la carpeta,
selecciona el entorno `Local`, sustituye `apiKey` por tu clave y `conversationId` por
el id que devuelva el POST de conversaciones.

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

## Despliegue

Todavía no hay un proveedor cloud elegido ni manifiestos de Terraform/Kubernetes. El
procedimiento reproducible con Docker Compose es:

1. Copiar `.env.example` a `.env` y definir una contraseña fuerte, `LLM_PROVIDER` y,
   si se usa OpenAI, `LLM_API_KEY`. No versionar `.env`.
2. Construir y arrancar: `docker compose up -d --build --wait`.
3. Aplicar migraciones: `docker compose run --rm backend alembic upgrade head`.
4. Crear la organización y su API key una sola vez:
   `docker compose run --rm backend python scripts/create_api_key.py --organization "Producción"`.
5. Sembrar datos solo en demo/staging; en producción no ejecutes `scripts/seed.py`.
6. Verificar `curl -fsS http://127.0.0.1:8000/health` y revisar
   `docker compose ps` y `docker compose logs backend`.
7. Poner un proxy inverso con TLS delante de la API. No publiques PostgreSQL ni
   Redis: deben seguir en la red interna `data`.
8. Configurar backups de PostgreSQL, retención de logs y límites de recursos antes
   de abrir tráfico real.

El Compose actual publica la API solo en `127.0.0.1:8000`. En un servidor remoto hay
que adaptar ese binding o conectar el proxy a la red `edge`; no se debe exponer
directamente PostgreSQL ni Redis. Si más adelante se elige un proveedor cloud, faltan
los manifiestos específicos de despliegue, secretos gestionados y observabilidad.

## Comandos

```bash
uv run pytest                              # tests (requiere Docker por testcontainers)
uv run python scripts/evaluate_classifier.py  # accuracy/F1 del clasificador
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
  ai/                capa de IA: JEV AI, proveedores LLM, chat y workflows
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

- [`docs/architecture.md`](docs/architecture.md): arquitectura del backend.
- [`docs/api.md`](docs/api.md): contrato HTTP de todos los endpoints.
- [`docs/chat.md`](docs/chat.md): flujo de chat, QueryPlan, políticas y proveedores.
- [`docs/evaluation.md`](docs/evaluation.md): dataset y métricas del clasificador.
- [`docs/metrics.md`](docs/metrics.md): fórmulas y reglas de agregación.
- [`docs/code-reference.md`](docs/code-reference.md): funciones, clases y contratos.
- [`docs/decisions/`](docs/decisions): ADR de decisiones clave.

## Git

Flujo de ramas: `main` ← `develop` ← `feature/*`. Los commits siguen la convención
`feat:`, `fix:`, `test:`, `docs:`, `chore:` y `refactor:`.
