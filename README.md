# Qupboard GraphQL / REST API

## Introduction

Qupboard is a proof-of-concept service for storing and serving **hardware calibration models** via both a GraphQL and a REST API. It is built with:

- **[FastAPI](https://fastapi.tiangolo.com/)** – HTTP framework for the REST and GraphQL routers
- **[Strawberry](https://strawberry.rocks/)** – GraphQL schema and query engine
- **[SQLAlchemy](https://www.sqlalchemy.org/)** – ORM and database abstraction
- **[Alembic](https://alembic.sqlalchemy.org/)** – database schema migrations
- **[Pydantic](https://docs.pydantic.dev/)** – request/response validation and serialisation

The default backing store is SQLite (`qupboard.db`), configured via the `DATABASE_URL` environment variable, but
because we use SQLAlchemy, many other database engines may be used (postgres, MySQL, MariaDB etc).

---

## Getting Started

### Prerequisites

- Python 3.12 or 3.13
- [Poetry](https://python-poetry.org/) (dependency and virtual environment management)

### Installation

Clone the repository and install all dependencies (including dev dependencies) into a local virtual environment:

```bash
git clone <repo-url>
cd qupboard_graphql
poetry install --with dev
```

> The virtual environment is created in-project at `.venv/` (configured in `poetry.toml`).

### Configuration

The application is configured via environment variables. All settings have sensible defaults so no configuration is required to run locally:

| Variable       | Default                   | Description                        |
|----------------|---------------------------|------------------------------------|
| `DATABASE_URL` | `sqlite:///./qupboard.db` | SQLAlchemy database URL            |
| `GRAPHQL_PATH` | `/graphql`                | Path for the GraphQL endpoint      |
| `REST_PATH`    | `/rest`                   | Path prefix for the REST endpoints |

To override a setting, export it before running the application:

```bash
export DATABASE_URL="sqlite:///./my_custom.db"
```

### Database setup

Before running the application for the first time, apply all Alembic migrations to initialise the database schema:

```bash
poetry run alembic upgrade head
```

### Running the application

Start the server using the installed `qupboard` script:

```bash
poetry run qupboard
```

or alternatively, run the FastAPI app directly (assuming you are in the project root and have installed dependencies
into a virtual environment):

```bash
./src/qupboard_graphql/main.py
````

The server starts on `http://0.0.0.0:8000`. The following endpoints are then available:

| URL                             | Description                            |
|---------------------------------|----------------------------------------|
| `http://localhost:8000/graphql` | GraphQL API + interactive GraphiQL IDE |
| `http://localhost:8000/rest`    | REST API                               |
| `http://localhost:8000/docs`    | OpenAPI / Swagger UI                   |

### Running the tests

The test suite uses [pytest](https://pytest.org/) with an in-memory SQLite database so no prior database setup is required.

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

---

## Project Structure

```
qupboard_graphql/
├── pyproject.toml                  # Project metadata and dependencies
├── alembic.ini                     # Alembic configuration
├── alembic/
│   ├── env.py                      # Migration environment (wired to ORM models)
│   └── versions/                   # Generated migration scripts
├── qupboard.db                     # Default SQLite database
├── src/
│   └── qupboard_graphql/
│       ├── main.py                 # Entrypoint – starts uvicorn on 0.0.0.0:8000
│       ├── config.py               # Pydantic settings (DATABASE_URL, API paths)
        ├── api/
        │   ├── app.py              # FastAPI application factory
        │   ├── graphql_types.py    # Strawberry type declarations (mapper + @mapper.type classes)
        │   ├── graphql.py          # Query resolvers, schema, and GraphQL router
        │   └── rest.py             # REST router (CRUD for hardware models)
        ├── db/
        │   ├── database.py         # SQLAlchemy DeclarativeBase
        │   ├── repository.py       # RepositoryMixin (get_by_uuid, get_all_pks)
        │   ├── models.py           # ORM models mirroring the hardware model schema
        │   ├── mapper.py           # ORM ↔ Pydantic conversion helpers
        │   └── session.py          # Engine, SessionLocal, and get_db dependency
│       └── schemas/
│           └── hardware_model.py   # Pydantic schema for HardwareModel
└── tests/
    ├── conftest.py
    ├── test_graphql.py
    ├── test_rest.py
    └── data/                       # Sample calibration JSON fixtures
```

---

## Example Queries

### GraphQL

The GraphQL API is available at `/graphql`. An interactive GraphiQL IDE is served at the same path in a browser.

**Fetch a calibration by ID**

```graphql
{
  getCalibration(id: "d8b81172-fb8d-43f7-92dd-aff4dbc1defb") {
    id
    version
    calibrationId
    logicalConnectivity
    qubits {
      edges {
        node {
          uuid
          qubitKey
          meanZMapArgs
          discriminatorReal
          discriminatorImag
          directXPi
          phaseCompXPi2
          resUuid
          physicalChannels {
            edges {
              node {
                uuid
                channelKind
                nameIndex
                blockSize
                defaultAmplitude
                switchBox
                swapReadoutIq
                basebandUuid
                basebandFrequency
                basebandIfFrequency
                iqBias
              }
            }
          }
          pulseChannels {
            edges {
              node {
                uuid
                channelRole
                frequency
                imbalance
                phaseIqOffset
                scaleReal
                scaleImag
                ssActive
                ssDelay
                fsActive
                fsAmp
                fsPhase
                acqDelay
                acqWidth
                acqSync
                acqUseWeights
                resetDelay
                pulse {
                  id
                  waveformType
                  width
                  amp
                  phase
                  drag
                  rise
                  ampSetup
                  stdDev
                }
                pulseXPi {
                  id
                  waveformType
                  width
                }
              }
            }
          }
          crossResonanceChannels {
            edges {
              node {
                uuid
                role
                auxiliaryQubit
                frequency
                imbalance
                phaseIqOffset
                scaleReal
                scaleImag
                zxPi4Pulse {
                  id
                  waveformType
                  width
                }
              }
            }
          }
          crossResonanceCancellationChannels {
            edges {
              node {
                uuid
                role
                auxiliaryQubit
                frequency
                imbalance
                phaseIqOffset
                scaleReal
                scaleImag
              }
            }
          }
          zxPi4Comps {
            edges {
              node {
                uuid
                auxiliaryQubit
                phaseCompTargetZxPi4
                pulseZxPi4TargetRotaryAmp
                precompActive
                postcompActive
                useSecondState
                useRotary
                pulsePrecomp {
                  id
                  waveformType
                  width
                }
                pulsePostcomp {
                  id
                  waveformType
                  width
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

**List all stored hardware model IDs**

```graphql
{
  getAllHardwareModelIds
}
```

---

### REST

The REST API is available at `/rest`. Interactive OpenAPI docs are served at `/docs`.

| Method | Path                            | Description                                        |
|--------|---------------------------------|----------------------------------------------------|
| `GET`  | `/healthcheck`                  | Health check – returns `OK`                        |
| `GET`  | `/rest/logical-hardware`        | List all hardware model UUIDs                      |
| `GET`  | `/rest/logical-hardware/{uuid}` | Fetch a hardware model by UUID                     |
| `POST` | `/rest/logical-hardware`        | Create a hardware model from a JSON body           |
| `POST` | `/rest/logical-hardware/upload` | Create a hardware model from an uploaded JSON file |

**List all hardware model IDs**

```bash
curl http://localhost:8000/rest/logical-hardware
```

**Fetch a specific hardware model**

```bash
curl http://localhost:8000/rest/logical-hardware/92f4847b-4df2-4c04-9fbc-18c9228b78ab
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

---

## Database Implementation

### Schema

The database schema mirrors the `HardwareModel` Pydantic schema and is defined as SQLAlchemy ORM models in `src/qupboard_graphql/db/models.py`. The table hierarchy is:

```
hardware_models
└── qubits
    ├── physical_channels      (channel_kind = 'qubit' | 'resonator'; baseband + IQ-bias inlined)
    ├── pulse_channels         (channel_role discriminator; replaces 4 separate tables)
    │   channel_role values:
    │     'drive'            – qubit drive channel
    │     'second_state'     – second-state channel (ss_active, ss_delay)
    │     'freq_shift'       – freq-shift channel   (fs_active, fs_amp, fs_phase)
    │     'measure'          – resonator measure channel
    │     'acquire'          – resonator acquire channel (acq_delay/width/sync/use_weights)
    │     'reset_qubit'      – qubit reset channel   (reset_delay)
    │     'reset_resonator'  – resonator reset channel (reset_delay)
    │   └── calibratable_pulses (owner_uuid + pulse_role discriminator)
    ├── cross_resonance_channels (role = 'cr' | 'crc')
    │   └── calibratable_pulses  (pulse_role = 'cr')
    ├── phase_comp_x_pi_2        (inlined column on qubits)
    ├── res_uuid                 (resonator UUID inlined on qubits)
    └── zx_pi_4_comps            (one per CR pair)
        └── calibratable_pulses  (pulse_role = 'zx_precomp' | 'zx_postcomp', nullable)
```

The database URL defaults to `sqlite:///./qupboard.db` and can be overridden with the `DATABASE_URL` environment variable.

### Migrations with Alembic

Schema migrations are managed with [Alembic](https://alembic.sqlalchemy.org/). The Alembic project lives at the **project root**:

```
alembic.ini          # Alembic configuration
alembic/
├── env.py           # Wired to ORM Base metadata and app settings
└── versions/        # Migration scripts
```

`env.py` automatically reads `DATABASE_URL` from the application settings, so no manual URL configuration is required. `render_as_batch=True` is enabled to support SQLite's limited `ALTER TABLE` capabilities.

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

**Stamp an existing database without running migrations** (useful when the schema was created outside of Alembic)

```bash
poetry run alembic stamp head
```
