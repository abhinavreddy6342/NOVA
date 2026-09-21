"""
NOVA Audit Trail persistent event store.

This module provides the low-level persistence layer for NOVA's
append-oriented audit trail.

Storage:
    backend/data/audit/audit_events.json

The store does not generate synthetic activity. Events are written only
when an actual NOVA service records them.
"""

from __future__ import annotations

import csv
import io
import json
import os
import tempfile
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# PATHS
# ---------------------------------------------------------------------------

BACKEND_ROOT = Path(__file__).resolve().parents[3]

AUDIT_ROOT = (
    BACKEND_ROOT
    / "data"
    / "audit"
)

AUDIT_EVENTS_FILE = (
    AUDIT_ROOT
    / "audit_events.json"
)


# ---------------------------------------------------------------------------
# STORE
# ---------------------------------------------------------------------------


class AuditStore:
    """
    Persistent JSON-backed audit event store.

    Events are treated as append-oriented records. The store does not expose
    a deletion operation because removing audit history would undermine the
    purpose of traceability.
    """

    _lock = threading.RLock()

    def __init__(
        self,
        events_file: Optional[Path] = None,
    ) -> None:
        self.events_file = (
            Path(events_file)
            if events_file is not None
            else AUDIT_EVENTS_FILE
        )

        self.events_file.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self._ensure_store()

    # ---------------------------------------------------------------------
    # INITIALIZATION
    # ---------------------------------------------------------------------

    def _ensure_store(self) -> None:
        """
        Create an empty audit store only when it does not already exist.
        """

        with self._lock:
            if self.events_file.exists():
                return

            self._atomic_write([])

    # ---------------------------------------------------------------------
    # LOW-LEVEL READ / WRITE
    # ---------------------------------------------------------------------

    def _read_events(self) -> List[Dict[str, Any]]:
        """
        Read all persisted events.

        Invalid or unexpected JSON content is treated as an empty store
        rather than crashing the application.
        """

        with self._lock:
            if not self.events_file.exists():
                return []

            try:
                raw = self.events_file.read_text(
                    encoding="utf-8"
                )

                if not raw.strip():
                    return []

                data = json.loads(raw)

                if not isinstance(data, list):
                    return []

                valid_events: List[Dict[str, Any]] = []

                for item in data:
                    if isinstance(item, dict):
                        valid_events.append(item)

                return valid_events

            except (
                OSError,
                json.JSONDecodeError,
                UnicodeError,
            ):
                return []

    def _atomic_write(
        self,
        events: List[Dict[str, Any]],
    ) -> None:
        """
        Atomically replace the audit JSON file.

        A temporary file is written first and then moved into place so a
        process interruption does not intentionally truncate the main store.
        """

        self.events_file.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        serialized = json.dumps(
            events,
            ensure_ascii=False,
            indent=2,
        )

        file_descriptor = None
        temporary_path: Optional[str] = None

        try:
            file_descriptor, temporary_path = tempfile.mkstemp(
                prefix="audit_",
                suffix=".tmp",
                dir=str(self.events_file.parent),
                text=True,
            )

            with os.fdopen(
                file_descriptor,
                "w",
                encoding="utf-8",
            ) as temporary_file:
                file_descriptor = None

                temporary_file.write(
                    serialized
                )

                temporary_file.flush()
                os.fsync(
                    temporary_file.fileno()
                )

            os.replace(
                temporary_path,
                self.events_file,
            )

            temporary_path = None

        finally:
            if file_descriptor is not None:
                try:
                    os.close(file_descriptor)
                except OSError:
                    pass

            if temporary_path is not None:
                try:
                    os.remove(
                        temporary_path
                    )
                except OSError:
                    pass

    # ---------------------------------------------------------------------
    # NORMALIZATION
    # ---------------------------------------------------------------------

    @staticmethod
    def _utc_now() -> str:
        """
        Return a timezone-aware UTC timestamp.
        """

        return (
            datetime.now(timezone.utc)
            .isoformat()
            .replace(
                "+00:00",
                "Z",
            )
        )

    @staticmethod
    def _normalize_event(
        event: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Normalize an event into a predictable JSON-safe structure.
        """

        normalized = dict(event)

        event_id = str(
            normalized.get(
                "event_id"
            )
            or uuid.uuid4().hex
        )

        normalized["event_id"] = event_id

        timestamp = normalized.get(
            "timestamp"
        )

        if not timestamp:
            normalized["timestamp"] = (
                AuditStore._utc_now()
            )

        normalized.setdefault(
            "category",
            "system",
        )

        normalized.setdefault(
            "action",
            "unknown",
        )

        normalized.setdefault(
            "service",
            "unknown",
        )

        normalized.setdefault(
            "status",
            "unknown",
        )

        normalized.setdefault(
            "message",
            "",
        )

        normalized.setdefault(
            "metadata",
            {},
        )

        if not isinstance(
            normalized.get("metadata"),
            dict,
        ):
            normalized["metadata"] = {
                "value": normalized[
                    "metadata"
                ]
            }

        return normalized

    # ---------------------------------------------------------------------
    # APPEND
    # ---------------------------------------------------------------------

    def append(
        self,
        event: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Append one real audit event and return the persisted record.
        """

        if not isinstance(event, dict):
            raise TypeError(
                "Audit event must be a dictionary."
            )

        normalized = self._normalize_event(
            event
        )

        with self._lock:
            events = self._read_events()

            events.append(
                normalized
            )

            self._atomic_write(
                events
            )

        return normalized

    # ---------------------------------------------------------------------
    # QUERY
    # ---------------------------------------------------------------------

    def list_events(
        self,
        *,
        query: Optional[str] = None,
        category: Optional[str] = None,
        action: Optional[str] = None,
        service: Optional[str] = None,
        status: Optional[str] = None,
        model: Optional[str] = None,
        task_type: Optional[str] = None,
        user_id: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """
        Return filtered audit events.

        Results are newest-first.
        """

        safe_limit = max(
            1,
            min(
                int(limit),
                1000,
            ),
        )

        safe_offset = max(
            0,
            int(offset),
        )

        events = self._read_events()

        # Newest events first.
        events.sort(
            key=lambda item: str(
                item.get(
                    "timestamp",
                    "",
                )
            ),
            reverse=True,
        )

        filtered: List[
            Dict[str, Any]
        ] = []

        clean_query = (
            str(query).strip().lower()
            if query
            else None
        )

        clean_category = (
            str(category).strip().lower()
            if category
            else None
        )

        clean_action = (
            str(action).strip().lower()
            if action
            else None
        )

        clean_service = (
            str(service).strip().lower()
            if service
            else None
        )

        clean_status = (
            str(status).strip().lower()
            if status
            else None
        )

        clean_model = (
            str(model).strip().lower()
            if model
            else None
        )

        clean_task_type = (
            str(task_type).strip().lower()
            if task_type
            else None
        )

        clean_user_id = (
            str(user_id).strip()
            if user_id is not None
            else None
        )

        for event in events:
            metadata = event.get("metadata", {})

            if not isinstance(metadata, dict):
                metadata = {}

            event_user_id = (
                event.get("user_id")
                or metadata.get("user_id")
            )

            if (
                clean_user_id is not None
                and str(event_user_id) != clean_user_id
            ):
                continue

            event_category = str(
                event.get(
                    "category",
                    "",
                )
            ).lower()

            event_action = str(
                event.get(
                    "action",
                    "",
                )
            ).lower()

            event_service = str(
                event.get(
                    "service",
                    "",
                )
            ).lower()

            event_status = str(
                event.get(
                    "status",
                    "",
                )
            ).lower()

            event_model = str(
                event.get(
                    "model",
                    "",
                )
            ).lower()

            event_task_type = str(
                event.get(
                    "task_type",
                    "",
                )
            ).lower()

            event_timestamp = str(
                event.get(
                    "timestamp",
                    "",
                )
            )

            if (
                clean_category is not None
                and event_category
                != clean_category
            ):
                continue

            if (
                clean_action is not None
                and event_action
                != clean_action
            ):
                continue

            if (
                clean_service is not None
                and event_service
                != clean_service
            ):
                continue

            if (
                clean_status is not None
                and event_status
                != clean_status
            ):
                continue

            if (
                clean_model is not None
                and clean_model
                not in event_model
            ):
                continue

            if (
                clean_task_type is not None
                and event_task_type
                != clean_task_type
            ):
                continue

            if (
                start_time
                and event_timestamp
                < str(start_time)
            ):
                continue

            if (
                end_time
                and event_timestamp
                > str(end_time)
            ):
                continue

            if clean_query:
                searchable = json.dumps(
                    event,
                    ensure_ascii=False,
                    default=str,
                ).lower()

                if clean_query not in searchable:
                    continue

            filtered.append(
                event
            )

        total = len(filtered)

        paginated = filtered[
            safe_offset:
            safe_offset + safe_limit
        ]

        return {
            "events": paginated,
            "total": total,
            "limit": safe_limit,
            "offset": safe_offset,
        }

    # ---------------------------------------------------------------------
    # SINGLE EVENT
    # ---------------------------------------------------------------------

    def get_event(
        self,
        event_id: str,
        *,
        user_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Find one audit event by event ID.
        """

        target = str(
            event_id
        ).strip()

        if not target:
            return None

        events = self._read_events()

        for event in events:
            if str(event.get("event_id", "")) != target:
                continue

            metadata = event.get("metadata", {})

            if not isinstance(metadata, dict):
                metadata = {}

            event_user_id = (
                event.get("user_id")
                or metadata.get("user_id")
            )

            if (
                user_id is None
                or str(event_user_id) == str(user_id)
            ):
                return event

        return None

    # ---------------------------------------------------------------------
    # SUMMARY
    # ---------------------------------------------------------------------

    def summary(
        self,
        *,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Return aggregate counts over the actual persisted audit events.
        """

        events = self.list_events(
            user_id=user_id,
            limit=1000,
        )["events"]

        total = len(events)

        success = 0
        failed = 0
        running = 0

        categories: Dict[
            str,
            int,
        ] = {}

        services: Dict[
            str,
            int,
        ] = {}

        statuses: Dict[
            str,
            int,
        ] = {}

        external_events = 0

        for event in events:
            category = str(
                event.get(
                    "category",
                    "unknown",
                )
            )

            service = str(
                event.get(
                    "service",
                    "unknown",
                )
            )

            status = str(
                event.get(
                    "status",
                    "unknown",
                )
            ).lower()

            categories[category] = (
                categories.get(
                    category,
                    0,
                )
                + 1
            )

            services[service] = (
                services.get(
                    service,
                    0,
                )
                + 1
            )

            statuses[status] = (
                statuses.get(
                    status,
                    0,
                )
                + 1
            )

            if status in {
                "success",
                "successful",
                "completed",
                "complete",
                "pass",
                "passed",
            }:
                success += 1

            if status in {
                "failed",
                "failure",
                "error",
            }:
                failed += 1

            if status in {
                "running",
                "started",
                "in_progress",
                "pending",
            }:
                running += 1

            if category in {
                "external_api",
                "cloud_upload",
            }:
                external_events += 1

        latest_event = None

        if events:
            events.sort(
                key=lambda item: str(
                    item.get(
                        "timestamp",
                        "",
                    )
                ),
                reverse=True,
            )

            latest_event = events[0]

        return {
            "total_events": total,
            "successful_events": success,
            "failed_events": failed,
            "running_events": running,
            "external_events": external_events,
            "categories": categories,
            "services": services,
            "statuses": statuses,
            "latest_event": latest_event,
        }

    # ---------------------------------------------------------------------
    # EXPORT
    # ---------------------------------------------------------------------

    def export_json(
        self,
        *,
        query: Optional[str] = None,
        category: Optional[str] = None,
        action: Optional[str] = None,
        service: Optional[str] = None,
        status: Optional[str] = None,
        model: Optional[str] = None,
        task_type: Optional[str] = None,
        user_id: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
    ) -> str:
        """
        Export filtered audit events as JSON.
        """

        result = self.list_events(
            query=query,
            category=category,
            action=action,
            service=service,
            status=status,
            model=model,
            task_type=task_type,
            user_id=user_id,
            start_time=start_time,
            end_time=end_time,
            limit=1000,
            offset=0,
        )

        return json.dumps(
            result["events"],
            ensure_ascii=False,
            indent=2,
        )

    def export_csv(
        self,
        *,
        query: Optional[str] = None,
        category: Optional[str] = None,
        action: Optional[str] = None,
        service: Optional[str] = None,
        status: Optional[str] = None,
        model: Optional[str] = None,
        task_type: Optional[str] = None,
        user_id: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
    ) -> str:
        """
        Export filtered audit events as CSV.
        """

        result = self.list_events(
            query=query,
            category=category,
            action=action,
            service=service,
            status=status,
            model=model,
            task_type=task_type,
            user_id=user_id,
            start_time=start_time,
            end_time=end_time,
            limit=1000,
            offset=0,
        )

        output = io.StringIO()

        fieldnames = [
            "event_id",
            "timestamp",
            "category",
            "action",
            "service",
            "status",
            "duration_ms",
            "model",
            "task_type",
            "resource",
            "resource_id",
            "message",
            "request_id",
            "metadata",
        ]

        writer = csv.DictWriter(
            output,
            fieldnames=fieldnames,
            extrasaction="ignore",
        )

        writer.writeheader()

        for event in result["events"]:
            row = dict(event)

            metadata = row.get(
                "metadata",
                {},
            )

            row["metadata"] = json.dumps(
                metadata,
                ensure_ascii=False,
            )

            writer.writerow(
                row
            )

        return output.getvalue()


# ---------------------------------------------------------------------------
# DEFAULT STORE
# ---------------------------------------------------------------------------

audit_store = AuditStore()


__all__ = [
    "AUDIT_ROOT",
    "AUDIT_EVENTS_FILE",
    "AuditStore",
    "audit_store",
]
