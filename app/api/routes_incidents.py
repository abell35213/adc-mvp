"""Incident API routes."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def list_incidents():
    return []


@router.get("/{incident_id}")
async def get_incident(incident_id: int):
    return {"incident_id": incident_id}
