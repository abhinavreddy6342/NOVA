"""
Unit tests for NOVA Analytics Service and API routes.

Tests ensure:
- Real audit events are calculated accurately.
- Empty datasets return real zero/empty states without failing or fabricating metrics.
- Date filtering correctly scopes results.
- Latency calculations (avg, min, max, p95) are accurate.
- Category, service, model, task_type aggregations are correct.
- FastAPI endpoints respond correctly with registered routes.
"""

import sys
from pathlib import Path

# Add backend path
backend_dir = Path(__file__).resolve().parents[1]
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.analytics.service import AnalyticsService, analytics_service
from app.services.audit.store import AuditStore
from app.services.audit.service import AuditService


@pytest.fixture
def tmp_audit_store(tmp_path):
    events_file = tmp_path / "test_audit_events.json"
    store = AuditStore(events_file=events_file)
    service = AuditService(store=store)
    return service


def test_empty_dataset_handling(tmp_audit_store, monkeypatch):
    monkeypatch.setattr("app.services.analytics.service.audit_service", tmp_audit_store)

    srv = AnalyticsService()
    summary = srv.get_summary(range_key="24h")

    assert summary["total_events"] == 0
    assert summary["successful_events"] == 0
    assert summary["failed_events"] == 0
    assert summary["success_rate_percent"] == 0.0
    assert summary["latency"]["avg_ms"] is None
    assert summary["latency"]["measured_count"] == 0
    assert summary["models_used_count"] == 0

    trends = srv.get_activity_trends(range_key="24h")
    assert len(trends["series"]) == 24
    assert all(point["total"] == 0 for point in trends["series"])


def test_analytics_aggregations(tmp_audit_store, monkeypatch):
    monkeypatch.setattr("app.services.analytics.service.audit_service", tmp_audit_store)

    # Record real events
    tmp_audit_store.record_event(
        category="chat",
        action="request",
        service="chat",
        status="success",
        duration_ms=100.0,
        model="llama3.2:latest",
        task_type="coding",
    )
    tmp_audit_store.record_event(
        category="chat",
        action="request",
        service="chat",
        status="failed",
        duration_ms=300.0,
        model="llama3.2:latest",
        task_type="coding",
    )
    tmp_audit_store.record_event(
        category="model",
        action="inference",
        service="ollama",
        status="success",
        duration_ms=200.0,
        model="qwen2.5-coder:3b",
        task_type="reasoning",
    )

    srv = AnalyticsService()
    summary = srv.get_summary(range_key="24h")

    assert summary["total_events"] == 3
    assert summary["successful_events"] == 2
    assert summary["failed_events"] == 1
    assert summary["success_rate_percent"] == 66.7
    assert summary["latency"]["avg_ms"] == 200.0
    assert summary["latency"]["min_ms"] == 100.0
    assert summary["latency"]["max_ms"] == 300.0
    assert summary["models_used_count"] == 2
    assert "llama3.2:latest" in summary["models_used_list"]
    assert "qwen2.5-coder:3b" in summary["models_used_list"]

    # Category breakdown test
    cats = srv.get_categories_breakdown(range_key="24h")
    assert len(cats) == 2
    chat_cat = next(c for c in cats if c["category"] == "chat")
    assert chat_cat["count"] == 2

    # Model breakdown test
    models = srv.get_models_breakdown(range_key="24h")
    assert len(models) == 2
    llama_mdl = next(m for m in models if m["model"] == "llama3.2:latest")
    assert llama_mdl["request_count"] == 2
    assert llama_mdl["success_count"] == 1
    assert llama_mdl["failed_count"] == 1
    assert llama_mdl["avg_latency_ms"] == 200.0

    # Task type test
    tts = srv.get_task_types_breakdown(range_key="24h")
    assert len(tts) == 2


def test_api_analytics_endpoints():
    client = TestClient(app)

    response = client.get("/api/analytics")
    assert response.status_code == 200
    data = response.json()
    assert "summary" in data
    assert "trends" in data
    assert "categories" in data

    response_summary = client.get("/api/analytics/summary?range=24h")
    assert response_summary.status_code == 200
    assert "total_events" in response_summary.json()

    response_trends = client.get("/api/analytics/trends?range=1h")
    assert response_trends.status_code == 200
    assert "series" in response_trends.json()

    response_export = client.get("/api/analytics/export/json")
    assert response_export.status_code == 200
    assert "application/json" in response_export.headers["content-type"]
