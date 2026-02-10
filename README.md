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
│   │   │   ├── celery_app.py          # Celery configuration
│   │   │   ├── evidence_tasks.py      # Evidence collection tasks
│   │   │   └── export_tasks.py        # Export generation tasks
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
│   └── docker-compose.yml             # Docker Compose stack
├── scripts/                           # Utility scripts
│   ├── create_admin.py                # Create admin user
│   └── validate_schemas.py            # Validate JSON schemas
├── docs/                              # Documentation
├── Makefile                           # Dev commands (make dev/test/fmt)
└── README.md
```

## Getting Started

### Prerequisites

- Python 3.11+
- PostgreSQL 15+
- Redis 7+
- Node.js 18+ (for frontend)

### Quick Start

```bash
# Start everything (backend + worker + frontend + infra)
make dev

# Run tests
make test

# Format / lint
make fmt
```

### Run Everything

Open four terminals and run each command:

```bash
# 1. Start infrastructure (PostgreSQL, Redis, etc.)
docker compose -f infra/docker-compose.yml up -d

# 2. Start the FastAPI backend
uvicorn backend.app.main:app --reload

# 3. Start the Celery worker
celery -A backend.app.tasks.celery_app worker -l info

# 4. Start the Next.js frontend
cd frontend && npm run dev
```

### Driver App (Expo)

```bash
cd driver-app
npm install
EXPO_PUBLIC_API_BASE_URL=http://localhost:8000 npm run start
```

- API: `http://localhost:8000`
- Frontend: `http://localhost:3000`

### Local Development (manual)

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Docker

```bash
docker compose -f infra/docker-compose.yml up --build
```
