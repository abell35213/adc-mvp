"""FastAPI application entry point."""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes_auth import router as auth_router
from app.api.routes_driver_auth import router as driver_auth_router
from app.api.routes_incidents import router as incidents_router
from app.api.routes_exports import router as exports_router
from app.api.routes_driver import router as driver_router
from app.api.routes_integrations import router as integrations_router
from app.api.routes.routes_driver_artifacts import router as driver_artifacts_router
from app.api.routes.routes_driver_report import router as driver_report_router
from app.api.routes_admin import router as admin_router
from app.api.routes_twilio import router as twilio_router
from app.health.routes import router as health_router
from app.core.config import settings
from app.config.validation import validate_startup_config
from app.observability.alerts import init_sentry
from app.observability.logging import RequestContextMiddleware, setup_logging

logger = logging.getLogger(__name__)

app = FastAPI(title="ADC MVP", version="0.1.0", debug=settings.DEBUG)

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
app.include_router(admin_router, prefix="/admin", tags=["admin"])
app.include_router(twilio_router, prefix="/twilio", tags=["twilio"])
app.include_router(integrations_router, tags=["integrations"])
app.include_router(health_router)


@app.on_event("startup")
async def validate_startup_configuration() -> None:
    """Fail fast if environment invariants are broken."""

    validate_startup_config(settings)
    init_sentry(service="api")
    logger.info("startup_complete", extra={"deploy_version": settings.RELEASE, "app_env": settings.APP_ENV})
