"""
NOVA Audit Trail API.

Read-only API surface for the persistent application-level audit trail.

Routes:
    GET /api/audit
    GET /api/audit/summary
    GET /api/audit/{event_id}
    GET /api/audit/export/json
    GET /api/audit/export/csv

There is intentionally no delete route for audit records.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from app.services.audit.service import audit_service


router = APIRouter(
    prefix="/api/audit",
    tags=["audit"],
)


# ---------------------------------------------------------------------------
# AUDIT EVENTS
# ---------------------------------------------------------------------------


@router.get("")
async def get_audit_events(
    query: Optional[str] = Query(
        default=None,
        description="Free-text search across audit event fields.",
    ),
    category: Optional[str] = Query(
        default=None,
        description="Exact audit category filter.",
    ),
    action: Optional[str] = Query(
        default=None,
        description="Exact audit action filter.",
    ),
    service: Optional[str] = Query(
        default=None,
        description="Exact service filter.",
    ),
    status: Optional[str] = Query(
        default=None,
        description="Exact status filter.",
    ),
    model: Optional[str] = Query(
        default=None,
        description="Model name filter.",
    ),
    task_type: Optional[str] = Query(
        default=None,
        description="Exact task type filter.",
    ),
    start_time: Optional[str] = Query(
        default=None,
        description="Inclusive ISO timestamp lower bound.",
    ),
    end_time: Optional[str] = Query(
        default=None,
        description="Inclusive ISO timestamp upper bound.",
    ),
    limit: int = Query(
        default=100,
        ge=1,
        le=1000,
        description="Maximum number of events to return.",
    ),
    offset: int = Query(
        default=0,
        ge=0,
        description="Number of matching events to skip.",
    ),
):
    """
    Return real persisted audit events.

    Results are newest-first.
    """

    return audit_service.list_events(
        query=query,
        category=category,
        action=action,
        service=service,
        status=status,
        model=model,
        task_type=task_type,
        start_time=start_time,
        end_time=end_time,
        limit=limit,
        offset=offset,
    )


# ---------------------------------------------------------------------------
# SUMMARY
# ---------------------------------------------------------------------------


@router.get("/summary")
async def get_audit_summary():
    """
    Return aggregate information over the actual persisted audit trail.
    """

    return {
        "summary": audit_service.summary(),
    }


# ---------------------------------------------------------------------------
# SINGLE EVENT
# ---------------------------------------------------------------------------


@router.get("/{event_id}")
async def get_audit_event(
    event_id: str,
):
    """
    Return one persisted audit event by event ID.
    """

    event = audit_service.get_event(
        event_id
    )

    if event is None:
        raise HTTPException(
            status_code=404,
            detail="Audit event not found.",
        )

    return {
        "event": event,
    }


# ---------------------------------------------------------------------------
# JSON EXPORT
# ---------------------------------------------------------------------------


@router.get("/export/json")
async def export_audit_json(
    query: Optional[str] = Query(default=None),
    category: Optional[str] = Query(default=None),
    action: Optional[str] = Query(default=None),
    service: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    model: Optional[str] = Query(default=None),
    task_type: Optional[str] = Query(default=None),
    start_time: Optional[str] = Query(default=None),
    end_time: Optional[str] = Query(default=None),
):
    """
    Export the filtered audit events as JSON.
    """

    content = audit_service.export_json(
        query=query,
        category=category,
        action=action,
        service=service,
        status=status,
        model=model,
        task_type=task_type,
        start_time=start_time,
        end_time=end_time,
    )

    return Response(
        content=content,
        media_type="application/json",
        headers={
            "Content-Disposition": (
                'attachment; filename="nova-audit.json"'
            ),
        },
    )


# ---------------------------------------------------------------------------
# CSV EXPORT
# ---------------------------------------------------------------------------


@router.get("/export/csv")
async def export_audit_csv(
    query: Optional[str] = Query(default=None),
    category: Optional[str] = Query(default=None),
    action: Optional[str] = Query(default=None),
    service: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    model: Optional[str] = Query(default=None),
    task_type: Optional[str] = Query(default=None),
    start_time: Optional[str] = Query(default=None),
    end_time: Optional[str] = Query(default=None),
):
    """
    Export the filtered audit events as CSV.
    """

    content = audit_service.export_csv(
        query=query,
        category=category,
        action=action,
        service=service,
        status=status,
        model=model,
        task_type=task_type,
        start_time=start_time,
        end_time=end_time,
    )

    return Response(
        content=content,
        media_type="text/csv",
        headers={
            "Content-Disposition": (
                'attachment; filename="nova-audit.csv"'
            ),
        },
    )


__all__ = [
    "router",
]