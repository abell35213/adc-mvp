.PHONY: dev test fmt lint

## Start all services (infra + backend + worker + frontend)
dev:
	docker-compose -f infra/docker-compose.yml up --build

## Run backend tests and contract validation
test:
	cd backend && pip install -q -r requirements.txt && pytest tests/ -v
	python scripts/validate_schemas.py

## Format & lint backend code
fmt:
	cd backend && pip install -q ruff && ruff check --fix --unsafe-fixes app/ tests/
	cd backend && ruff format app/ tests/

## Lint only (no auto-fix)
lint:
	cd backend && pip install -q ruff && ruff check app/ tests/
