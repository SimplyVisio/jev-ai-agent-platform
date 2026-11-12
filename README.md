# JEV AI

Backend de inteligencia comercial y automatización de marketing. Expone una API de
analítica para campañas y anuncios, y una capa de IA que consulta esos resultados de
forma controlada.

El proyecto se construye en dos hitos: primero un backend de analítica verificable
sin IA; después el chatbot y el motor de decisiones JEV AI. La lógica de negocio y los
cálculos de métricas son deterministas y deben funcionar con el chatbot apagado.

## Estado

Fase 1 completada: estructura base, tooling, CI y documentación inicial. Todavía no
hay API, base de datos ni capa de IA.

Consulta el roadmap y las decisiones del proyecto en [`AGENTS.md`](AGENTS.md).

## Stack

| Tecnología | Uso |
|---|---|
| Python 3.12 | Lenguaje |
| uv | Paquetes y entornos |
| Ruff | Lint y formato |
| pytest | Tests |
| FastAPI + SQLAlchemy + PostgreSQL | API y persistencia (fases siguientes) |
| LangGraph + LLM | Capa de IA (fases siguientes) |

## Requisitos

- Python 3.12
- [uv](https://docs.astral.sh/uv/)

## Puesta en marcha

```bash
uv sync
```

## Comandos

```bash
uv run pytest                  # tests
uv run ruff check .            # lint
uv run ruff format --check .   # comprobar formato
uv run ruff format .           # aplicar formato
```

## Estructura

```text
src/jev_ai/          paquete de la aplicación
tests/unit/          tests unitarios
tests/integration/   tests con infraestructura real
tests/e2e/           tests de extremo a extremo
docs/                documentación de arquitectura y métricas
.github/workflows/   integración continua
```

## Documentación

- [`AGENTS.md`](AGENTS.md): decisiones, reglas y roadmap.
- [`docs/architecture.md`](docs/architecture.md): arquitectura del backend.

## Git

Flujo de ramas: `main` ← `develop` ← `feature/*`. Los commits siguen la convención
`feat:`, `fix:`, `test:`, `docs:`, `chore:` y `refactor:`.
