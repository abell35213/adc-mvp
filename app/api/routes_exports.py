"""Export API routes."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def list_exports():
    return []


@router.get("/{export_id}")
async def get_export(export_id: int):
    return {"export_id": export_id}
