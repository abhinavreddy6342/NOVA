"""
NOVA Sovereignty Service

Collects truthful, application-relevant local runtime information for
the Sovereignty Center.

This module never invents measurements. When a subsystem cannot be
measured, it reports the limitation explicitly.
"""

from __future__ import annotations

import json
import os
import subprocess
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import psutil

from app.services.sovereignty.network_ledger import (
    network_ledger,
)


# ---------------------------------------------------------------------------
# PATHS
# ---------------------------------------------------------------------------

NOVA_ROOT = Path(__file__).resolve().parents[4]
BACKEND_ROOT = NOVA_ROOT / "backend"

DATA_ROOT = BACKEND_ROOT / "data"

KNOWLEDGE_ROOT = BACKEND_ROOT / "app" / "knowledge"
KNOWLEDGE_DOCUMENTS = KNOWLEDGE_ROOT / "documents"
KNOWLEDGE_UPLOADS = KNOWLEDGE_ROOT / "chat_uploads"
KNOWLEDGE_VECTORSTORE = KNOWLEDGE_ROOT / "vectorstore"

SANDBOX_ROOT = BACKEND_ROOT / "sandbox"
WORKSPACE_ROOT = BACKEND_ROOT / "workspace"

MODEL_RUNTIME_STATE = (
    DATA_ROOT / "model_runtime_state.json"
)


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------


def _utc_now() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat()


def _directory_status(
    path: Path,
) -> Dict[str, Any]:
    """
    Inspect a local directory without inventing state.

    File count and byte size are only reported when they can be
    measured from the local filesystem.
    """

    exists = path.exists()
    is_directory = path.is_dir()

    file_count: Optional[int] = None
    size_bytes: Optional[int] = None
    scan_error: Optional[str] = None

    if is_directory:
        try:
            count = 0
            total_size = 0

            for item in path.rglob("*"):
                try:
                    if item.is_file():
                        count += 1
                        total_size += item.stat().st_size
                except (
                    OSError,
                    PermissionError,
                ):
                    continue

            file_count = count
            size_bytes = total_size

        except (
            OSError,
            PermissionError,
        ) as exc:
            scan_error = str(exc)

    if not exists:
        status = "NOT_FOUND"
    elif not is_directory:
        status = "INVALID"
    else:
        status = "AVAILABLE"

    return {
        "path": str(path),
        "status": status,
        "exists": exists,
        "is_directory": is_directory,
        "file_count": file_count,
        "size_bytes": size_bytes,
        "scan_error": scan_error,
    }


def _read_json(
    path: Path,
) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None

    try:
        with path.open(
            "r",
            encoding="utf-8",
        ) as file:
            data = json.load(file)

        return (
            data
            if isinstance(data, dict)
            else None
        )

    except (
        OSError,
        json.JSONDecodeError,
        TypeError,
        ValueError,
    ):
        return None


def _get_ollama_url() -> str:
    value = os.getenv(
        "OLLAMA_BASE_URL",
        "http://127.0.0.1:11434",
    )

    return value.rstrip("/")


def _ollama_get(
    path: str,
    timeout: float = 2.5,
) -> Optional[Dict[str, Any]]:
    """
    Query local Ollama using its HTTP API.

    This function is intentionally limited to the configured local
    Ollama endpoint.
    """

    url = f"{_get_ollama_url()}{path}"

    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
        },
        method="GET",
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=timeout,
        ) as response:
            payload = response.read()

        data = json.loads(
            payload.decode(
                "utf-8",
                errors="replace",
            )
        )

        return (
            data
            if isinstance(data, dict)
            else None
        )

    except (
        urllib.error.URLError,
        urllib.error.HTTPError,
        TimeoutError,
        json.JSONDecodeError,
        OSError,
        ValueError,
    ):
        return None


def _safe_float(
    value: Any,
) -> Optional[float]:
    try:
        return float(value)
    except (
        TypeError,
        ValueError,
    ):
        return None


def _safe_int(
    value: Any,
) -> Optional[int]:
    try:
        return int(value)
    except (
        TypeError,
        ValueError,
    ):
        return None


# ---------------------------------------------------------------------------
# SYSTEM METRICS
# ---------------------------------------------------------------------------


def _get_cpu_metrics() -> Dict[str, Any]:
    try:
        cpu_percent = psutil.cpu_percent(
            interval=0.15
        )

        logical_processors = psutil.cpu_count(
            logical=True
        )

        physical_cores = psutil.cpu_count(
            logical=False
        )

        return {
            "status": "AVAILABLE",
            "usage_percent": round(
                float(cpu_percent),
                1,
            ),
            "logical_processors": logical_processors,
            "logical_cores": logical_processors,
            "physical_cores": physical_cores,
        }

    except Exception as exc:
        return {
            "status": "UNAVAILABLE",
            "error": str(exc),
        }


def _get_memory_metrics() -> Dict[str, Any]:
    try:
        memory = psutil.virtual_memory()

        return {
            "status": "AVAILABLE",
            "total_gb": round(
                memory.total / (1024**3),
                2,
            ),
            "used_gb": round(
                memory.used / (1024**3),
                2,
            ),
            "available_gb": round(
                memory.available / (1024**3),
                2,
            ),
            "usage_percent": round(
                float(memory.percent),
                1,
            ),
        }

    except Exception as exc:
        return {
            "status": "UNAVAILABLE",
            "error": str(exc),
        }


def _get_gpu_metrics() -> Dict[str, Any]:
    """
    Read NVIDIA GPU state through nvidia-smi when available.

    No fabricated GPU values are returned.
    """

    try:
        completed = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.total,memory.used,"
                "memory.free,utilization.gpu",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        )

        if (
            completed.returncode != 0
            or not completed.stdout.strip()
        ):
            return {
                "status": "UNAVAILABLE",
                "reason": (
                    "nvidia-smi did not return GPU telemetry."
                ),
                "devices": [],
            }

        devices: List[Dict[str, Any]] = []

        for line in completed.stdout.splitlines():
            values = [
                item.strip()
                for item in line.split(",")
            ]

            if len(values) < 5:
                continue

            name = values[0]

            memory_total_mb = _safe_float(
                values[1]
            )

            memory_used_mb = _safe_float(
                values[2]
            )

            memory_free_mb = _safe_float(
                values[3]
            )

            utilization_percent = _safe_float(
                values[4]
            )

            vram_usage_percent = None

            if (
                memory_total_mb is not None
                and memory_total_mb > 0
                and memory_used_mb is not None
            ):
                vram_usage_percent = round(
                    (
                        memory_used_mb
                        / memory_total_mb
                    )
                    * 100,
                    1,
                )

            devices.append(
                {
                    "name": name,
                    "memory_total_mb": memory_total_mb,
                    "memory_used_mb": memory_used_mb,
                    "memory_free_mb": memory_free_mb,
                    "utilization_percent": (
                        round(
                            utilization_percent,
                            1,
                        )
                        if utilization_percent
                        is not None
                        else None
                    ),
                    "vram_usage_percent": (
                        vram_usage_percent
                    ),
                }
            )

        if not devices:
            return {
                "status": "UNAVAILABLE",
                "reason": (
                    "GPU telemetry could not be parsed."
                ),
                "devices": [],
            }

        primary = devices[0]

        return {
            "status": "AVAILABLE",
            "device_count": len(
                devices
            ),
            "name": primary.get(
                "name"
            ),
            "memory_total_mb": primary.get(
                "memory_total_mb"
            ),
            "memory_used_mb": primary.get(
                "memory_used_mb"
            ),
            "memory_free_mb": primary.get(
                "memory_free_mb"
            ),
            "utilization_percent": primary.get(
                "utilization_percent"
            ),
            "vram_usage_percent": primary.get(
                "vram_usage_percent"
            ),
            "devices": devices,
        }

    except (
        FileNotFoundError,
        subprocess.SubprocessError,
        OSError,
        ValueError,
    ) as exc:
        return {
            "status": "UNAVAILABLE",
            "reason": str(exc),
            "devices": [],
        }


# ---------------------------------------------------------------------------
# MODEL RUNTIME
# ---------------------------------------------------------------------------


def _get_model_runtime() -> Dict[str, Any]:
    """
    Inspect the local Ollama runtime and persisted NOVA model state.

    /api/tags provides installed model information.

    /api/ps is queried best-effort for currently loaded model information.
    Only fields actually returned by Ollama are exposed.
    """

    endpoint = _get_ollama_url()

    tags = _ollama_get(
        "/api/tags"
    )

    processes = _ollama_get(
        "/api/ps"
    )

    models: List[Dict[str, Any]] = []

    if isinstance(tags, dict):
        raw_models = tags.get(
            "models",
            [],
        )

        if isinstance(
            raw_models,
            list,
        ):
            for item in raw_models:
                if not isinstance(
                    item,
                    dict,
                ):
                    continue

                name = item.get(
                    "name"
                )

                if not name:
                    continue

                model_size = _safe_int(
                    item.get(
                        "size"
                    )
                )

                details = item.get(
                    "details"
                )

                models.append(
                    {
                        "name": name,
                        "size_bytes": model_size,
                        "size_gb": (
                            round(
                                model_size
                                / (1024**3),
                                2,
                            )
                            if model_size
                            is not None
                            else None
                        ),
                        "details": (
                            details
                            if isinstance(
                                details,
                                dict,
                            )
                            else None
                        ),
                    }
                )

    state = _read_json(
        MODEL_RUNTIME_STATE
    )

    active_model = None

    if state:
        active_model = state.get(
            "active_model"
        )

    running_models: List[
        Dict[str, Any]
    ] = []

    if isinstance(
        processes,
        dict,
    ):
        raw_running = processes.get(
            "models",
            [],
        )

        if isinstance(
            raw_running,
            list,
        ):
            for item in raw_running:
                if not isinstance(
                    item,
                    dict,
                ):
                    continue

                running_models.append(
                    {
                        "name": item.get(
                            "name"
                        ),
                        "size_bytes": _safe_int(
                            item.get(
                                "size"
                            )
                        ),
                        "size_vram_bytes": _safe_int(
                            item.get(
                                "size_vram"
                            )
                        ),
                        "context_length": _safe_int(
                            item.get(
                                "context_length"
                            )
                        ),
                        "expires_at": item.get(
                            "expires_at"
                        ),
                    }
                )

    runtime_online = (
        tags is not None
    )

    status = (
        "READY"
        if runtime_online
        else "OFFLINE"
    )

    active_model_info = None

    for model in models:
        if (
            active_model
            and model.get("name")
            == active_model
        ):
            active_model_info = model
            break

    return {
        "provider": "ollama",
        "endpoint": endpoint,
        "status": status,
        "online": runtime_online,
        "installed_model_count": len(
            models
        ),
        "installed_models": [
            item.get(
                "name"
            )
            for item in models
            if item.get(
                "name"
            )
        ],
        "installed_model_details": models,
        "active_model": active_model,
        "active_model_size_bytes": (
            active_model_info.get(
                "size_bytes"
            )
            if active_model_info
            else None
        ),
        "active_model_size_gb": (
            active_model_info.get(
                "size_gb"
            )
            if active_model_info
            else None
        ),
        "running_models": running_models,
        "running_model_count": len(
            running_models
        ),
        "state_file": str(
            MODEL_RUNTIME_STATE
        ),
        "state_file_exists": (
            MODEL_RUNTIME_STATE.exists()
        ),
    }


# ---------------------------------------------------------------------------
# LOCAL STORAGE
# ---------------------------------------------------------------------------


def _get_local_storage() -> Dict[str, Any]:
    return {
        "knowledge_documents": _directory_status(
            KNOWLEDGE_DOCUMENTS
        ),
        "knowledge_uploads": _directory_status(
            KNOWLEDGE_UPLOADS
        ),
        "knowledge_vectorstore": _directory_status(
            KNOWLEDGE_VECTORSTORE
        ),
        "sandbox": _directory_status(
            SANDBOX_ROOT
        ),
        "workspace": _directory_status(
            WORKSPACE_ROOT
        ),
        "runtime_data": _directory_status(
            DATA_ROOT
        ),
    }


# ---------------------------------------------------------------------------
# SOVEREIGNTY VERIFICATION
# ---------------------------------------------------------------------------


def _verification_checks(
    runtime: Dict[str, Any],
    storage: Dict[str, Any],
    network: Dict[str, Any],
) -> Dict[str, Any]:
    checks: List[
        Dict[str, Any]
    ] = []

    runtime_ok = bool(
        runtime.get(
            "online"
        )
    )

    checks.append(
        {
            "id": "local_model_runtime",
            "label": "Local model runtime",
            "status": (
                "PASS"
                if runtime_ok
                else "FAIL"
            ),
            "detail": (
                "Ollama runtime is reachable."
                if runtime_ok
                else "Ollama runtime is not reachable."
            ),
        }
    )

    knowledge_paths = [
        storage.get(
            "knowledge_documents",
            {},
        ),
        storage.get(
            "knowledge_uploads",
            {},
        ),
        storage.get(
            "knowledge_vectorstore",
            {},
        ),
    ]

    knowledge_ok = all(
        item.get(
            "status"
        )
        == "AVAILABLE"
        for item in knowledge_paths
    )

    checks.append(
        {
            "id": "local_knowledge_storage",
            "label": "Local knowledge storage",
            "status": (
                "PASS"
                if knowledge_ok
                else "CHECK"
            ),
            "detail": (
                "Knowledge storage paths are available."
                if knowledge_ok
                else "One or more knowledge storage paths require inspection."
            ),
        }
    )

    workspace_ok = (
        storage.get(
            "workspace",
            {},
        ).get(
            "status"
        )
        == "AVAILABLE"
    )

    checks.append(
        {
            "id": "local_workspace",
            "label": "Local workspace",
            "status": (
                "PASS"
                if workspace_ok
                else "CHECK"
            ),
            "detail": (
                "NOVA workspace storage is available."
                if workspace_ok
                else "NOVA workspace storage is not available."
            ),
        }
    )

    network_tracking = (
        network.get(
            "tracking"
        )
        == "application_level"
    )

    checks.append(
        {
            "id": "network_tracking",
            "label": "Network activity tracking",
            "status": (
                "PASS"
                if network_tracking
                else "CHECK"
            ),
            "detail": (
                "NOVA application-level network ledger is active."
                if network_tracking
                else "Network ledger status requires inspection."
            ),
        }
    )

    passed = sum(
        1
        for item in checks
        if item.get(
            "status"
        )
        == "PASS"
    )

    failed = sum(
        1
        for item in checks
        if item.get(
            "status"
        )
        == "FAIL"
    )

    needs_check = sum(
        1
        for item in checks
        if item.get(
            "status"
        )
        == "CHECK"
    )

    if failed > 0:
        overall_status = (
            "ATTENTION_REQUIRED"
        )
    elif needs_check > 0:
        overall_status = (
            "CHECK_REQUIRED"
        )
    else:
        overall_status = "VERIFIED"

    return {
        "status": overall_status,
        "passed": passed,
        "failed": failed,
        "checks_required": needs_check,
        "checks": checks,
    }


# ---------------------------------------------------------------------------
# MAIN SERVICE
# ---------------------------------------------------------------------------


class SovereigntyService:
    """
    Main backend service for the NOVA Sovereignty Center.
    """

    def get_snapshot(
        self,
    ) -> Dict[str, Any]:
        runtime = _get_model_runtime()

        storage = _get_local_storage()

        cpu = _get_cpu_metrics()

        memory = _get_memory_metrics()

        gpu = _get_gpu_metrics()

        network = dict(
            network_ledger.get_summary()
        )

        if network.get(
            "tracking"
        ) == "application_level":
            network["status"] = (
                "TRACKING"
            )
        else:
            network["status"] = (
                "NOT_REPORTED"
            )

        verification = _verification_checks(
            runtime,
            storage,
            network,
        )

        return {
            "timestamp": _utc_now(),
            "scope": (
                "NOVA application and local runtime state"
            ),
            "truthfulness": {
                "synthetic_metrics": False,
                "network_measurement_scope": (
                    "NOVA-recorded application-level events only"
                ),
            },
            "runtime": runtime,
            "storage": storage,
            "hardware": {
                "cpu": cpu,
                "memory": memory,
                "gpu": gpu,
            },
            "network": network,
            "verification": verification,
        }


# ---------------------------------------------------------------------------
# SINGLETON
# ---------------------------------------------------------------------------

sovereignty_service = SovereigntyService()