# adc-mvp
Accident Defense Command - MVP

## Project Structure

```
adc-mvp/
├── backend/
│   ├── app/
│   │   ├── main.py                    # FastAPI entry point
│   │   ├── api/
│   │   │   ├── routes_incidents.py    # Incident API routes
│   │   │   ├── routes_exports.py      # Export API routes
│   │   │   ├── routes_auth.py         # Auth API routes
│   │   │   └── schemas.py             # Pydantic request/response schemas
│   │   ├── core/
│   │   │   ├── config.py              # Application configuration
│   │   │   ├── security.py            # Security utilities
│   │   │   ├── logging.py             # Logging setup
│   │   │   └── deps.py                # FastAPI dependencies
│   │   ├── db/
│   │   │   ├── session.py             # Database session management
│   │   │   ├── models.py              # SQLAlchemy models
│   │   │   ├── repo/                  # Repository-pattern data access
│   │   │   │   ├── incidents.py
│   │   │   │   ├── events.py
│   │   │   │   ├── artifacts.py
│   │   │   │   ├── exports.py
│   │   │   │   └── users.py
│   │   │   └── migrations/            # Alembic migrations
│   │   ├── services/
│   │   │   ├── samsara_client.py      # Samsara API client
│   │   │   ├── fake_samsara_adapter.py # Fake Samsara adapter for dev/test
│   │   │   ├── normalizers/           # Data normalizers (ELD, GPS, etc.)
│   │   │   ├── schema_validate.py     # Schema validation service
│   │   │   ├── vault_s3.py            # S3 storage service
│   │   │   ├── export_builder.py      # Export builder service
│   │   │   ├── pdf_render.py          # PDF rendering service
│   │   │   └── s3_key_builder.py      # S3 key construction helper
│   │   ├── tasks/
│   │   │   ├── __init__.py            # Tasks package marker
│   │   │   ├── celery_app.py          # Celery app config + task routing/queues
│   │   │   ├── evidence_tasks.py      # Dashcam + telematics evidence ingestion
│   │   │   ├── export_tasks.py        # Export build + persistence/upload tasks
│   │   │   ├── notification_tasks.py  # Safety manager SMS/voice alerts via Twilio
│   │   │   └── notify_tasks.py        # Legacy shim alias for deprecated notify task
│   │   └── domain/
│   │       ├── event_types.py         # Event type definitions
│   │       ├── evidence_types.py      # Evidence type definitions
│   │       └── system_event_types.py  # System event type definitions
│   ├── tests/                         # Backend test suite (pytest)
│   ├── provider_fixtures/
│   │   └── samsara/                   # Sample provider payloads
│   ├── alembic.ini                    # Alembic configuration
│   └── requirements.txt
├── frontend/                          # Next.js UI
│   ├── app/                           # Next.js app router pages
│   │   ├── page.tsx                   # Home page
│   │   ├── layout.tsx                 # Root layout
│   │   ├── login/page.tsx             # Login page
│   │   └── incidents/                 # Incident pages
│   │       ├── page.tsx               # Incident list
│   │       └── [id]/page.tsx          # Incident detail
│   ├── components/                    # React components
│   │   ├── EvidenceTable.tsx
│   │   ├── ExportPanel.tsx
│   │   └── Timeline.tsx
│   ├── lib/                           # Client-side utilities
│   │   ├── api.ts
│   │   ├── auth.ts
│   │   └── useAuth.ts
│   └── package.json
├── driver-app/                        # Expo driver app
│   ├── App.tsx                        # Navigation entry point
│   ├── src/                           # Driver app screens + API
│   └── package.json
├── contracts/
│   └── schemas/                       # JSON schemas (single source of truth)
├── infra/
│   ├── docker-compose.yml             # Docker Compose stack
│   └── production/                    # Production manifests + secret provider refs
├── scripts/                           # Utility scripts
│   ├── create_admin.py                # Create admin user
│   └── validate_schemas.py            # Validate JSON schemas
├── docs/                              # Documentation
├── Makefile                           # Dev commands (make dev/test/fmt)
└── README.md
```


## Runtime package canonical path

The canonical backend runtime package lives at `backend/app`. The top-level `app/` tree is reserved as a non-runtime placeholder to prevent accidental duplicate modules.

## Getting Started

### Prerequisites

- Python 3.11+
- PostgreSQL 15+
- Redis 7+
- Node.js 18+ (for frontend)

### Directory Context (important)

- **From repo root (`adc-mvp/`)**: use commands with `backend.app...` import paths.
- **From `backend/`**: use commands with `app...` import paths.

All commands below call out which directory they assume.

### Quick Start (from repo root)

```bash
# Start everything (backend + worker + frontend + infra)
make dev

# Run backend tests + schema validation
make test

# Lint and format backend code
make fmt
```

### Try the demo locally

After the stack is running you can walk through the seeded demo workflow:

```bash
# 1. Bring the stack up
make dev

# 2. Seed the demo org, ORG_ADMIN user, driver, vehicle, and a scenario
python scripts/seed_demo_data.py

# 3. Open the marketing site and click "Try the demo" in the top nav
#    (or go directly to http://localhost:3000/login?demo=1)
```

The login form is prefilled with the seeded credentials and a sandbox banner
confirms you are entering the demo tenant. After signing in you land on the
dashboard, where a dismissible tour banner shown on load deep-links into the
seeded incident, the Exports page, and the `/demo` workspace where additional
scenarios can be launched.

Default demo credentials (override via env before running the seed script):

| Variable               | Default                  |
|------------------------|--------------------------|
| `DEMO_ADMIN_EMAIL`     | `demo-admin@adc.local`   |
| `DEMO_ADMIN_PASSWORD`  | `DemoAdmin!2345`         |
| `DEMO_ORG`             | `ADC Demo Org`           |

The frontend reads `NEXT_PUBLIC_DEMO_EMAIL` / `NEXT_PUBLIC_DEMO_PASSWORD`
to prefill the login form (see `.env.example`). Demo prefill is opt-in
and **only activates** when both env vars are set at frontend build time
**and** the build is non-production (`NODE_ENV !== "production"`).
Production builds never embed or autofill these credentials, even if a
visitor appends `?demo=1` to the URL.

### Local Docker Development (from repo root)

Use the local-only compose stack for development and pilot demo prep. It starts PostgreSQL, Redis, the FastAPI API, a Celery worker, and the Next.js frontend without AWS credentials, AWS Secrets Manager, staging secrets, Twilio, Samsara, FMCSA, or other live provider credentials.

Fresh local demo bootstrap:

```bash
cp .env.example .env
make local-bootstrap
```

`make local-bootstrap` builds and starts the local containers, waits for Postgres and the API, runs Alembic migrations inside the backend container against the local Compose database, seeds the deterministic demo tenant, and verifies the seeded demo plus API login.

After bootstrap:

```bash
curl http://localhost:8000/health
curl http://localhost:3000
make local-verify-demo
```

Local URLs and ports:

| Service | URL / port | Notes |
| --- | --- | --- |
| Frontend | `http://localhost:3000` | Next.js web app. |
| Backend API | `http://localhost:8000` | FastAPI; readiness is `http://localhost:8000/health`. |
| PostgreSQL | `127.0.0.1:5432` | Local-only Compose database. |
| Redis | `127.0.0.1:6379` | Local-only Compose broker/cache. |

Demo credentials:

| Field | Value |
| --- | --- |
| Demo login email | `demo-admin@adc.local` |
| Demo login password | `DemoAdmin!2345` |
| Demo organization | `ADC Demo Org` |

Local demo commands:

```bash
make local-up           # Start local containers without deleting data
make local-migrate      # Run Alembic migrations against local Postgres
make local-seed         # Idempotently seed/reset the demo tenant and scenario
make local-verify-demo  # Print pass/fail checks for local demo data and login
make local-down         # Stop containers, keep local volumes
make local-reset        # LOCAL ONLY: stop containers and delete local volumes
```

`make local-reset` uses `infra/docker-compose.local.yml` and `docker compose down --volumes --remove-orphans`; it deletes only this local Compose stack's Postgres and vault volumes. It is intentionally separate from staging/production commands.

Common troubleshooting:


Docker Desktop file-sharing troubleshooting (macOS):

- Run the repo from a Docker-shared path. On macOS, prefer the canonical path spelling, for example `/Users/<name>/Documents/adc-mvp`, rather than a lowercase `/users/...` alias or symlinked path.
- If Docker reports `Mounts denied` for the repo or `scripts` directory, add the repo folder or its parent `Documents` folder in Docker Desktop under **Settings → Resources → File Sharing**.
- Restart Docker Desktop after changing file-sharing settings, then rerun `make local-bootstrap`.

- Port `3000` already in use: stop the other frontend/dev server, then rerun `make local-bootstrap` or `make local-up`.
- Port `8000` already in use: stop the other API process/container and rerun `make local-wait-api`; inspect logs with `make local-logs`.
- Port `5432` already in use: stop your host Postgres or change the local Compose port mapping before bootstrapping. The backend container still uses the Compose service hostname `db`.
- Port `6379` already in use: stop your host Redis or change the local Compose port mapping. The backend container still uses the Compose service hostname `redis`.
- API readiness does not pass: run `make local-logs`, then rerun `make local-migrate` and `make local-verify-demo` after the containers are healthy.

The local compose file is `infra/docker-compose.local.yml`. Its backend services run with `APP_ENV=local`, `SECRET_PROVIDER=env`, local Postgres/Redis container URLs, filesystem storage, insecure local-only JWT/OTP secrets, `COOKIE_SECURE=false`, and `FRONTEND_ORIGIN=http://localhost:3000`. Inside compose, the frontend calls the API at `http://api:8000`; from the browser it uses `http://localhost:8000`.

### Manual Development (from repo root)

If you prefer running application processes directly on the host, start local infrastructure first and then run each app process in separate terminals:

```bash
# 1. Start local infrastructure (PostgreSQL, Redis, etc.)
docker compose -f infra/docker-compose.local.yml up -d db redis

# 2. Start the FastAPI backend
cd backend && uvicorn app.main:app --reload

# 3. Start the Celery worker
cd backend && celery -A app.tasks.celery_app worker -l info

# 4. Start the Next.js frontend
cd frontend && npm run dev
```

### Backend-only Manual Development (from backend/)

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Run Tests Manually (from repo root)

Use `python -m pytest` instead of bare `pytest` when running inside the backend `.venv`; this ensures the interpreter and installed packages (for example `boto3`) come from the same environment.

```bash
cd backend && python -m pytest tests/ -v
python scripts/validate_schemas.py
```


### Production secret-loading

Backend runtime settings can be loaded from AWS Secrets Manager by setting:

- `SECRET_PROVIDER=aws_secrets_manager`
- `AWS_SECRETS_MANAGER_SECRET_ID=<secret-name>`
- `AWS_REGION=<region>`

The secret payload should be JSON with setting keys (for example `DATABASE_URL`, `JWT_SECRET_KEY`, `TWILIO_AUTH_TOKEN`).

Reference manifests are in `infra/production/` and use External Secrets to sync secrets from AWS Secrets Manager into Kubernetes.

### Driver App (Expo)

```bash
cd driver-app
npm install
EXPO_PUBLIC_API_BASE_URL=http://localhost:8000 npm run start
```

- API: `http://localhost:8000`
- Frontend: `http://localhost:3000`

See [`driver-app/TESTING.md`](driver-app/TESTING.md) for the test
architecture (unit + RNTL Jest projects), running tests, mocking
conventions, and coverage thresholds.

### Staging-Oriented Docker Compose (from repo root)

The original compose file remains staging-oriented and still expects externally supplied secrets such as AWS Secrets Manager configuration. For normal local development, use `make local-up` instead.

```bash
docker compose -f infra/docker-compose.yml up --build
```
