# Qupboard GraphQL / REST API

## Introduction

Qupboard is a proof-of-concept service for storing and serving **hardware calibration models** via
both a GraphQL and a REST API. It is built with:

- **[FastAPI](https://fastapi.tiangolo.com/)** – HTTP framework for the REST and GraphQL routers
- **[Strawberry](https://strawberry.rocks/)** – GraphQL schema and query engine
- **[SQLAlchemy](https://www.sqlalchemy.org/)** – ORM and database abstraction
- **[Alembic](https://alembic.sqlalchemy.org/)** – database schema migrations
- **[Pydantic](https://docs.pydantic.dev/)** – request/response validation and serialisation

The default backing store is SQLite (`qupboard.db`), configured via the `DATABASE_URL` environment
variable, but because we use SQLAlchemy, many other database engines may be used (PostgreSQL, MySQL,
MariaDB, etc.).

______________________________________________________________________

## Table of Contents

- [Getting Started](#getting-started)
- [Example Queries](#example-queries)
- [GraphQL Client Access](#graphql-client-access)
- [Project Structure](#project-structure)
- [Architecture](#architecture)
- [Database Implementation](#database-implementation)
- [Database Migrations with Alembic](#database-migrations-with-alembic)
- [Known Limitations / Not Implemented](#known-limitations--not-implemented)

______________________________________________________________________

## Getting Started

### Prerequisites

- Python 3.12 or 3.13
- [Poetry](https://python-poetry.org/) (dependency and virtual environment management)

### Installation

After cloning, install all dependencies (including dev dependencies) into a local virtual
environment:

```bash
poetry install --with dev
```

> The virtual environment is created in-project at `.venv/` (configured in `poetry.toml`). Omit
> `--with dev` for a runtime-only install (no test, lint, or documentation tools).

### Configuration

The application is configured via environment variables. All settings have sensible defaults so no
configuration is required to run locally:

| Variable       | Default                   | Description                        |
| -------------- | ------------------------- | ---------------------------------- |
| `DATABASE_URL` | `sqlite:///./qupboard.db` | SQLAlchemy database URL            |
| `GRAPHQL_PATH` | `/graphql`                | Path for the GraphQL endpoint      |
| `REST_PATH`    | `/rest`                   | Path prefix for the REST endpoints |

To override a setting, export it before running the application:

```bash
export DATABASE_URL="sqlite:///./my_custom.db"
```

### Database setup

Before running the application for the first time, apply all Alembic migrations to initialise the
database schema:

```bash
poetry run alembic upgrade head
```

### Running the application

Start the server using the installed `qupboard` script:

```bash
poetry run qupboard
```

or alternatively, run the FastAPI app directly (assuming you are in the project root and have
installed dependencies into a virtual environment):

```bash
./src/qupboard_graphql/main.py
```

The server starts on `http://0.0.0.0:8000`. The following endpoints are then available:

| URL                                 | Description                            |
| ----------------------------------- | -------------------------------------- |
| `http://localhost:8000/`            | Redirects to `/docs`                   |
| `http://localhost:8000/graphql`     | GraphQL API + interactive GraphiQL IDE |
| `http://localhost:8000/rest`        | REST API                               |
| `http://localhost:8000/docs`        | OpenAPI / Swagger UI                   |
| `http://localhost:8000/healthcheck` | Liveness probe – returns `OK`          |

### Running the tests

The test suite uses [pytest](https://pytest.org/) with an in-memory SQLite database so no prior
database setup is required. Each test runs inside a transaction that is rolled back on completion,
keeping tests fully isolated without recreating the schema between runs.

Run all tests:

```bash
poetry run pytest
```

Run tests in parallel (faster):

```bash
poetry run pytest -n auto
```

Run with coverage:

```bash
poetry run pytest --cov=qupboard_graphql --cov-report=term-missing
```

### Generating the documentation

The project documentation is built with [MkDocs](https://www.mkdocs.org/) using the
[Material](https://squidfunk.github.io/mkdocs-material/) theme. API reference pages are generated
automatically from the in-code docstrings via [mkdocstrings](https://mkdocstrings.github.io/). All
documentation dependencies are included in the dev dependency group and are installed automatically
by `poetry install`.

To start a live-reloading local documentation server:

```bash
poetry run mkdocs serve
```

The docs are then available at `http://127.0.0.1:8000`. The server watches for changes to both the
Markdown source files in `docs/` and the Python source files in `src/`, and automatically rebuilds
the site on any change.

> **Note:** MkDocs and the application server both default to port 8000. If you need to run both
> simultaneously, start MkDocs on a different port:
> `poetry run mkdocs serve --dev-addr 127.0.0.1:8001`.

To produce a self-contained static site (output written to `site/`):

```bash
poetry run mkdocs build
```

The `site/` directory is excluded from version control via `.gitignore`. The static output can be
served by any web server or deployed to any static hosting provider (GitHub Pages, GitLab Pages, S3,
etc.).

### Code style & pre-commit hooks

The project uses [Ruff](https://docs.astral.sh/ruff/) for linting and formatting, and
[pre-commit](https://pre-commit.com/) to enforce hygiene checks automatically on every commit. The
hooks are defined in `.pre-commit-config.yaml` and include:

| Hook                      | Purpose                                                                             |
| ------------------------- | ----------------------------------------------------------------------------------- |
| `ruff`                    | Lint and auto-fix Python source files                                               |
| `ruff-format`             | Format Python source files                                                          |
| `mdformat`                | Format Markdown files (100-character wrap)                                          |
| `conventional-pre-commit` | Enforce [Conventional Commits](https://www.conventionalcommits.org/) message format |
| General file hooks        | Trailing whitespace, YAML/TOML/JSON validity, merge-conflict markers, etc.          |

Install the hooks into your local clone (one-time setup, run after `poetry install`):

```bash
poetry run pre-commit install --install-hooks
poetry run pre-commit install --hook-type commit-msg
```

> The second command is required for the `conventional-pre-commit` hook, which runs at the
> `commit-msg` stage rather than the default `pre-commit` stage.

To run all hooks manually against the entire codebase:

```bash
poetry run pre-commit run --all-files
```

To run only the linter/formatter without committing:

```bash
poetry run ruff check --fix .
poetry run ruff format .
```

______________________________________________________________________

## Example Queries

### REST

The REST API is available at `/rest`. Interactive OpenAPI docs are served at `/docs`.

| Method | Path                            | Description                                        |
| ------ | ------------------------------- | -------------------------------------------------- |
| `GET`  | `/healthcheck`                  | Health check – returns `OK`                        |
| `GET`  | `/rest/logical-hardware`        | List all hardware model UUIDs                      |
| `GET`  | `/rest/logical-hardware/{uuid}` | Fetch a hardware model by UUID                     |
| `POST` | `/rest/logical-hardware`        | Create a hardware model from a JSON body           |
| `POST` | `/rest/logical-hardware/upload` | Create a hardware model from an uploaded JSON file |

> **Before running any read queries**, you must upload at least one hardware model. Use the example
> included in the repository:
>
> ```bash
> curl -X POST http://localhost:8000/rest/logical-hardware/upload \
>      -F "file=@tests/data/calibration_pydantic.json;type=application/json"
> ```
>
> The response will contain the UUID of the newly created model — use that UUID in the read queries
> below.

**List all hardware model IDs**

```bash
curl http://localhost:8000/rest/logical-hardware
```

**Fetch a specific hardware model**

```bash
curl http://localhost:8000/rest/logical-hardware/<uuid>
```

**Create a hardware model from a JSON body**

```bash
curl -X POST http://localhost:8000/rest/logical-hardware \
     -H "Content-Type: application/json" \
     -d @path/to/calibration.json
```

**Upload a hardware model from a file**

```bash
curl -X POST http://localhost:8000/rest/logical-hardware/upload \
     -F "file=@path/to/calibration.json;type=application/json"
```

______________________________________________________________________

### GraphQL

The GraphQL API is available at `/graphql`. An interactive GraphQL IDE is served at the same path in
a browser.

> **Before running any read queries**, ensure you have uploaded at least one hardware model via the
> REST API (see above).

**List all stored hardware model IDs**

Use this query first to obtain a valid UUID to pass to `getCalibration`:

```graphql
{
  getAllHardwareModelIds
}
```

**Fetch a calibration by ID**

Pass a UUID returned by `getAllHardwareModelIds` as the `id` argument:

```graphql
{
  getCalibration(id: "<uuid>") {
    id
    version
    calibrationId
    logicalConnectivity
    qubits {
      edges {
        node {
          id
          qubitKey
          physicalChannel {
            id
            channelKind
            basebandFrequency
          }
          pulseChannels {
            edges {
              node {
                id
                channelRole
                frequency
                pulse {
                  id
                  waveformType
                  width
                  amp
                }
              }
            }
          }
          resonator {
            id
            pulseChannels {
              edges {
                node {
                  id
                  channelRole
                  frequency
                }
              }
            }
          }
        }
      }
    }
  }
}
```

> For an exhaustive query that selects every available field (including `crossResonanceChannels`,
> `crossResonanceCancellationChannels`, `zxPi4Comps`, pulse sub-fields, etc.), see
> `test_get_calibration` in [`tests/test_graphql.py`](tests/test_graphql.py).

**Fetch the first page of qubits for a calibration**

The `qubits` field (and every other relationship collection) uses relay-style cursor pagination
generated automatically by `strawberry-sqlalchemy-mapper`. Pass `first` to set the page size and
`after` to advance to the next page using the `endCursor` returned in `pageInfo`.

```graphql
{
  getCalibration(id: "<uuid>") {
    id
    calibrationId
    qubits(first: 5, after: null) {
      edges {
        cursor
        node {
          id
          qubitKey
        }
      }
      pageInfo {
        hasNextPage
        endCursor
      }
    }
  }
}
```

Take `endCursor` from the response and pass it as `after` to fetch the next page:

```graphql
{
  getCalibration(id: "<uuid>") {
    qubits(first: 5, after: "<endCursor from previous response>") {
      edges {
        node { id qubitKey }
      }
      pageInfo {
        hasNextPage
        endCursor
      }
    }
  }
}
```

The full set of pagination arguments supported on `qubits` (and all other collections):

| Argument | Description                                                    |
| -------- | -------------------------------------------------------------- |
| `first`  | Page size going forward                                        |
| `after`  | Cursor from a previous `endCursor` — fetch the next page       |
| `last`   | Page size going backward                                       |
| `before` | Cursor from a previous `startCursor` — fetch the previous page |

**Fetch all calibrations (first page)**

`getAllCalibrations` uses the same relay-style cursor pagination as relationship fields. Pass
`first`/`after` to page forward and `last`/`before` to page backward.

```graphql
{
  getAllCalibrations(first: 20) {
    edges {
      cursor
      node {
        id
        version
        calibrationId
      }
    }
    pageInfo {
      hasNextPage
      endCursor
    }
  }
}
```

To fetch the next page, pass `endCursor` from `pageInfo` as the `after` argument:

```graphql
{
  getAllCalibrations(first: 20, after: "<endCursor from previous response>") {
    edges {
      node { id calibrationId }
    }
    pageInfo {
      hasNextPage
      endCursor
    }
  }
}
```

______________________________________________________________________

## GraphQL Client Access

### Interactive IDE

The easiest way to explore the schema and test queries is the interactive GraphiQL IDE served at
`http://localhost:8000/graphql` in a browser.

### Downloading the Schema

For programmatic access (e.g. for code generation or client development), there are several ways to
obtain the schema.

**Option 1 – Strawberry CLI (recommended, no server required)**

```bash
poetry run strawberry export-schema qupboard_graphql.api.graphql:schema
```

**Option 2 – Introspection query via `curl`**

```bash
curl -s -X POST http://localhost:8000/graphql \
     -H "Content-Type: application/json" \
     -d '{"query": "{ __schema { types { name } } }"}' | jq
```

For the full schema definition:

```bash
curl -s -X POST http://localhost:8000/graphql \
     -H "Content-Type: application/json" \
     -d @- <<'EOF'
{
  "query": "query IntrospectionQuery { __schema { queryType { name } mutationType { name } subscriptionType { name } types { ...FullType } directives { name description locations args { ...InputValue } } } } fragment FullType on __Type { kind name description fields(includeDeprecated: true) { name description args { ...InputValue } type { ...TypeRef } isDeprecated deprecationReason } inputFields { ...InputValue } interfaces { ...TypeRef } enumValues(includeDeprecated: true) { name description isDeprecated deprecationReason } possibleTypes { ...TypeRef } } fragment InputValue on __InputValue { name description type { ...TypeRef } defaultValue } fragment TypeRef on __Type { kind name ofType { kind name ofType { kind name ofType { kind name ofType { kind name ofType { kind name ofType { kind name } } } } } } }"
}
EOF
```

### GraphQL Client Libraries

The `/graphql` endpoint is standard GraphQL-over-HTTP. For client development, any GraphQL client
library that supports schema introspection and query execution can be used. The following are some
popular options:

| Language   | Library                                                           | Sync | Async | Introspection      | Notes                                                                                                                                                                                                                                                                                                                              |
| ---------- | ----------------------------------------------------------------- | ---- | ----- | ------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Python     | [gql](https://gql.readthedocs.io/)                                | ✅   | ✅    | ✅ runtime         | <ul><li>Most widely used Python GraphQL client</li><li>Multiple transports: HTTP, WebSocket, aiohttp</li><li>Validates queries against the live schema locally before sending</li><li>No generated types</li></ul>                                                                                                                 |
| Python     | [strawberry-graphql](https://strawberry.rocks/docs/guides/client) | ✅   | ✅    | ❌                 | <ul><li>Minimal built-in HTTP client</li><li>No transport abstraction or local schema validation</li><li>Convenient if Strawberry is already a dependency; otherwise prefer `gql`</li></ul>                                                                                                                                        |
| Python     | [ariadne-codegen](https://github.com/mirumee/ariadne-codegen)     | ✅   | ✅    | ✅ at codegen time | <ul><li>Generates a fully typed, dataclass-based client from <code>.graphql</code> query files</li><li>Full IDE auto-complete and static analysis</li><li>Requires a code-generation step; generated code must be kept in sync with the schema</li></ul>                                                                           |
| JavaScript | [Apollo Client](https://www.apollographql.com/docs/react/)        | ❌   | ✅    | ✅ via DevTools    | <ul><li>De-facto standard for GraphQL in the browser</li><li>Built-in normalised cache, reactive updates</li><li>Primarily React-oriented; heavier dependency for non-UI use</li></ul>                                                                                                                                             |
| JavaScript | [graphql-request](https://github.com/jasonkuhrt/graphql-request)  | ✅   | ✅    | ❌                 | <ul><li>Minimal zero-dependency client; ideal for Node.js scripts and serverless functions</li><li>No caching or schema validation</li></ul>                                                                                                                                                                                       |
| TypeScript | [graphql-codegen](https://the-guild.dev/graphql/codegen)          | ✅   | ✅    | ✅ at codegen time | <ul><li>Generates fully typed query hooks / SDK from <code>.graphql</code> files</li><li>Pluggable: outputs React hooks, plain fetch, urql, etc.</li><li>Requires a code-generation step; generated code must be kept in sync with the schema</li></ul>                                                                            |
| TypeScript | [urql](https://formidable.com/open-source/urql/)                  | ❌   | ✅    | ✅ via exchanges   | <ul><li>Lightweight, framework-agnostic (React, Vue, Svelte)</li><li>Extensible via exchanges (normalised cache, schema awareness, auth)</li><li>Smaller bundle than Apollo Client</li></ul>                                                                                                                                       |
| Rust       | [cynic](https://cynic-rs.dev/)                                    | ✅   | ✅    | ✅ at codegen time | <ul><li>Generates strongly typed Rust structs from <code>.graphql</code> query files at compile time</li><li>Zero-cost schema validation; incompatible queries are compile errors</li><li>Requires a code-generation step</li></ul>                                                                                                |
| Rust       | [graphql-client](https://github.com/graphql-rust/graphql-client)  | ✅   | ✅    | ✅ at codegen time | <ul><li>Derive-macro based; generates request/response types from <code>.graphql</code> files</li><li>Works with any HTTP client (reqwest, surf, etc.)</li><li>Requires a code-generation step</li></ul>                                                                                                                           |
| C++        | [CaffQL](https://github.com/caffeinetv/CaffQL)                    | ✅   | ❌    | ✅ at codegen time | <ul><li>Generates C++ types from a GraphQL schema and query files</li><li>The most feature-complete dedicated C++ option, but largely unmaintained since 2020</li><li>Requires a code-generation step</li></ul>                                                                                                                    |
| C++        | libcurl / [cpr](https://docs.libcpr.org/) + manual                | ✅   | ✅    | ❌                 | <ul><li>No actively maintained, general-purpose C++ GraphQL client library exists</li><li>Typical approach: POST JSON with libcurl or cpr and parse the response with <a href="https://github.com/nlohmann/json">nlohmann/json</a> or similar</li><li>No schema validation or generated types without additional tooling</li></ul> |

## Project Structure

```
qupboard_graphql/
├── pyproject.toml                  # Project metadata and dependencies
├── poetry.toml                     # Poetry local venv configuration
├── alembic.ini                     # Alembic configuration
├── alembic/
│   ├── env.py                      # Migration environment (wired to ORM models)
│   └── versions/                   # Generated migration scripts
├── qupboard.db                     # Default SQLite database
├── src/
│   └── qupboard_graphql/
│       ├── main.py                 # Entrypoint – starts uvicorn on 0.0.0.0:8000
│       ├── config.py               # Pydantic settings (DATABASE_URL, API paths)
│       ├── api/
│       │   ├── app.py              # FastAPI application factory
│       │   ├── graphql_types.py    # Strawberry type declarations (StrawberrySQLAlchemyMapper + @mapper.type classes)
│       │   ├── graphql.py          # Query resolvers, schema, and GraphQL router
│       │   ├── rest.py             # REST router (CRUD for hardware models)
│       │   └── root.py             # Health-check and root redirect routes
│       ├── db/
│       │   ├── database.py         # SQLAlchemy DeclarativeBase
│       │   ├── repository.py       # RepositoryMixin (get_by_uuid, get_all_pks)
│       │   ├── models.py           # ORM models mirroring the hardware model schema
│       │   ├── mapper_from_orm.py  # ORM → Pydantic conversion helpers
│       │   ├── mapper_to_orm.py    # Pydantic → ORM conversion helpers
│       │   └── session.py          # Module-level engine instance and get_db dependency
│       └── schemas/
│           └── hardware_model.py   # Pydantic schema for HardwareModel
└── tests/
    ├── conftest.py
    ├── test_graphql.py
    ├── test_model_loader.py
    ├── test_rest.py
    ├── test_root.py
    └── data/                       # Sample calibration JSON fixtures
```

______________________________________________________________________

## Architecture

### Layers

The application is split into four distinct layers, each with a clear responsibility and minimal
coupling to the others:

- **API layer** (`api/`) – FastAPI routers for REST and GraphQL endpoints, plus the GraphQL schema
  and resolvers.
- **Schema layer** (`schemas/`) – Pydantic models defining the hardware model schema used for
  request validation and serialisation in the REST API.
- **Database layer** (`db/`) – SQLAlchemy ORM models, database session management, and mapping
  helpers to convert between the Pydantic schema and the ORM models.
- **DB Engine** – the actual database engine (SQLite by default, but configurable via
  `DATABASE_URL`).

```mermaid
flowchart TD
    Client(["HTTP Client"])

    subgraph api ["api/"]
        REST["rest.py"]
        GQL["graphql.py + graphql_types.py"]
    end

    subgraph schemas ["schemas/"]
        HM["hardware_model.py<br/>(Pydantic models)"]
    end

    subgraph db ["db/"]
        TO["mapper_to_orm.py<br/>Pydantic → ORM"]
        FROM["mapper_from_orm.py<br/>ORM → Pydantic"]
        ORM["models.py<br/>(SQLAlchemy ORM)<br/>repository.py · session.py"]
    end

    DB[("SQLite / PostgreSQL / …")]

    api ~~~ schemas
    schemas ~~~ db
    db ~~~ DB

    Client --> REST
    Client --> GQL
    REST -->|"writes via"| HM
    HM --> TO
    TO --> ORM
    ORM --> FROM
    FROM -->|"reads via"| HM
    GQL -->|"reads directly<br/>(strawberry-sqlalchemy-mapper)"| ORM
    ORM <--> DB
```

### Request flow

**REST write** (`POST /rest/logical-hardware`):

1. FastAPI parses the JSON body into a Pydantic `HardwareModel`.
1. `mapper_to_orm` converts it into a tree of SQLAlchemy ORM objects.
1. The ORM objects are committed to the database and the new UUID is returned.

**REST read** (`GET /rest/logical-hardware/{uuid}`):

1. `HardwareModelORM.get_by_uuid` fetches the row (and all related rows via eager-loaded
   relationships).
1. `mapper_from_orm` reconstructs the full Pydantic `HardwareModel` and FastAPI serialises it to
   JSON.

**GraphQL read** (`getCalibration`, `getAllCalibrations`):

1. Strawberry calls the resolver, which fetches the ORM row(s) directly.
1. `strawberry-sqlalchemy-mapper` translates the ORM objects into Strawberry types on the fly — no
   manual mapping step required.

The GraphQL path therefore bypasses the Pydantic `schemas/` layer entirely; the Pydantic layer is
only used by the REST API and the ORM mappers. This means the database schema is effectively the
source of truth for the GraphQL API: any change to the ORM models is immediately reflected in the
GraphQL schema, with no separate mapping step required.

The REST API is more decoupled from the database schema — the Pydantic models and manual mappers act
as an explicit translation layer, giving the REST interface the freedom to evolve independently of
the underlying data model. This makes the REST surface better suited to a stable, versioned contract
for existing clients, while the GraphQL interface can track the database schema more closely and
change more rapidly.

Note that `strawberry-sqlalchemy-mapper` generates Strawberry types directly from the ORM models and
wires up relationship fields as paginated connections (hence the `edges { node { … } }` shape seen
in the example queries). Generic field-level filtering is not provided automatically; any
specialised queries (for example, fetching a subset of the qubits filtered by fidelity belonging to
a particular QPU) would still be written as custom resolvers that return ORM objects in the same
connection-style shape, leaving clients free to select whichever fields they need.

______________________________________________________________________

## Database Implementation

### Schema

The database schema semi-mirrors the `HardwareModel` Pydantic schema and is defined as SQLAlchemy
ORM models in `src/qupboard_graphql/db/models.py`. The table hierarchy is:

```
hardware_models
└── qubits
    ├── physical_channels      (channel_kind = 'qubit'; baseband + IQ-bias inlined)
    ├── pulse_channels         (channel_role discriminator; qubit-owned channels only)
    │   channel_role values:
    │     'drive'            – qubit drive channel
    │     'second_state'     – second-state channel (ss_active, ss_delay)
    │     'freq_shift'       – freq-shift channel   (fs_active, fs_amp, fs_phase)
    │     'reset_qubit'      – qubit reset channel  (reset_delay)
    │   └── calibratable_pulses (owner_uuid -> pulse_channels.id + pulse_role discriminator)
    ├── cross_resonance_channels (role = 'cr' | 'crc')
    │   └── calibratable_pulses  (pulse_role = 'cr')
    ├── phase_comp_x_pi_2      (inlined column on qubits)
    ├── zx_pi_4_comps          (one per CR pair)
    │   └── calibratable_pulses (pulse_role = 'zx_precomp' | 'zx_postcomp', nullable)
    └── resonators             (one-to-one with qubit)
        ├── physical_channels  (channel_kind = 'resonator'; baseband + IQ-bias inlined)
        └── pulse_channels     (channel_role discriminator; resonator-owned channels only)
            channel_role values:
              'measure'        – resonator measure channel
              'acquire'        – resonator acquire channel (acq_delay/width/sync/use_weights)
              'reset_resonator'– resonator reset channel   (reset_delay)
            └── calibratable_pulses (owner_uuid -> pulse_channels.id + pulse_role discriminator)
```

Note that although this does store the same information as the `HardwareModel` schema, it is not a
direct 1:1 mapping — we have made some adjustments. For example, ids are consistently generated as
UUIDs at the database level (instead of a mix of UUIDs and integer PKs) and named `id`, and some
fields are inlined for simplicity (e.g. physical channel parameters are stored directly on the
qubits and resonators instead of separate tables).

This is part of the demonstration to show how legacy schemas can be adapted to fit the needs of a
particular database engine or query patterns, and how the REST API can be decoupled from the
database schema via the Pydantic layer and manual mappers.

Exposing the SQLAlchemy models directly in the GraphQL layer via `strawberry-sqlalchemy-mapper` is
also a deliberate choice to show how the GraphQL API can track the database schema closely without
needing a separate mapping layer, while the REST API can evolve more independently to keep legacy
clients happy.

The database URL defaults to `sqlite:///./qupboard.db` and can be overridden with the `DATABASE_URL`
environment variable.

______________________________________________________________________

## Database Migrations with Alembic

As the application evolves, the database schema needs to evolve with it — new tables are added,
columns are renamed, types change, and so on. Without a migration tool, keeping the schema in sync
across development machines, CI environments, and production deployments requires manual
`ALTER TABLE` statements that are error-prone and hard to reproduce reliably.

[Alembic](https://alembic.sqlalchemy.org/) solves this by treating schema changes as **versioned
migration scripts** stored alongside the source code. Each migration is a small Python file
describing how to move the schema forward (`upgrade`) and, optionally, how to reverse that change
(`downgrade`). Alembic records which migrations have been applied in an `alembic_version` table in
the database, so it always knows exactly what state the schema is in and which scripts still need to
run.

Alembic integrates directly with SQLAlchemy, meaning it can **autogenerate** migration scripts by
comparing the current ORM model definitions against the live database schema — catching additions,
removals, and type changes automatically, though the generated scripts should always be reviewed
before committing.

The Alembic project lives at the **project root**:

```
alembic.ini          # Alembic configuration
alembic/
├── env.py           # Wired to ORM Base metadata and app settings
└── versions/        # Migration scripts
```

`env.py` automatically reads `DATABASE_URL` from the application settings, so no manual URL
configuration is required. `render_as_batch=True` is enabled to support SQLite's limited
`ALTER TABLE` capabilities.

All commands below assume they are run from the **project root**.

**Apply all pending migrations**

```bash
poetry run alembic upgrade head
```

**Check whether the database is up to date**

```bash
poetry run alembic check
```

**Show the current revision**

```bash
poetry run alembic current
```

**Generate a new migration after changing ORM models**

```bash
poetry run alembic revision --autogenerate -m "describe_your_change"
```

**Downgrade one revision**

```bash
poetry run alembic downgrade -1
```

**Stamp an existing database without running migrations** (useful when the schema was created
outside of Alembic)

```bash
poetry run alembic stamp head
```

______________________________________________________________________

## Known Limitations / Not Implemented

This is a proof-of-concept service. The following are notable omissions that would be required in a
production-grade version:

### DataLoaders (N+1 query problem)

The GraphQL resolvers fetch related ORM objects via SQLAlchemy eager-loading, but this is done
naively per-root-object. When fetching multiple calibrations each with many qubits, pulse channels,
etc., this can produce an **N+1 query pattern**. A real service would use
[Strawberry DataLoaders](https://strawberry.rocks/docs/guides/dataloaders) (backed by the built-in
[`strawberry.dataloader`](https://strawberry.rocks/docs/guides/dataloaders)) to batch and cache
database lookups within a single request.

### Authentication & Authorisation

There is no authentication or authorisation. A production service would require at minimum:

- **Authentication** – e.g. OAuth 2.0 / OIDC JWT bearer tokens, API keys, or mutual TLS.
- **Authorisation** – role-based or attribute-based access control to restrict which clients can
  read or write which hardware models.

### GraphQL Mutations

The GraphQL API is currently read-only. A real service would expose **mutations** for creating,
updating, and deleting hardware models, with appropriate input validation mirroring what the REST
`POST` endpoint does today.

### Input Validation on the GraphQL Layer

Pydantic validation is only applied on the REST path. GraphQL mutations (once added) should perform
equivalent validation. Strawberry supports Pydantic integration via
`strawberry.experimental.pydantic` that could be used to share the schema definitions.

### Async Database Access

The application uses a synchronous SQLAlchemy session (created per-request inside `get_db`). FastAPI
automatically runs synchronous dependencies in a thread pool, but this still blocks a worker thread
per request. A production service under concurrent load should use SQLAlchemy's async engine
(`create_async_engine` + `AsyncSession`) together with an async-compatible driver (e.g. `aiosqlite`
for SQLite, `asyncpg` for PostgreSQL) to avoid blocking the event loop.

### Caching

Frequently-read calibration models are re-fetched from the database on every request. A caching
layer (e.g. Redis with an appropriate TTL, or an in-process LRU cache invalidated on write) would
dramatically reduce database load for read-heavy workloads.

### Observability

There is no structured logging, metrics, or distributed tracing. A production service should emit:

- **Structured logs** (e.g. via `structlog`) including request IDs for correlation.
- **Metrics** (e.g. Prometheus counters/histograms via `prometheus-fastapi-instrumentator`).
- **Traces** (e.g. OpenTelemetry spans covering HTTP requests and database queries).

### Database Connection Pooling & Configuration

The current SQLite default is not suitable for production. When switching to PostgreSQL or another
server-side database, connection pool settings (`pool_size`, `max_overflow`, `pool_timeout`) should
be tuned and exposed via configuration, and a connection health-check (`pool_pre_ping=True`) should
be enabled.

Additionally, `session.py` passes `connect_args={"check_same_thread": False}` unconditionally — this
argument is SQLite-specific and will cause an error with other database drivers. It should be gated
behind a check on the `DATABASE_URL` scheme, or removed in favour of driver-appropriate
configuration.

### REST API Versioning

The REST endpoints have no version prefix (e.g. `/v1/rest/…`). A stable public API should be
versioned from the start to allow breaking changes to be introduced without disrupting existing
clients.

### Error Handling

Unhandled exceptions propagate as generic 500 responses with minimal detail. A real service would
map domain errors (e.g. "model not found", "validation failed", "database constraint violated") to
well-structured error responses with appropriate HTTP status codes, and equivalent
[GraphQL error extensions](https://strawberry.rocks/docs/guides/errors) for the GraphQL path.
