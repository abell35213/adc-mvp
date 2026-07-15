.PHONY: dev local-up local-down local-logs local-ps local-rebuild local-wait-db local-wait-api local-migrate local-seed local-verify-demo local-smoke local-reset local-bootstrap test fmt lint guard-duplicates check-prod-hardening-gates check-hardening-matrix verify-demo


LOCAL_COMPOSE = docker compose -f infra/docker-compose.local.yml
LOCAL_API_URL ?= http://localhost:8000

## Start the local-only Docker stack (Postgres, Redis, API, worker, frontend).
local-up:
	$(LOCAL_COMPOSE) up -d --build

## Stop the local-only Docker stack without deleting local volumes.
local-down:
	$(LOCAL_COMPOSE) down

## Tail logs from the local-only Docker stack.
local-logs:
	$(LOCAL_COMPOSE) logs -f

## Show local-only Docker stack service status.
local-ps:
	$(LOCAL_COMPOSE) ps

## Rebuild and restart the local-only Docker stack.
local-rebuild:
	$(LOCAL_COMPOSE) up -d --build --force-recreate

## Wait until the local-only Postgres container is healthy.
local-wait-db:
	@echo "Waiting for local Postgres..."
	@for i in $$(seq 1 60); do \
		if $(LOCAL_COMPOSE) exec -T db pg_isready -U $${POSTGRES_USER:-adc_local} -d $${POSTGRES_DB:-adc_mvp} >/dev/null 2>&1; then \
			echo "Local Postgres is ready."; \
			exit 0; \
		fi; \
		sleep 2; \
	done; \
	echo "Timed out waiting for local Postgres." >&2; \
	exit 1

## Wait until the local-only API readiness endpoint is healthy.
local-wait-api:
	@echo "Waiting for local API at $(LOCAL_API_URL)/health..."
	@for i in $$(seq 1 90); do \
		if curl --fail --silent --show-error "$(LOCAL_API_URL)/health" >/dev/null 2>&1; then \
			echo "Local API is ready."; \
			exit 0; \
		fi; \
		sleep 2; \
	done; \
	echo "Timed out waiting for local API." >&2; \
	exit 1

## Run Alembic migrations against local-only Docker Postgres from the backend container.
local-migrate: local-wait-db
	$(LOCAL_COMPOSE) run --rm api alembic -c alembic.ini upgrade head

## Seed the local-only Docker Postgres database with the deterministic demo tenant.
local-seed: local-wait-db
	$(LOCAL_COMPOSE) run --rm -e PYTHONPATH=/app api python /scripts/seed_demo_data.py

## Verify seeded local demo data and the live incident-to-export workflow.
## Requires the local worker included in `make local-up` for async export readiness.
local-verify-demo: local-wait-api
	$(LOCAL_COMPOSE) run --rm -e PYTHONPATH=/app -e DEMO_API_BASE_URL=http://api:8000 api python /scripts/verify_demo.py --local-db

## Smoke-test the seeded demo workflow against the running local-only stack.
local-smoke: local-verify-demo

## Delete local-only containers and volumes. This removes local Postgres/vault data only.
local-reset:
	$(LOCAL_COMPOSE) down --volumes --remove-orphans

## Start local services, migrate, seed demo data, and verify the local demo tenant.
local-bootstrap:
	$(LOCAL_COMPOSE) up -d --build
	$(MAKE) local-wait-db
	$(MAKE) local-migrate
	$(MAKE) local-wait-api
	$(MAKE) local-seed
	$(MAKE) local-verify-demo
	@echo "Local bootstrap complete. Frontend: http://localhost:3000 Backend: $(LOCAL_API_URL) Demo login: demo-admin@adc.local / DemoAdmin!2345"

## Start all services (infra + backend + worker + frontend) from repo root
## Uses docker compose (plugin-style command)
dev:
	docker compose -f infra/docker-compose.yml up --build

## Run backend tests and contract validation from repo root
test:
	python scripts/check_no_duplicate_modules.py
	cd backend && pip install -q -r requirements.txt && APP_ENV=test python -m pytest tests/ -q --durations=20
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
