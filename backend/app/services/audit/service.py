"""
NOVA Audit Trail service.

This module provides the application-level audit interface used by NOVA
services and API routes.

Responsibilities:
    - Record real NOVA events.
    - Measure event duration.
    - Attach structured metadata.
    - Track request/event identifiers.
    - Record success and failure states.
    - Query and summarize persisted events.
    - Export persisted events.

The service never creates synthetic activity merely to populate the UI.
Only actual callers create audit events.
"""

from __future__ import annotations

import time
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any, Dict, Iterator, Optional

from app.services.audit.store import (
    AuditStore,
    audit_store,
)


# ---------------------------------------------------------------------------
# CONSTANTS
# ---------------------------------------------------------------------------

AUDIT_STATUS_STARTED = "started"
AUDIT_STATUS_SUCCESS = "success"
AUDIT_STATUS_FAILED = "failed"
AUDIT_STATUS_COMPLETED = "completed"
AUDIT_STATUS_ERROR = "error"

DEFAULT_CATEGORY = "system"
DEFAULT_ACTION = "operation"
DEFAULT_SERVICE = "unknown"


_audit_user_id: ContextVar[Optional[str]] = ContextVar(
    "audit_user_id",
    default=None,
)


def set_audit_user_id(user_id: Optional[Any]):
    """Bind the authenticated request owner to its audit records."""

    return _audit_user_id.set(
        str(user_id) if user_id is not None else None
    )


def reset_audit_user_id(token: Any) -> None:
    """Clear request-scoped audit ownership."""

    _audit_user_id.reset(token)


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------


def _utc_now() -> str:
    """Return a timezone-aware UTC ISO timestamp."""

    return (
        datetime.now(timezone.utc)
        .isoformat()
        .replace(
            "+00:00",
            "Z",
        )
    )


def _safe_value(
    value: Any,
) -> Any:
    """
    Convert common runtime values into JSON-safe representations.
    """

    if value is None:
        return None

    if isinstance(
        value,
        (
            str,
            int,
            float,
            bool,
        ),
    ):
        return value

    if isinstance(
        value,
        dict,
    ):
        return {
            str(key): _safe_value(item)
            for key, item in value.items()
        }

    if isinstance(
        value,
        (list, tuple, set),
    ):
        return [
            _safe_value(item)
            for item in value
        ]

    return str(value)


def create_event_id() -> str:
    """Create a unique audit event identifier."""

    return uuid.uuid4().hex


def create_request_id() -> str:
    """Create a unique request identifier."""

    return uuid.uuid4().hex


# ---------------------------------------------------------------------------
# CORE SERVICE
# ---------------------------------------------------------------------------


class AuditService:
    """
    High-level NOVA audit interface.

    The service intentionally delegates persistence to AuditStore so that
    application code does not need to know where audit data is stored.
    """

    def __init__(
        self,
        store: Optional[AuditStore] = None,
    ) -> None:
        self.store = (
            store
            or audit_store
        )

    # ---------------------------------------------------------------------
    # RECORD EVENT
    # ---------------------------------------------------------------------

    def record_event(
        self,
        *,
        category: str = DEFAULT_CATEGORY,
        action: str = DEFAULT_ACTION,
        service: str = DEFAULT_SERVICE,
        status: str = AUDIT_STATUS_SUCCESS,
        message: str = "",
        duration_ms: Optional[float] = None,
        model: Optional[str] = None,
        task_type: Optional[str] = None,
        resource: Optional[str] = None,
        resource_id: Optional[str] = None,
        request_id: Optional[str] = None,
        event_id: Optional[str] = None,
        timestamp: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **extra_fields: Any,
    ) -> Dict[str, Any]:
        """
        Record one actual NOVA event.

        Unknown additional fields are preserved at the top level so future
        event types can add structured information without changing this
        method immediately.
        """

        event: Dict[str, Any] = {
            "event_id": (
                event_id
                or create_event_id()
            ),
            "timestamp": (
                timestamp
                or _utc_now()
            ),
            "category": (
                str(category)
                if category
                else DEFAULT_CATEGORY
            ),
            "action": (
                str(action)
                if action
                else DEFAULT_ACTION
            ),
            "service": (
                str(service)
                if service
                else DEFAULT_SERVICE
            ),
            "status": (
                str(status)
                if status
                else AUDIT_STATUS_SUCCESS
            ),
            "message": str(
                message
                or ""
            ),
            "metadata": _safe_value(
                metadata
                or {}
            ),
        }

        current_user_id = _audit_user_id.get()

        if current_user_id is not None:
            event["user_id"] = current_user_id

        if duration_ms is not None:
            try:
                event["duration_ms"] = round(
                    float(duration_ms),
                    2,
                )
            except (
                TypeError,
                ValueError,
            ):
                event["duration_ms"] = None

        optional_fields = {
            "model": model,
            "task_type": task_type,
            "resource": resource,
            "resource_id": resource_id,
            "request_id": request_id,
        }

        for key, value in optional_fields.items():
            if value is not None:
                event[key] = str(value)

        for key, value in extra_fields.items():
            if key in event:
                continue

            event[str(key)] = _safe_value(
                value
            )

        return self.store.append(
            event
        )

    # ---------------------------------------------------------------------
    # SUCCESS
    # ---------------------------------------------------------------------

    def success(
        self,
        *,
        category: str,
        action: str,
        service: str,
        message: str = "",
        duration_ms: Optional[float] = None,
        model: Optional[str] = None,
        task_type: Optional[str] = None,
        resource: Optional[str] = None,
        resource_id: Optional[str] = None,
        request_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **extra_fields: Any,
    ) -> Dict[str, Any]:
        """Record a successful event."""

        return self.record_event(
            category=category,
            action=action,
            service=service,
            status=AUDIT_STATUS_SUCCESS,
            message=message,
            duration_ms=duration_ms,
            model=model,
            task_type=task_type,
            resource=resource,
            resource_id=resource_id,
            request_id=request_id,
            metadata=metadata,
            **extra_fields,
        )

    # ---------------------------------------------------------------------
    # FAILURE
    # ---------------------------------------------------------------------

    def failure(
        self,
        *,
        category: str,
        action: str,
        service: str,
        message: str = "",
        duration_ms: Optional[float] = None,
        model: Optional[str] = None,
        task_type: Optional[str] = None,
        resource: Optional[str] = None,
        resource_id: Optional[str] = None,
        request_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **extra_fields: Any,
    ) -> Dict[str, Any]:
        """Record a failed event."""

        return self.record_event(
            category=category,
            action=action,
            service=service,
            status=AUDIT_STATUS_FAILED,
            message=message,
            duration_ms=duration_ms,
            model=model,
            task_type=task_type,
            resource=resource,
            resource_id=resource_id,
            request_id=request_id,
            metadata=metadata,
            **extra_fields,
        )

    # ---------------------------------------------------------------------
    # ERROR
    # ---------------------------------------------------------------------

    def error(
        self,
        *,
        category: str,
        action: str,
        service: str,
        error: Exception,
        duration_ms: Optional[float] = None,
        model: Optional[str] = None,
        task_type: Optional[str] = None,
        resource: Optional[str] = None,
        resource_id: Optional[str] = None,
        request_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **extra_fields: Any,
    ) -> Dict[str, Any]:
        """
        Record a runtime error.

        Exception details are stored as metadata rather than allowing the
        audit system to raise a second exception.
        """

        combined_metadata = dict(
            metadata
            or {}
        )

        combined_metadata.setdefault(
            "exception_type",
            type(error).__name__,
        )

        combined_metadata.setdefault(
            "exception_message",
            str(error),
        )

        return self.record_event(
            category=category,
            action=action,
            service=service,
            status=AUDIT_STATUS_ERROR,
            message=str(error),
            duration_ms=duration_ms,
            model=model,
            task_type=task_type,
            resource=resource,
            resource_id=resource_id,
            request_id=request_id,
            metadata=combined_metadata,
            **extra_fields,
        )

    # ---------------------------------------------------------------------
    # TIMED OPERATION
    # ---------------------------------------------------------------------

    @contextmanager
    def timed(
        self,
        *,
        category: str,
        action: str,
        service: str,
        message: str = "",
        model: Optional[str] = None,
        task_type: Optional[str] = None,
        resource: Optional[str] = None,
        resource_id: Optional[str] = None,
        request_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        record_started: bool = False,
        **extra_fields: Any,
    ) -> Iterator[Dict[str, Any]]:
        """
        Time a real NOVA operation.

        Usage:

            with audit_service.timed(
                category="model",
                action="inference",
                service="ollama",
            ) as context:
                ...
        
        The yielded context contains the generated request/event IDs and
        can be updated by the caller during execution.

        By default, only the final event is persisted. Set record_started=True
        when a separate 'started' audit event is useful.
        """

        event_id = create_event_id()

        effective_request_id = (
            request_id
            or create_request_id()
        )

        context: Dict[str, Any] = {
            "event_id": event_id,
            "request_id": effective_request_id,
            "category": category,
            "action": action,
            "service": service,
        }

        started_at = time.perf_counter()

        if record_started:
            self.record_event(
                category=category,
                action=action,
                service=service,
                status=AUDIT_STATUS_STARTED,
                message=message,
                model=model,
                task_type=task_type,
                resource=resource,
                resource_id=resource_id,
                request_id=effective_request_id,
                event_id=event_id,
                metadata=metadata,
                **extra_fields,
            )

        try:
            yield context

        except Exception as exc:
            elapsed_ms = (
                time.perf_counter()
                - started_at
            ) * 1000.0

            self.error(
                category=category,
                action=action,
                service=service,
                error=exc,
                duration_ms=elapsed_ms,
                model=(
                    context.get(
                        "model",
                        model,
                    )
                ),
                task_type=(
                    context.get(
                        "task_type",
                        task_type,
                    )
                ),
                resource=(
                    context.get(
                        "resource",
                        resource,
                    )
                ),
                resource_id=(
                    context.get(
                        "resource_id",
                        resource_id,
                    )
                ),
                request_id=effective_request_id,
                metadata=(
                    context.get(
                        "metadata",
                        metadata,
                    )
                    or {}
                ),
                event_id=event_id,
                **extra_fields,
            )

            raise

        else:
            elapsed_ms = (
                time.perf_counter()
                - started_at
            ) * 1000.0

            self.record_event(
                category=category,
                action=action,
                service=service,
                status=AUDIT_STATUS_SUCCESS,
                message=(
                    context.get(
                        "message",
                        message,
                    )
                ),
                duration_ms=elapsed_ms,
                model=(
                    context.get(
                        "model",
                        model,
                    )
                ),
                task_type=(
                    context.get(
                        "task_type",
                        task_type,
                    )
                ),
                resource=(
                    context.get(
                        "resource",
                        resource,
                    )
                ),
                resource_id=(
                    context.get(
                        "resource_id",
                        resource_id,
                    )
                ),
                request_id=effective_request_id,
                event_id=event_id,
                timestamp=_utc_now(),
                metadata=(
                    context.get(
                        "metadata",
                        metadata,
                    )
                    or {}
                ),
                **extra_fields,
            )

    # ---------------------------------------------------------------------
    # QUERY
    # ---------------------------------------------------------------------

    def list_events(
        self,
        **filters: Any,
    ) -> Dict[str, Any]:
        """Return filtered audit events."""

        return self.store.list_events(
            **filters
        )

    def get_event(
        self,
        event_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Return one audit event by ID."""

        return self.store.get_event(
            event_id
        )

    # ---------------------------------------------------------------------
    # SUMMARY
    # ---------------------------------------------------------------------

    def summary(self) -> Dict[str, Any]:
        """Return aggregate information over actual audit events."""

        return self.store.summary()

    # ---------------------------------------------------------------------
    # EXPORT
    # ---------------------------------------------------------------------

    def export_json(
        self,
        **filters: Any,
    ) -> str:
        """Return filtered audit events as JSON."""

        return self.store.export_json(
            **filters
        )

    def export_csv(
        self,
        **filters: Any,
    ) -> str:
        """Return filtered audit events as CSV."""

        return self.store.export_csv(
            **filters
        )


# ---------------------------------------------------------------------------
# DEFAULT SERVICE
# ---------------------------------------------------------------------------

audit_service = AuditService()


__all__ = [
    "AUDIT_STATUS_STARTED",
    "AUDIT_STATUS_SUCCESS",
    "AUDIT_STATUS_FAILED",
    "AUDIT_STATUS_COMPLETED",
    "AUDIT_STATUS_ERROR",
    "AuditService",
    "audit_service",
    "create_event_id",
    "create_request_id",
    "reset_audit_user_id",
    "set_audit_user_id",
]
