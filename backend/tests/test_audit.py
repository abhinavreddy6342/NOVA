from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Iterable, Tuple

import pytest

from app.main import app
from app.services.audit import store as audit_store_module
from app.services.audit.service import (
    audit_service,
    create_event_id,
    create_request_id,
)


# ============================================================================
# TEST STORE ISOLATION
# ============================================================================

@pytest.fixture()
def isolated_audit_store(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    """
    Redirect the existing global AuditStore instance to a temporary file.

    IMPORTANT:
    The production global `audit_store` object stores its active file path
    on the instance itself as `events_file`. Patching only AUDIT_EVENTS_FILE
    is not enough because the global object has already been constructed.
    """

    audit_root = tmp_path / "audit"
    audit_root.mkdir(
        parents=True,
        exist_ok=True,
    )

    audit_file = (
        audit_root / "audit_events.json"
    )

    audit_file.write_text(
        "[]",
        encoding="utf-8",
    )

    # Keep module-level constants aligned with the test location.
    monkeypatch.setattr(
        audit_store_module,
        "AUDIT_ROOT",
        audit_root,
    )

    monkeypatch.setattr(
        audit_store_module,
        "AUDIT_EVENTS_FILE",
        audit_file,
    )

    # CRITICAL FIX:
    # Redirect the already-created global store object itself.
    monkeypatch.setattr(
        audit_store_module.audit_store,
        "events_file",
        audit_file,
    )

    return (
        audit_root,
        audit_file,
    )


# ============================================================================
# FASTAPI ROUTE WALKER
# ============================================================================

def _walk_routes(
    routes: Iterable[object],
) -> Iterable[Tuple[str, set[str]]]:
    """
    Recursively inspect normal FastAPI routes and nested included routers.

    FastAPI can expose `_IncludedRouter` objects in app.routes, so tests
    must not assume every top-level entry has `.path`.
    """

    for route in routes:
        path = getattr(
            route,
            "path",
            None,
        )

        methods = getattr(
            route,
            "methods",
            None,
        )

        if path:
            yield (
                path,
                set(methods or set()),
            )

        nested_routes = getattr(
            route,
            "routes",
            None,
        )

        if nested_routes:
            yield from _walk_routes(
                nested_routes
            )


def _audit_routes() -> list[Tuple[str, set[str]]]:
    """Return all recursively discovered audit routes."""

    return [
        (
            path,
            methods,
        )
        for path, methods in _walk_routes(
            app.routes
        )
        if path.startswith(
            "/api/audit"
        )
    ]


# ============================================================================
# IDENTIFIERS
# ============================================================================

def test_audit_identifier_generation():
    event_id_one = create_event_id()
    event_id_two = create_event_id()

    request_id_one = create_request_id()
    request_id_two = create_request_id()

    assert event_id_one
    assert event_id_two
    assert request_id_one
    assert request_id_two

    assert (
        event_id_one
        != event_id_two
    )

    assert (
        request_id_one
        != request_id_two
    )


# ============================================================================
# SUCCESS EVENT
# ============================================================================

def test_record_success_event(
    isolated_audit_store,
):
    _, audit_file = isolated_audit_store

    event = audit_service.success(
        category="test",
        action="test_success",
        service="test_suite",
        message="Audit success event",
        model="qwen2.5-coder:3b",
        task_type="test",
        resource="test_resource",
        resource_id="test-001",
        duration_ms=125.5,
        metadata={
            "source": "pytest",
            "verified": True,
        },
    )

    assert event["event_id"]
    assert event["status"] == "success"
    assert event["category"] == "test"
    assert event["action"] == "test_success"
    assert event["service"] == "test_suite"
    assert event["message"] == "Audit success event"
    assert event["model"] == "qwen2.5-coder:3b"
    assert event["task_type"] == "test"
    assert event["resource"] == "test_resource"
    assert event["resource_id"] == "test-001"
    assert event["duration_ms"] == 125.5
    assert event["metadata"]["source"] == "pytest"

    persisted = json.loads(
        audit_file.read_text(
            encoding="utf-8"
        )
    )

    assert len(persisted) == 1

    assert (
        persisted[0]["event_id"]
        == event["event_id"]
    )


# ============================================================================
# FAILURE EVENT
# ============================================================================

def test_record_failure_event(
    isolated_audit_store,
):
    audit_service.failure(
        category="test",
        action="test_failure",
        service="test_suite",
        message="Audit failure event",
        metadata={
            "source": "pytest",
            "error_type": "TestError",
        },
    )

    result = audit_service.list_events(
        limit=50
    )

    assert result["total"] == 1

    event = result["events"][0]

    assert event["status"] == "failed"
    assert event["category"] == "test"
    assert event["action"] == "test_failure"
    assert (
        event["metadata"]["error_type"]
        == "TestError"
    )


# ============================================================================
# EVENT LOOKUP
# ============================================================================

def test_event_lookup(
    isolated_audit_store,
):
    created = audit_service.success(
        category="model",
        action="model_test",
        service="model_engine",
        model="qwen2.5-coder:3b",
        task_type="test",
        resource="model",
        resource_id="qwen2.5-coder:3b",
        message="Model test completed",
    )

    event = audit_service.get_event(
        created["event_id"]
    )

    assert event is not None

    assert (
        event["event_id"]
        == created["event_id"]
    )

    assert (
        event["action"]
        == "model_test"
    )


# ============================================================================
# EVENT FILTERS
# ============================================================================

def test_event_filters(
    isolated_audit_store,
):
    audit_service.success(
        category="chat",
        action="request",
        service="chat",
        model="qwen2.5-coder:3b",
        task_type="auto",
        message="Chat request completed",
    )

    audit_service.failure(
        category="knowledge",
        action="file_upload",
        service="knowledge",
        model="llama3.2:latest",
        task_type="document",
        message="Knowledge upload failed",
    )

    audit_service.success(
        category="model",
        action="model_test",
        service="model_engine",
        model="qwen2.5-coder:3b",
        task_type="test",
        message="Model test completed",
    )

    chat_results = audit_service.list_events(
        category="chat",
        limit=50,
    )

    assert chat_results["total"] == 1

    assert (
        chat_results["events"][0]["category"]
        == "chat"
    )

    failed_results = audit_service.list_events(
        status="failed",
        limit=50,
    )

    assert failed_results["total"] == 1

    assert (
        failed_results["events"][0]["service"]
        == "knowledge"
    )

    model_results = audit_service.list_events(
        model="qwen2.5-coder:3b",
        limit=50,
    )

    assert model_results["total"] == 2

    task_results = audit_service.list_events(
        task_type="document",
        limit=50,
    )

    assert task_results["total"] == 1

    search_results = audit_service.list_events(
        query="upload failed",
        limit=50,
    )

    assert search_results["total"] == 1


# ============================================================================
# PAGINATION
# ============================================================================

def test_event_pagination(
    isolated_audit_store,
):
    for index in range(5):
        audit_service.success(
            category="test",
            action=f"event_{index}",
            service="test_suite",
            message=f"Event number {index}",
        )

    first_page = audit_service.list_events(
        limit=2,
        offset=0,
    )

    second_page = audit_service.list_events(
        limit=2,
        offset=2,
    )

    assert first_page["total"] == 5
    assert second_page["total"] == 5

    assert (
        len(first_page["events"])
        == 2
    )

    assert (
        len(second_page["events"])
        == 2
    )

    first_ids = {
        item["event_id"]
        for item in first_page["events"]
    }

    second_ids = {
        item["event_id"]
        for item in second_page["events"]
    }

    assert first_ids.isdisjoint(
        second_ids
    )


# ============================================================================
# SUMMARY
# ============================================================================

def test_summary_counts(
    isolated_audit_store,
):
    audit_service.success(
        category="chat",
        action="request",
        service="chat",
        message="success 1",
    )

    audit_service.success(
        category="model",
        action="model_test",
        service="model_engine",
        message="success 2",
    )

    audit_service.failure(
        category="knowledge",
        action="file_upload",
        service="knowledge",
        message="failure 1",
    )

    summary = audit_service.summary()

    assert summary["total_events"] == 3
    assert summary["successful_events"] == 2
    assert summary["failed_events"] == 1


# ============================================================================
# JSON EXPORT
# ============================================================================

def test_json_export(
    isolated_audit_store,
):
    audit_service.success(
        category="chat",
        action="request",
        service="chat",
        message="JSON export test",
        metadata={
            "export": True,
        },
    )

    exported = audit_service.export_json()

    assert isinstance(
        exported,
        str,
    )

    data = json.loads(
        exported
    )

    assert isinstance(
        data,
        list,
    )

    assert len(data) == 1

    assert (
        data[0]["message"]
        == "JSON export test"
    )

    assert (
        data[0]["metadata"]["export"]
        is True
    )


# ============================================================================
# CSV EXPORT
# ============================================================================

def test_csv_export(
    isolated_audit_store,
):
    audit_service.success(
        category="chat",
        action="request",
        service="chat",
        message="CSV export test",
        model="qwen2.5-coder:3b",
        task_type="auto",
        duration_ms=42.0,
    )

    exported = audit_service.export_csv()

    assert isinstance(
        exported,
        str,
    )

    reader = csv.DictReader(
        io.StringIO(exported)
    )

    rows = list(reader)

    assert len(rows) == 1

    assert (
        rows[0]["category"]
        == "chat"
    )

    assert (
        rows[0]["action"]
        == "request"
    )

    assert (
        rows[0]["service"]
        == "chat"
    )

    assert (
        rows[0]["model"]
        == "qwen2.5-coder:3b"
    )


# ============================================================================
# APPEND-ONLY GUARANTEE
# ============================================================================

def test_append_only_store_has_no_delete_api(
    isolated_audit_store,
):
    store = audit_store_module.audit_store

    assert not hasattr(
        store,
        "delete_event",
    )

    assert not hasattr(
        audit_service,
        "delete_event",
    )


# ============================================================================
# ROUTER REGISTRATION
# ============================================================================

def test_audit_router_is_registered():
    audit_routes = _audit_routes()

    audit_paths = {
        path
        for path, _ in audit_routes
    }

    expected_paths = {
        "/api/audit",
        "/api/audit/summary",
        "/api/audit/{event_id}",
        "/api/audit/export/json",
        "/api/audit/export/csv",
    }

    assert expected_paths.issubset(
        audit_paths
    )


# ============================================================================
# NO DELETE ENDPOINT
# ============================================================================

def test_audit_router_has_no_delete_endpoint():
    audit_routes = _audit_routes()

    delete_audit_routes = [
        (
            path,
            methods,
        )
        for path, methods in audit_routes
        if "DELETE" in methods
    ]

    assert delete_audit_routes == []


# ============================================================================
# REAL FILE PERSISTENCE
# ============================================================================

def test_real_file_persistence_across_reads(
    isolated_audit_store,
):
    _, audit_file = isolated_audit_store

    created = audit_service.success(
        category="sovereignty",
        action="network_event",
        service="network_ledger",
        resource="network",
        resource_id="network-test-001",
        message="Application-level network event",
        metadata={
            "measurement_scope":
                "application_level",
        },
    )

    raw = audit_file.read_text(
        encoding="utf-8"
    )

    assert (
        created["event_id"]
        in raw
    )

    parsed = json.loads(
        raw
    )

    assert len(parsed) == 1

    assert (
        parsed[0]["resource"]
        == "network"
    )

    assert (
        parsed[0]["metadata"][
            "measurement_scope"
        ]
        == "application_level"
    )
def _audit_routes():
    paths = app.openapi().get("paths", {})
    return {
        path: methods
        for path, methods in paths.items()
        if path.startswith("/api/audit")
    }


def test_audit_router_is_registered():
    audit_routes = _audit_routes()

    expected_paths = {
        "/api/audit",
        "/api/audit/summary",
        "/api/audit/{event_id}",
        "/api/audit/export/json",
        "/api/audit/export/csv",
    }

    assert expected_paths.issubset(audit_routes.keys())


def test_audit_router_has_no_delete_endpoint():
    audit_routes = _audit_routes()

    for path, methods in audit_routes.items():
        assert "delete" not in {
            method.lower()
            for method in methods
        }