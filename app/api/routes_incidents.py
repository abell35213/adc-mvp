"""Incident API routes."""

import uuid

from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def list_incidents():
    return []


@router.get("/{incident_id}")
async def get_incident(incident_id: uuid.UUID):
    return {"incident_id": str(incident_id)}
