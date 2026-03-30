.PHONY: dev test fmt lint

## Start all services (infra + backend + worker + frontend) from repo root
## Uses docker compose (plugin-style command)
dev:
	docker compose -f infra/docker-compose.yml up --build

## Run backend tests and contract validation from repo root
test:
	cd backend && pip install -q -r requirements.txt && pytest tests/ -v
	python scripts/validate_schemas.py

## Format & lint backend code (from repo root)
fmt:
	cd backend && pip install -q ruff && ruff check --fix --unsafe-fixes app/ tests/
	cd backend && ruff format app/ tests/

## Lint only (no auto-fix) from repo root
lint:
	cd backend && pip install -q ruff && ruff check app/ tests/
