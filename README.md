# adc-mvp
Accident Defense Command - MVP

## Project Structure

```
adc-mvp/
├── contracts/
│   └── schemas/                 # JSON schemas for data contracts
├── app/
│   ├── main.py                  # FastAPI entry point
│   ├── api/
│   │   ├── routes_incidents.py  # Incident API routes
│   │   └── routes_exports.py    # Export API routes
│   ├── core/
│   │   ├── config.py            # Application configuration
│   │   └── logging.py           # Logging setup
│   ├── db/
│   │   ├── session.py           # Database session management
│   │   ├── models.py            # SQLAlchemy models
│   │   ├── migrations/          # Alembic migrations
│   │   ├── repo_events.py       # Events repository
│   │   ├── repo_incidents.py    # Incidents repository
│   │   ├── repo_artifacts.py    # Artifacts repository
│   │   └── repo_exports.py      # Exports repository
│   ├── services/
│   │   ├── samsara_client.py    # Samsara API client
│   │   ├── normalizers/
│   │   │   ├── eld.py           # ELD data normalizer
│   │   │   ├── gps.py           # GPS data normalizer
│   │   │   ├── safety_events.py # Safety events normalizer
│   │   │   └── vehicle_state.py # Vehicle state normalizer
│   │   ├── schema_validate.py   # Schema validation service
│   │   ├── vault_s3.py          # S3 storage service
│   │   ├── pdf_render.py        # PDF rendering service
│   │   └── export_builder.py    # Export builder service
│   ├── tasks/
│   │   ├── celery_app.py        # Celery configuration
│   │   ├── evidence_tasks.py    # Evidence collection tasks
│   │   └── export_tasks.py      # Export generation tasks
│   └── domain/
│       ├── event_types.py       # Event type definitions
│       └── evidence_types.py    # Evidence type definitions
├── docker-compose.yml
├── requirements.txt
└── README.md
```

## Getting Started

### Prerequisites

- Python 3.11+
- PostgreSQL 15+
- Redis 7+

### Local Development

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Docker

```bash
docker-compose up --build
```

The API will be available at `http://localhost:8000`.
