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
| `jev_ai/infrastructure/database/` | Base declarativa, engine y sesiones |
| `scripts/create_api_key.py` | Procedimiento de alta de organización y clave |

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
lifespan que crea y libera el engine, y registra los routers. Uvicorn la invoca con
`--factory`.

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

## Clases abstractas e interfaces

En esta fase **no hay clases abstractas ni Protocol en Python**. No existe una segunda
implementación que justifique la abstracción (regla de oro: funcionalidad primero).

Los contratos actuales son:

- **Pydantic** (`Settings`, `HealthResponse`, `OrganizationResponse`): validación y
  esquema OpenAPI.
- **OpenAPI** (`/openapi.json`): contrato HTTP publicado. Si se construye un frontend
  TypeScript, sus tipos se generarán desde aquí. No se mantiene un espejo manual.

Interfaces previstas, que se crearán cuando exista más de una implementación:

| Interfaz | Fase | Implementaciones previstas |
|---|---|---|
| `IntentClassifier` | 8 | reglas, TF-IDF/embeddings |
| `LLMProvider` | 7 | mock determinista, proveedor real |

No se crean antes de tener dos implementaciones: un `ABC` con una sola clase concreta
solo añade ceremonia.

## Contratos de API

Pydantic valida los datos y FastAPI publica el esquema en `/openapi.json`. Es la única
fuente de verdad. No existe un espejo TypeScript en el repositorio: si se construye un
frontend, sus tipos se generarán desde OpenAPI.
