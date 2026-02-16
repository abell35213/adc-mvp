"""FastAPI application entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes_auth import router as auth_router
from app.api.routes_driver_auth import router as driver_auth_router
from app.api.routes_incidents import router as incidents_router
from app.api.routes_exports import router as exports_router
from app.api.routes_driver import router as driver_router
from app.api.routes_admin import router as admin_router
from app.api.routes_twilio import router as twilio_router
from app.core.config import settings

app = FastAPI(title="ADC MVP", version="0.1.0", debug=settings.DEBUG)

# CORS — allow the Next.js dev server and any configured origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_ORIGIN],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(incidents_router, prefix="/incidents", tags=["incidents"])
app.include_router(exports_router, prefix="/api/exports", tags=["exports"])
app.include_router(driver_auth_router, prefix="/driver/auth", tags=["driver-auth"])
app.include_router(driver_router, prefix="/driver", tags=["driver"])
app.include_router(admin_router, prefix="/admin", tags=["admin"])
app.include_router(twilio_router, prefix="/twilio", tags=["twilio"])

@app.get("/health")
async def health_check():
    return {"status": "ok"}
