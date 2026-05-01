.PHONY: dev test fmt lint guard-duplicates check-prod-hardening-gates check-hardening-matrix verify-demo

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
	python scripts/check_hardening_matrix_updates.py

## Ensure no stale duplicate runtime modules reappear
guard-duplicates:
	python scripts/check_no_duplicate_modules.py

## Enforce Priority-1 production hardening gates for production tags
check-prod-hardening-gates:
	python scripts/check_release_hardening_gates.py

## Enforce control-matrix updates when hardening files change
check-hardening-matrix:
	python scripts/check_hardening_matrix_updates.py

## Verify the Phase 4 ``crash_with_full_packet`` demo scenario end-to-end.
## Spins up an in-memory SQLite DB, seeds the scenario, and asserts that
## every Phase 1+2+3 record the guided tour calls out is present and
## well-formed. Offline — no Postgres / Celery / SES / S3 needed.
verify-demo:
cd backend && pip install -q -r requirements.txt
python scripts/verify_demo.py
