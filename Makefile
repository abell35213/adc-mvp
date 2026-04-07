.PHONY: dev test fmt lint guard-duplicates check-prod-hardening-gates

## Start all services (infra + backend + worker + frontend) from repo root
## Uses docker compose (plugin-style command)
dev:
	docker compose -f infra/docker-compose.yml up --build

## Run backend tests and contract validation from repo root
test:
	python scripts/check_no_duplicate_modules.py
	cd backend && pip install -q -r requirements.txt && pytest tests/ -v
	python scripts/validate_schemas.py

## Format & lint backend code (from repo root)
fmt:
	cd backend && pip install -q ruff && ruff check --fix --unsafe-fixes app/ tests/
	cd backend && ruff format app/ tests/

## Lint only (no auto-fix) from repo root
lint:
	cd backend && pip install -q ruff && ruff check app/ tests/

## Ensure no stale duplicate runtime modules reappear
guard-duplicates:
	python scripts/check_no_duplicate_modules.py

## Enforce Priority-1 production hardening gates for production tags
check-prod-hardening-gates:
	python scripts/check_release_hardening_gates.py
