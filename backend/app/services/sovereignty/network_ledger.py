"""
NOVA Sovereignty Network Ledger

Truthful, local persistence for application-level network/egress events.

Important:
- This module does NOT claim to monitor the entire operating system network.
- It records events only when NOVA explicitly reports them.
- No synthetic counters or fake telemetry are generated.
- Every recorded network event is mirrored into the NOVA Audit Trail.
"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.services.audit.service import (
    audit_service,
)


# ---------------------------------------------------------------------------
# STORAGE
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parents[4]
DATA_DIR = BASE_DIR / "data" / "sovereignty"
LEDGER_FILE = DATA_DIR / "network_ledger.json"

_LOCK = threading.RLock()


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_storage() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    if not LEDGER_FILE.exists():
        _write_state(
            {
                "version": 1,
                "events": [],
            }
        )


def _read_state() -> Dict[str, Any]:
    _ensure_storage()

    try:
        with LEDGER_FILE.open(
            "r",
            encoding="utf-8",
        ) as file:
            data = json.load(file)

        if not isinstance(data, dict):
            return {
                "version": 1,
                "events": [],
            }

        events = data.get("events")

        if not isinstance(events, list):
            data["events"] = []

        return data

    except (
        OSError,
        json.JSONDecodeError,
        TypeError,
        ValueError,
    ):
        return {
            "version": 1,
            "events": [],
        }


def _write_state(state: Dict[str, Any]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    temp_file = LEDGER_FILE.with_suffix(".tmp")

    with temp_file.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            state,
            file,
            indent=2,
            ensure_ascii=False,
        )

    temp_file.replace(LEDGER_FILE)


def _normalize_text(
    value: Optional[Any],
) -> Optional[str]:
    if value is None:
        return None

    text = str(value).strip()

    return text or None


def _extract_request_id(
    metadata: Optional[Dict[str, Any]],
) -> Optional[str]:
    if not isinstance(
        metadata,
        dict,
    ):
        return None

    for key in (
        "request_id",
        "audit_request_id",
        "correlation_id",
    ):
        value = _normalize_text(
            metadata.get(key)
        )

        if value:
            return value

    return None


def _safe_audit_network_event(
    *,
    event: Dict[str, Any],
) -> None:
    """
    Mirror one real sovereignty ledger event into the central
    append-only NOVA Audit Trail.

    Audit persistence is best-effort and must never break the
    network ledger itself.
    """

    try:
        event_type = str(
            event.get(
                "event_type",
                "network",
            )
        ).strip()

        target = _normalize_text(
            event.get(
                "target"
            )
        )

        service = _normalize_text(
            event.get(
                "service"
            )
        )

        method = _normalize_text(
            event.get(
                "method"
            )
        )

        success = event.get(
            "success"
        )

        request_id = _extract_request_id(
            event.get(
                "metadata"
            )
        )

        audit_status = (
            "success"
            if success is True
            else (
                "failed"
                if success is False
                else "success"
            )
        )

        target_text = (
            f" → {target}"
            if target
            else ""
        )

        method_text = (
            f" {method}"
            if method
            else ""
        )

        message = (
            f"{event_type.replace('_', ' ').title()}"
            f" network event{method_text}{target_text}"
        )

        audit_service.record_event(
            category="sovereignty",
            action="network_event",
            service=(
                service
                or "network_ledger"
            ),
            status=audit_status,
            message=message,
            request_id=request_id,
            resource="network",
            resource_id=str(
                event.get(
                    "id",
                    "",
                )
            ).strip() or None,
            metadata={
                "network_event_id": event.get(
                    "id"
                ),
                "event_type": event_type,
                "target": target,
                "service": service,
                "method": method,
                "success": success,
                "measurement_scope": (
                    "application_level"
                ),
                "ledger_file": str(
                    LEDGER_FILE
                ),
                "source": (
                    "sovereignty.network_ledger"
                ),
                **(
                    dict(
                        event.get(
                            "metadata"
                        )
                    )
                    if isinstance(
                        event.get(
                            "metadata"
                        ),
                        dict,
                    )
                    else {}
                ),
            },
        )

    except Exception as exc:
        print(
            "[NOVA AUDIT NETWORK MIRROR] "
            f"{type(exc).__name__}: {exc}"
        )


# ---------------------------------------------------------------------------
# LEDGER
# ---------------------------------------------------------------------------


class NetworkLedger:
    """
    Local application-level network/egress ledger.

    Supported event types:
        external_api
        cloud_upload
        local_network
        network_error

    This ledger is intentionally explicit:
    a request is counted only when NOVA calls one of the record_* methods.
    """

    VALID_EVENT_TYPES = {
        "external_api",
        "cloud_upload",
        "local_network",
        "network_error",
    }

    def record_event(
        self,
        event_type: str,
        *,
        target: Optional[str] = None,
        service: Optional[str] = None,
        method: Optional[str] = None,
        success: Optional[bool] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Record one verified application-level network event.
        """

        normalized_type = str(
            event_type or ""
        ).strip().lower()

        if normalized_type not in self.VALID_EVENT_TYPES:
            raise ValueError(
                "Unsupported network event type: "
                f"{event_type}"
            )

        normalized_metadata = (
            dict(metadata)
            if isinstance(
                metadata,
                dict,
            )
            else {}
        )

        event = {
            "id": (
                f"net-"
                f"{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}"
            ),
            "timestamp": _utc_now(),
            "event_type": normalized_type,
            "target": _normalize_text(
                target
            ),
            "service": _normalize_text(
                service
            ),
            "method": _normalize_text(
                method
            ),
            "success": (
                bool(success)
                if success is not None
                else None
            ),
            "metadata": normalized_metadata,
        }

        with _LOCK:
            state = _read_state()

            events = state.setdefault(
                "events",
                [],
            )

            events.append(
                event
            )

            _write_state(
                state
            )

        # ---------------------------------------------------------------
        # CENTRAL AUDIT MIRROR
        # ---------------------------------------------------------------

        _safe_audit_network_event(
            event=event
        )

        return event

    def record_external_api(
        self,
        *,
        target: str,
        service: Optional[str] = None,
        method: Optional[str] = "POST",
        success: Optional[bool] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Record an external API request made by NOVA.
        """

        return self.record_event(
            "external_api",
            target=target,
            service=service,
            method=method,
            success=success,
            metadata=metadata,
        )

    def record_cloud_upload(
        self,
        *,
        target: str,
        service: Optional[str] = None,
        method: Optional[str] = "POST",
        success: Optional[bool] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Record a cloud upload initiated by NOVA.
        """

        return self.record_event(
            "cloud_upload",
            target=target,
            service=service,
            method=method,
            success=success,
            metadata=metadata,
        )

    def record_local_network(
        self,
        *,
        target: str,
        service: Optional[str] = None,
        method: Optional[str] = "GET",
        success: Optional[bool] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Record a NOVA-local network interaction.

        Example:
            127.0.0.1:11434
        """

        return self.record_event(
            "local_network",
            target=target,
            service=service,
            method=method,
            success=success,
            metadata=metadata,
        )

    def record_network_error(
        self,
        *,
        target: Optional[str] = None,
        service: Optional[str] = None,
        method: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Record a failed network interaction.
        """

        return self.record_event(
            "network_error",
            target=target,
            service=service,
            method=method,
            success=False,
            metadata=metadata,
        )

    def get_events(
        self,
        *,
        limit: Optional[int] = 100,
        event_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Return newest ledger events first.
        """

        with _LOCK:
            state = _read_state()

        events = list(
            state.get(
                "events",
                [],
            )
        )

        normalized_type = _normalize_text(
            event_type
        )

        if normalized_type:
            events = [
                event
                for event in events
                if event.get("event_type")
                == normalized_type
            ]

        events.sort(
            key=lambda item: str(
                item.get(
                    "timestamp",
                    "",
                )
            ),
            reverse=True,
        )

        if limit is None:
            return events

        try:
            safe_limit = max(
                0,
                int(limit),
            )
        except (
            TypeError,
            ValueError,
        ):
            safe_limit = 100

        return events[:safe_limit]

    def get_summary(
        self,
    ) -> Dict[str, Any]:
        """
        Return truthful aggregate information.
        """

        events = self.get_events(
            limit=None
        )

        external_api = [
            event
            for event in events
            if event.get("event_type")
            == "external_api"
        ]

        cloud_uploads = [
            event
            for event in events
            if event.get("event_type")
            == "cloud_upload"
        ]

        local_network = [
            event
            for event in events
            if event.get("event_type")
            == "local_network"
        ]

        network_errors = [
            event
            for event in events
            if event.get("event_type")
            == "network_error"
        ]

        latest_event = (
            events[0]
            if events
            else None
        )

        return {
            "tracking": "application_level",
            "measurement_scope": (
                "NOVA-recorded network events only"
            ),
            "external_api_calls": len(
                external_api
            ),
            "cloud_uploads": len(
                cloud_uploads
            ),
            "local_network_events": len(
                local_network
            ),
            "network_errors": len(
                network_errors
            ),
            "total_events": len(
                events
            ),
            "latest_event": latest_event,
        }

    def clear(self) -> None:
        """
        Clear the local ledger.

        Intended for development/testing only.

        This operation is intentionally not mirrored into the
        Audit Trail because it is a test/development reset rather
        than a runtime network operation.
        """

        with _LOCK:
            _write_state(
                {
                    "version": 1,
                    "events": [],
                }
            )


# ---------------------------------------------------------------------------
# SINGLETON
# ---------------------------------------------------------------------------

network_ledger = NetworkLedger()