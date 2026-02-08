"""FastAPI application entry point."""

from fastapi import FastAPI

from app.api.routes_incidents import router as incidents_router
from app.api.routes_exports import router as exports_router
from app.core.config import settings

app = FastAPI(title="ADC MVP", version="0.1.0")

app.include_router(incidents_router, prefix="/incidents", tags=["incidents"])
app.include_router(exports_router, prefix="/exports", tags=["exports"])


@app.get("/health")
async def health_check():
    return {"status": "ok"}
