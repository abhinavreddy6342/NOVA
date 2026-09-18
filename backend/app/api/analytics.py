"""
NOVA Analytics Center API.

Read-only API surface exposing real operational intelligence metrics.

Routes:
    GET /api/analytics
    GET /api/analytics/summary
    GET /api/analytics/trends
    GET /api/analytics/categories
    GET /api/analytics/services
    GET /api/analytics/models
    GET /api/analytics/task-types
    GET /api/analytics/statuses
    GET /api/analytics/latency
    GET /api/analytics/missions
    GET /api/analytics/knowledge
    GET /api/analytics/artifacts
    GET /api/analytics/network
    GET /api/analytics/resources
    GET /api/analytics/recent
    GET /api/analytics/top-actions
    GET /api/analytics/export/json
    GET /api/analytics/export/csv
"""

from __future__ import annotations

import json
from typing import Optional

from fastapi import APIRouter, Query
from fastapi.responses import Response

from app.services.analytics.service import analytics_service
from app.services.audit.service import audit_service

router = APIRouter(
    prefix="/api/analytics",
    tags=["analytics"],
)


@router.get("")
async def get_full_analytics(
    range_key: str = Query(default="24h", alias="range"),
    query: Optional[str] = Query(default=None),
    category: Optional[str] = Query(default=None),
    service: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    model: Optional[str] = Query(default=None),
    task_type: Optional[str] = Query(default=None),
    custom_start: Optional[str] = Query(default=None, alias="start"),
    custom_end: Optional[str] = Query(default=None, alias="end"),
):
    """
    Return the complete operational intelligence dashboard snapshot.
    """
    return analytics_service.get_full_dashboard(
        range_key=range_key,
        query=query,
        category=category,
        service=service,
        status=status,
        model=model,
        task_type=task_type,
        custom_start=custom_start,
        custom_end=custom_end,
    )


@router.get("/summary")
async def get_analytics_summary(
    range_key: str = Query(default="24h", alias="range"),
    query: Optional[str] = Query(default=None),
    category: Optional[str] = Query(default=None),
    service: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    model: Optional[str] = Query(default=None),
    task_type: Optional[str] = Query(default=None),
    custom_start: Optional[str] = Query(default=None, alias="start"),
    custom_end: Optional[str] = Query(default=None, alias="end"),
):
    """
    Return high-level summary KPIs.
    """
    return analytics_service.get_summary(
        range_key=range_key,
        query=query,
        category=category,
        service=service,
        status=status,
        model=model,
        task_type=task_type,
        custom_start=custom_start,
        custom_end=custom_end,
    )


@router.get("/trends")
async def get_analytics_trends(
    range_key: str = Query(default="24h", alias="range"),
    query: Optional[str] = Query(default=None),
    category: Optional[str] = Query(default=None),
    service: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    model: Optional[str] = Query(default=None),
    task_type: Optional[str] = Query(default=None),
    custom_start: Optional[str] = Query(default=None, alias="start"),
    custom_end: Optional[str] = Query(default=None, alias="end"),
):
    """
    Return time-series activity trend dataset.
    """
    return analytics_service.get_activity_trends(
        range_key=range_key,
        query=query,
        category=category,
        service=service,
        status=status,
        model=model,
        task_type=task_type,
        custom_start=custom_start,
        custom_end=custom_end,
    )


@router.get("/categories")
async def get_analytics_categories(
    range_key: str = Query(default="24h", alias="range"),
    query: Optional[str] = Query(default=None),
    custom_start: Optional[str] = Query(default=None, alias="start"),
    custom_end: Optional[str] = Query(default=None, alias="end"),
):
    """
    Return category breakdown.
    """
    return {
        "categories": analytics_service.get_categories_breakdown(
            range_key=range_key, query=query, custom_start=custom_start, custom_end=custom_end
        )
    }


@router.get("/services")
async def get_analytics_services(
    range_key: str = Query(default="24h", alias="range"),
    query: Optional[str] = Query(default=None),
    custom_start: Optional[str] = Query(default=None, alias="start"),
    custom_end: Optional[str] = Query(default=None, alias="end"),
):
    """
    Return service breakdown.
    """
    return {
        "services": analytics_service.get_services_breakdown(
            range_key=range_key, query=query, custom_start=custom_start, custom_end=custom_end
        )
    }


@router.get("/models")
async def get_analytics_models(
    range_key: str = Query(default="24h", alias="range"),
    query: Optional[str] = Query(default=None),
    custom_start: Optional[str] = Query(default=None, alias="start"),
    custom_end: Optional[str] = Query(default=None, alias="end"),
):
    """
    Return model usage analytics.
    """
    return {
        "models": analytics_service.get_models_breakdown(
            range_key=range_key, query=query, custom_start=custom_start, custom_end=custom_end
        )
    }


@router.get("/task-types")
async def get_analytics_task_types(
    range_key: str = Query(default="24h", alias="range"),
    query: Optional[str] = Query(default=None),
    custom_start: Optional[str] = Query(default=None, alias="start"),
    custom_end: Optional[str] = Query(default=None, alias="end"),
):
    """
    Return task type breakdown.
    """
    return {
        "task_types": analytics_service.get_task_types_breakdown(
            range_key=range_key, query=query, custom_start=custom_start, custom_end=custom_end
        )
    }


@router.get("/statuses")
async def get_analytics_statuses(
    range_key: str = Query(default="24h", alias="range"),
    query: Optional[str] = Query(default=None),
    custom_start: Optional[str] = Query(default=None, alias="start"),
    custom_end: Optional[str] = Query(default=None, alias="end"),
):
    """
    Return status breakdown.
    """
    return {
        "statuses": analytics_service.get_statuses_breakdown(
            range_key=range_key, query=query, custom_start=custom_start, custom_end=custom_end
        )
    }


@router.get("/latency")
async def get_analytics_latency(
    range_key: str = Query(default="24h", alias="range"),
    query: Optional[str] = Query(default=None),
    custom_start: Optional[str] = Query(default=None, alias="start"),
    custom_end: Optional[str] = Query(default=None, alias="end"),
):
    """
    Return latency and performance metrics.
    """
    return analytics_service.get_latency_analytics(
        range_key=range_key, query=query, custom_start=custom_start, custom_end=custom_end
    )


@router.get("/missions")
async def get_analytics_missions(
    range_key: str = Query(default="24h", alias="range"),
    custom_start: Optional[str] = Query(default=None, alias="start"),
    custom_end: Optional[str] = Query(default=None, alias="end"),
):
    """
    Return mission and agent execution analytics.
    """
    return analytics_service.get_missions_analytics(
        range_key=range_key, custom_start=custom_start, custom_end=custom_end
    )


@router.get("/knowledge")
async def get_analytics_knowledge(
    range_key: str = Query(default="24h", alias="range"),
    custom_start: Optional[str] = Query(default=None, alias="start"),
    custom_end: Optional[str] = Query(default=None, alias="end"),
):
    """
    Return knowledge vault activity analytics.
    """
    return analytics_service.get_knowledge_analytics(
        range_key=range_key, custom_start=custom_start, custom_end=custom_end
    )


@router.get("/artifacts")
async def get_analytics_artifacts(
    range_key: str = Query(default="24h", alias="range"),
    custom_start: Optional[str] = Query(default=None, alias="start"),
    custom_end: Optional[str] = Query(default=None, alias="end"),
):
    """
    Return artifact generation analytics.
    """
    return analytics_service.get_artifacts_analytics(
        range_key=range_key, custom_start=custom_start, custom_end=custom_end
    )


@router.get("/network")
async def get_analytics_network():
    """
    Return application network tracking analytics.
    """
    return analytics_service.get_network_analytics()


@router.get("/resources")
async def get_analytics_resources():
    """
    Return real system telemetry and resource state.
    """
    return analytics_service.get_resource_analytics()


@router.get("/recent")
async def get_analytics_recent(
    limit: int = Query(default=20, ge=1, le=100),
    query: Optional[str] = Query(default=None),
    category: Optional[str] = Query(default=None),
    service: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    model: Optional[str] = Query(default=None),
    task_type: Optional[str] = Query(default=None),
    custom_start: Optional[str] = Query(default=None, alias="start"),
    custom_end: Optional[str] = Query(default=None, alias="end"),
):
    """
    Return recent activity feed.
    """
    return {
        "recent_activity": analytics_service.get_recent_activity(
            limit=limit,
            query=query,
            category=category,
            service=service,
            status=status,
            model=model,
            task_type=task_type,
            custom_start=custom_start,
            custom_end=custom_end,
        )
    }


@router.get("/top-actions")
async def get_analytics_top_actions(
    limit: int = Query(default=10, ge=1, le=50),
    range_key: str = Query(default="24h", alias="range"),
    query: Optional[str] = Query(default=None),
    custom_start: Optional[str] = Query(default=None, alias="start"),
    custom_end: Optional[str] = Query(default=None, alias="end"),
):
    """
    Return top frequent operations.
    """
    return {
        "top_actions": analytics_service.get_top_actions(
            limit=limit,
            range_key=range_key,
            query=query,
            custom_start=custom_start,
            custom_end=custom_end,
        )
    }


@router.get("/export/json")
async def export_analytics_json(
    range_key: str = Query(default="24h", alias="range"),
    query: Optional[str] = Query(default=None),
    category: Optional[str] = Query(default=None),
    service: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    model: Optional[str] = Query(default=None),
    task_type: Optional[str] = Query(default=None),
    custom_start: Optional[str] = Query(default=None, alias="start"),
    custom_end: Optional[str] = Query(default=None, alias="end"),
):
    """
    Export current analytics snapshot as JSON download.
    """
    data = analytics_service.get_full_dashboard(
        range_key=range_key,
        query=query,
        category=category,
        service=service,
        status=status,
        model=model,
        task_type=task_type,
        custom_start=custom_start,
        custom_end=custom_end,
    )
    content = json.dumps(data, indent=2, ensure_ascii=False)
    return Response(
        content=content,
        media_type="application/json",
        headers={
            "Content-Disposition": 'attachment; filename="nova-analytics.json"',
        },
    )


@router.get("/export/csv")
async def export_analytics_csv(
    range_key: str = Query(default="24h", alias="range"),
    query: Optional[str] = Query(default=None),
    category: Optional[str] = Query(default=None),
    service: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    model: Optional[str] = Query(default=None),
    task_type: Optional[str] = Query(default=None),
    custom_start: Optional[str] = Query(default=None, alias="start"),
    custom_end: Optional[str] = Query(default=None, alias="end"),
):
    """
    Export underlying filtered events as CSV via audit export.
    """
    start_dt, end_dt, _ = analytics_service.resolve_date_range(
        range_key, custom_start, custom_end
    )
    start_str = start_dt.isoformat().replace("+00:00", "Z") if start_dt else None
    end_str = end_dt.isoformat().replace("+00:00", "Z") if end_dt else None

    content = audit_service.export_csv(
        query=query,
        category=category,
        service=service,
        status=status,
        model=model,
        task_type=task_type,
        start_time=start_str,
        end_time=end_str,
    )
    return Response(
        content=content,
        media_type="text/csv",
        headers={
            "Content-Disposition": 'attachment; filename="nova-analytics-events.csv"',
        },
    )


__all__ = ["router"]
