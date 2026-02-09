# adc-mvp
Accident Defense Command - MVP

## Project Structure

```
adc-mvp/
├── backend/
│   ├── app/
│   │   ├── main.py                  # FastAPI entry point
│   │   ├── api/
│   │   │   ├── routes_incidents.py  # Incident API routes
│   │   │   ├── routes_exports.py    # Export API routes
│   │   │   └── routes_auth.py       # Auth API routes
│   │   ├── core/
│   │   │   ├── config.py            # Application configuration
│   │   │   ├── security.py          # Security utilities
│   │   │   └── logging.py           # Logging setup
│   │   ├── db/
│   │   │   ├── session.py           # Database session management
│   │   │   ├── models.py            # SQLAlchemy models
│   │   │   └── migrations/          # Alembic migrations
│   │   ├── services/
│   │   │   ├── samsara_client.py    # Samsara API client
│   │   │   ├── normalizers/         # Data normalizers (ELD, GPS, etc.)
│   │   │   ├── schema_validate.py   # Schema validation service
│   │   │   ├── vault_s3.py          # S3 storage service
│   │   │   └── export_builder.py    # Export builder service
│   │   ├── tasks/
│   │   │   ├── celery_app.py        # Celery configuration
│   │   │   ├── evidence_tasks.py    # Evidence collection tasks
│   │   │   └── export_tasks.py      # Export generation tasks
│   │   └── domain/
│   │       ├── event_types.py       # Event type definitions
│   │       └── evidence_types.py    # Evidence type definitions
│   ├── tests/                       # Backend test suite (pytest)
│   ├── examples/                    # Sample API payloads
│   └── requirements.txt
├── frontend/                        # Next.js UI
│   ├── app/                         # Next.js app router pages
│   ├── components/                  # React components
│   └── lib/                         # Client-side utilities
├── contracts/
│   └── schemas/                     # JSON schemas (single source of truth)
├── infra/
│   └── docker-compose.yml           # Docker Compose stack
├── scripts/                         # Utility scripts
├── docs/                            # Documentation
├── Makefile                         # Dev commands (make dev/test/fmt)
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

### Local Development (manual)

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Docker

```bash
docker-compose -f infra/docker-compose.yml up --build
```

- API: `http://localhost:8000`
- Frontend: `http://localhost:3000`
