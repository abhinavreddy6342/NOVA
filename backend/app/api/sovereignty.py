"""
NOVA Sovereignty API

FastAPI endpoints exposing truthful local sovereignty/runtime state.
"""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter

from app.services.sovereignty.service import (
    sovereignty_service,
)


router = APIRouter(
    prefix="/api/sovereignty",
    tags=["Sovereignty"],
)


@router.get(
    "",
    response_model=Dict[str, Any],
)
def get_sovereignty() -> Dict[str, Any]:
    """
    Return the complete current Sovereignty snapshot.
    """

    return sovereignty_service.get_snapshot()


@router.get(
    "/network",
    response_model=Dict[str, Any],
)
def get_network_state() -> Dict[str, Any]:
    """
    Return the application-level network ledger summary.
    """

    snapshot = sovereignty_service.get_snapshot()

    return {
        "timestamp": snapshot["timestamp"],
        "network": snapshot["network"],
    }


@router.get(
    "/verification",
    response_model=Dict[str, Any],
)
def get_verification_state() -> Dict[str, Any]:
    """
    Return the current Sovereignty verification result.
    """

    snapshot = sovereignty_service.get_snapshot()

    return {
        "timestamp": snapshot["timestamp"],
        "verification": snapshot["verification"],
    }