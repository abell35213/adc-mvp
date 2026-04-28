"""FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes_auth import router as auth_router
from app.api.routes_driver_auth import router as driver_auth_router
from app.api.routes_incidents import router as incidents_router
from app.api.routes_exports import router as exports_router
from app.api.routes_driver import router as driver_router
from app.api.routes_onboarding import router as onboarding_router
from app.api.routes_vehicle_imports import router as vehicle_imports_router
from app.api.routes_driver_imports import router as driver_imports_router
from app.api.routes_qr_deployment import router as qr_deployment_router
from app.api.routes_test_runs import router as test_runs_router
from app.api.routes_integrations import router as integrations_router
from app.api.routes.routes_driver_artifacts import router as driver_artifacts_router
from app.api.routes.routes_case_ops import router as case_ops_router
from app.api.routes.routes_notes import router as notes_router
from app.api.routes.routes_driver_report import router as driver_report_router
from app.api.routes.routes_tasks import router as tasks_router
from app.api.routes.routes_demo import router as demo_router
from app.api.routes.routes_entitlements import router as entitlements_router
from app.api.routes.routes_help import router as help_router
from app.api.routes.routes_reporting import router as reporting_router
from app.api.routes.routes_trust import router as trust_router
from app.api.routes.routes_deployment import router as deployment_router
from app.api.routes.routes_webhooks import router as webhooks_router
from app.api.routes_admin import router as admin_router
from app.api.routes_twilio import router as twilio_router
from app.health.routes import router as health_router
from app.core.config import settings
from app.config.validation import validate_startup_config
from app.observability.alerts import init_sentry
from app.observability.logging import RequestContextMiddleware, setup_logging

logger = logging.getLogger(__name__)


@asynccontextmanager
async def _lifespan(_: FastAPI):
    """Validate startup invariants once before serving requests."""

    validate_startup_config(settings)
    init_sentry(service="api")
    logger.info(
        "startup_complete",
        extra={"deploy_version": settings.RELEASE, "app_env": settings.APP_ENV},
    )
    yield


app = FastAPI(
    title="ADC MVP",
    version="0.1.0",
    debug=settings.DEBUG,
    lifespan=_lifespan,
)

setup_logging(settings.LOG_LEVEL)

# CORS — allow the Next.js dev server and any configured origins
app.add_middleware(RequestContextMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_ORIGIN],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(incidents_router, prefix="/incidents", tags=["incidents"])
app.include_router(exports_router, prefix="/exports", tags=["exports"])
app.include_router(driver_auth_router, prefix="/driver/auth", tags=["driver-auth"])
app.include_router(driver_router, prefix="/driver", tags=["driver"])
app.include_router(driver_artifacts_router, prefix="/driver", tags=["driver-artifacts"])
app.include_router(driver_report_router, prefix="/driver", tags=["driver-report"])
app.include_router(case_ops_router, tags=["case-ops"])
app.include_router(notes_router, tags=["notes"])
app.include_router(tasks_router, tags=["tasks"])
app.include_router(demo_router)
app.include_router(entitlements_router)
app.include_router(reporting_router)
app.include_router(help_router)
app.include_router(trust_router)
app.include_router(deployment_router)
app.include_router(webhooks_router, prefix="/webhooks/twilio", tags=["webhooks"])
app.include_router(admin_router, prefix="/admin", tags=["admin"])
app.include_router(twilio_router, prefix="/twilio", tags=["twilio"])
app.include_router(onboarding_router)
app.include_router(test_runs_router)
app.include_router(vehicle_imports_router)
app.include_router(driver_imports_router)
app.include_router(qr_deployment_router)
app.include_router(integrations_router, tags=["integrations"])
app.include_router(health_router)
