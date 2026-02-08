"""Export API routes."""

import uuid

from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def list_exports():
    return []


@router.get("/{export_id}")
async def get_export(export_id: uuid.UUID):
    return {"export_id": str(export_id)}
