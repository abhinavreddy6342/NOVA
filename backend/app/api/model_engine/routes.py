from __future__ import annotations

import inspect
import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.ai_config import (
    get_active_model_name,
    set_active_model_name,
)
from app.models.model_registry import (
    MODEL_REGISTRY,
    get_enabled_models,
    sync_discovered_models,
)
from app.services.audit.service import (
    audit_service,
    create_request_id,
)
from app.services.model_engine.model_router import (
    get_task_routing,
    route_request,
    set_task_routing,
)
from app.services.model_engine.ollama_manager import (
    get_verified_activity,
    ollama_manager,
)


router = APIRouter(
    prefix="/api/models",
    tags=["Model Engine"],
)


# ---------------------------------------------------------------------------
# REQUEST MODELS
# ---------------------------------------------------------------------------

class RouteRequest(BaseModel):
    text: str = Field(
        ...,
        min_length=1,
        description="User request to classify and route.",
    )


class GenerateRequest(BaseModel):
    prompt: str = Field(
        ...,
        min_length=1,
    )

    model: Optional[str] = Field(
        default=None,
    )

    system: Optional[str] = Field(
        default=None,
    )

    temperature: float = Field(
        default=0.4,
        ge=0.0,
        le=2.0,
    )

    num_predict: int = Field(
        default=512,
        ge=1,
        le=8192,
    )

    task_type: Optional[str] = Field(
        default=None,
    )


class SetActiveModelRequest(BaseModel):
    model: str = Field(
        ...,
        min_length=1,
    )


class TestModelRequest(BaseModel):
    model: str = Field(
        ...,
        min_length=1,
    )

    prompt: str = Field(
        ...,
        min_length=1,
    )

    system: Optional[str] = Field(
        default=None,
    )


class SetTaskRoutingRequest(BaseModel):
    routing: Dict[str, str] = Field(
        ...,
    )


# ---------------------------------------------------------------------------
# AUDIT HELPERS
# ---------------------------------------------------------------------------

def _safe_audit(
    method_name: str,
    *,
    action: str,
    status: str,
    message: str,
    request_id: Optional[str] = None,
    resource_id: Optional[str] = None,
    model: Optional[str] = None,
    task_type: Optional[str] = None,
    duration_ms: Optional[float] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Best-effort adapter around NOVA's audit service.

    Audit failures must never break the Model Engine itself.
    """
    try:
        method = getattr(
            audit_service,
            method_name,
            None,
        )

        if method is None:
            return

        payload: Dict[str, Any] = {
            "category": "model",
            "action": action,
            "service": "model_engine",
            "status": status,
            "message": message,
            "request_id": request_id,
            "resource_id": resource_id,
            "model": model,
            "task_type": task_type,
            "duration_ms": duration_ms,
            "metadata": metadata or {},
        }

        try:
            signature = inspect.signature(
                method
            )

            parameters = signature.parameters

            accepts_var_kwargs = any(
                parameter.kind
                == inspect.Parameter.VAR_KEYWORD
                for parameter in parameters.values()
            )

            if not accepts_var_kwargs:
                payload = {
                    key: value
                    for key, value in payload.items()
                    if key in parameters
                }

        except Exception:
            pass

        method(
            **payload
        )

    except Exception as exc:
        print(
            "[NOVA AUDIT WARNING] "
            f"Model Engine audit failed: {exc}"
        )


def _audit_success(
    *,
    action: str,
    message: str,
    request_id: Optional[str] = None,
    resource_id: Optional[str] = None,
    model: Optional[str] = None,
    task_type: Optional[str] = None,
    duration_ms: Optional[float] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    _safe_audit(
        "success",
        action=action,
        status="SUCCESS",
        message=message,
        request_id=request_id,
        resource_id=resource_id,
        model=model,
        task_type=task_type,
        duration_ms=duration_ms,
        metadata=metadata,
    )


def _audit_failure(
    *,
    action: str,
    message: str,
    request_id: Optional[str] = None,
    resource_id: Optional[str] = None,
    model: Optional[str] = None,
    task_type: Optional[str] = None,
    duration_ms: Optional[float] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    _safe_audit(
        "failure",
        action=action,
        status="FAILED",
        message=message,
        request_id=request_id,
        resource_id=resource_id,
        model=model,
        task_type=task_type,
        duration_ms=duration_ms,
        metadata=metadata,
    )


def _duration_ms(
    started_at: float,
) -> float:
    return round(
        (
            time.perf_counter()
            - started_at
        )
        * 1000,
        2,
    )


# ---------------------------------------------------------------------------
# MODEL LIST & DISCOVERY
# ---------------------------------------------------------------------------

@router.get("")
def list_models() -> Dict[str, Any]:
    """
    Return the actual local Ollama model inventory.
    """

    local_models = (
        ollama_manager.list_models(
            enrich=True
        )
    )

    sync_discovered_models(
        local_models
    )

    local_by_name = {
        str(
            model.get(
                "name",
                "",
            )
        ).strip(): model
        for model in local_models
        if str(
            model.get(
                "name",
                "",
            )
        ).strip()
    }

    active_model = (
        get_active_model_name()
    )

    registered = (
        get_enabled_models()
    )

    models: List[
        Dict[str, Any]
    ] = []

    for profile in registered:
        local_info = (
            local_by_name.get(
                profile.name,
                {},
            )
        )

        is_installed = (
            profile.name
            in local_by_name
        )

        is_active = (
            profile.name
            == active_model
            and is_installed
        )

        models.append(
            {
                "name": profile.name,
                "provider": profile.provider,
                "capabilities": profile.capabilities,
                "context_window": (
                    local_info.get(
                        "context_length",
                        "NOT AVAILABLE",
                    )
                ),
                "vision": profile.vision,
                "code": profile.code,
                "reasoning": profile.reasoning,
                "enabled": profile.enabled,
                "installed": is_installed,
                "active": is_active,
                "status": (
                    "ACTIVE"
                    if is_active
                    else (
                        "INSTALLED"
                        if is_installed
                        else "NOT AVAILABLE"
                    )
                ),
                "description": (
                    profile.description
                    or "NOT AVAILABLE"
                ),
                "size_human": local_info.get(
                    "size_human",
                    "NOT AVAILABLE",
                ),
                "size_bytes": local_info.get(
                    "size_bytes",
                    0,
                ),
                "parameter_size": local_info.get(
                    "parameter_size",
                    "NOT AVAILABLE",
                ),
                "format": local_info.get(
                    "format",
                    "NOT AVAILABLE",
                ),
                "family": local_info.get(
                    "family",
                    "NOT AVAILABLE",
                ),
                "quantization_level": local_info.get(
                    "quantization_level",
                    "NOT AVAILABLE",
                ),
                "context_length": local_info.get(
                    "context_length",
                    "NOT AVAILABLE",
                ),
            }
        )

    return {
        "count": len(models),
        "installed_count": len(
            local_models
        ),
        "active_model": active_model,
        "models": models,
    }


# ---------------------------------------------------------------------------
# HEALTH & STATUS
# ---------------------------------------------------------------------------

@router.get("/health")
@router.get("/status")
def model_status() -> Dict[str, Any]:
    """
    Return real local Ollama runtime health.
    """

    ollama_online = (
        ollama_manager.is_available()
    )

    local_models = (
        ollama_manager.list_models()
        if ollama_online
        else []
    )

    active_model = (
        get_active_model_name()
    )

    return {
        "status": (
            "online"
            if ollama_online
            else "offline"
        ),
        "state": (
            "READY"
            if ollama_online
            else "OFFLINE"
        ),
        "provider": "ollama",
        "endpoint": (
            ollama_manager.base_url
            if ollama_online
            else ollama_manager.base_url
        ),
        "local_model_count": len(
            local_models
        ),
        "active_model": active_model,
        "local_models": [
            model.get(
                "name"
            )
            for model in local_models
            if model.get("name")
        ],
    }


# ---------------------------------------------------------------------------
# ACTIVE MODEL
# ---------------------------------------------------------------------------

@router.get("/active")
def get_active_model() -> Dict[str, Any]:
    """
    Return the currently persisted active model and its verified state.
    """

    active_name = (
        get_active_model_name()
    )

    runtime_online = (
        ollama_manager.is_available()
    )

    installed = (
        runtime_online
        and ollama_manager.model_exists(
            active_name
        )
    )

    profile = (
        MODEL_REGISTRY.get(
            active_name
        )
    )

    if not runtime_online:
        status = "OFFLINE"
    elif installed:
        status = "LOCAL / READY"
    else:
        status = "UNAVAILABLE"

    return {
        "active_model": active_name,
        "installed": installed,
        "status": status,
        "description": (
            profile.description
            if profile
            else "NOT AVAILABLE"
        ),
    }


@router.post("/active")
def change_active_model(
    request: SetActiveModelRequest,
) -> Dict[str, Any]:
    """
    Change the active local model only after runtime verification.
    """

    started_at = time.perf_counter()
    request_id = create_request_id()

    target_model = (
        request.model.strip()
    )

    if not target_model:
        _audit_failure(
            action="active_model_change",
            message=(
                "Active model change was rejected because "
                "the model name was empty."
            ),
            request_id=request_id,
            duration_ms=_duration_ms(
                started_at
            ),
        )

        raise HTTPException(
            status_code=400,
            detail=(
                "Model name cannot be empty."
            ),
        )

    try:
        if not ollama_manager.is_available():
            _audit_failure(
                action="active_model_change",
                message=(
                    "Active model change failed because "
                    "the local Ollama runtime is offline."
                ),
                request_id=request_id,
                resource_id=target_model,
                model=target_model,
                duration_ms=_duration_ms(
                    started_at
                ),
                metadata={
                    "reason": "runtime_offline",
                },
            )

            raise HTTPException(
                status_code=503,
                detail=(
                    "Local Ollama runtime is offline."
                ),
            )

        if not ollama_manager.model_exists(
            target_model
        ):
            _audit_failure(
                action="active_model_change",
                message=(
                    "Active model change failed because "
                    "the requested model is not installed locally."
                ),
                request_id=request_id,
                resource_id=target_model,
                model=target_model,
                duration_ms=_duration_ms(
                    started_at
                ),
                metadata={
                    "reason": "model_not_installed",
                },
            )

            raise HTTPException(
                status_code=404,
                detail=(
                    f"Local model '{target_model}' "
                    "is not installed in Ollama."
                ),
            )

        previous_model = (
            get_active_model_name()
        )

        confirmed_model = (
            set_active_model_name(
                target_model
            )
        )

        _audit_success(
            action="active_model_change",
            message=(
                "Active local model changed successfully."
            ),
            request_id=request_id,
            resource_id=confirmed_model,
            model=confirmed_model,
            duration_ms=_duration_ms(
                started_at
            ),
            metadata={
                "previous_model": previous_model,
                "active_model": confirmed_model,
            },
        )

        return {
            "status": "success",
            "active_model": confirmed_model,
            "message": (
                f"Active model updated to "
                f"'{confirmed_model}'."
            ),
        }

    except HTTPException:
        raise

    except Exception as exc:
        _audit_failure(
            action="active_model_change",
            message="Active local model change failed.",
            request_id=request_id,
            resource_id=target_model,
            model=target_model,
            duration_ms=_duration_ms(
                started_at
            ),
            metadata={
                "error_type": type(
                    exc
                ).__name__,
                "error": str(exc),
            },
        )

        raise HTTPException(
            status_code=500,
            detail=(
                f"Active model update failed: {exc}"
            ),
        ) from exc


# ---------------------------------------------------------------------------
# MODEL TEST CONSOLE
# ---------------------------------------------------------------------------

@router.post("/test")
def test_model(
    request: TestModelRequest,
) -> Dict[str, Any]:
    """
    Run a real local inference test.
    """

    started_at = time.perf_counter()
    request_id = create_request_id()

    target_model = (
        request.model.strip()
    )

    prompt = (
        request.prompt.strip()
    )

    if not target_model:
        _audit_failure(
            action="model_test",
            message=(
                "Model test was rejected because "
                "the model name was empty."
            ),
            request_id=request_id,
            duration_ms=_duration_ms(
                started_at
            ),
        )

        raise HTTPException(
            status_code=400,
            detail=(
                "Model name cannot be empty."
            ),
        )

    if not prompt:
        _audit_failure(
            action="model_test",
            message=(
                "Model test was rejected because "
                "the test prompt was empty."
            ),
            request_id=request_id,
            resource_id=target_model,
            model=target_model,
            duration_ms=_duration_ms(
                started_at
            ),
        )

        raise HTTPException(
            status_code=400,
            detail=(
                "Test prompt cannot be empty."
            ),
        )

    if not ollama_manager.is_available():
        _audit_failure(
            action="model_test",
            message=(
                "Model test failed because "
                "the local Ollama runtime is offline."
            ),
            request_id=request_id,
            resource_id=target_model,
            model=target_model,
            task_type="test_console",
            duration_ms=_duration_ms(
                started_at
            ),
            metadata={
                "reason": "runtime_offline",
            },
        )

        raise HTTPException(
            status_code=503,
            detail=(
                "Local Ollama runtime is offline."
            ),
        )

    if not ollama_manager.model_exists(
        target_model
    ):
        _audit_failure(
            action="model_test",
            message=(
                "Model test failed because "
                "the requested model is not installed locally."
            ),
            request_id=request_id,
            resource_id=target_model,
            model=target_model,
            task_type="test_console",
            duration_ms=_duration_ms(
                started_at
            ),
            metadata={
                "reason": "model_not_installed",
            },
        )

        raise HTTPException(
            status_code=404,
            detail=(
                f"Model '{target_model}' "
                "is not installed locally."
            ),
        )

    try:
        result = (
            ollama_manager.generate(
                model=target_model,
                prompt=prompt,
                system=request.system,
                temperature=0.3,
                num_predict=512,
                stream=False,
                task_type="test_console",
            )
        )

        model_used = result.get(
            "model_used",
            target_model,
        )

        latency_ms = result.get(
            "latency_ms"
        )

        response_text = str(
            result.get(
                "response",
                "",
            )
            or ""
        ).strip()

        _audit_success(
            action="model_test",
            message=(
                "Local model test completed successfully."
            ),
            request_id=request_id,
            resource_id=target_model,
            model=str(
                model_used
                or target_model
            ),
            task_type="test_console",
            duration_ms=_duration_ms(
                started_at
            ),
            metadata={
                "requested_model": target_model,
                "model_used": model_used,
                "latency_ms": latency_ms,
                "prompt_length": len(
                    prompt
                ),
                "response_length": len(
                    response_text
                ),
                "done": result.get(
                    "done",
                    True,
                ),
            },
        )

        return {
            "status": "SUCCESS",
            "model_used": model_used,
            "response": response_text,
            "latency_ms": latency_ms,
            "done": result.get(
                "done",
                True,
            ),
        }

    except ValueError as exc:
        _audit_failure(
            action="model_test",
            message="Local model test failed validation.",
            request_id=request_id,
            resource_id=target_model,
            model=target_model,
            task_type="test_console",
            duration_ms=_duration_ms(
                started_at
            ),
            metadata={
                "error_type": type(
                    exc
                ).__name__,
                "error": str(exc),
            },
        )

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except RuntimeError as exc:
        _audit_failure(
            action="model_test",
            message="Local model test failed during model execution.",
            request_id=request_id,
            resource_id=target_model,
            model=target_model,
            task_type="test_console",
            duration_ms=_duration_ms(
                started_at
            ),
            metadata={
                "error_type": type(
                    exc
                ).__name__,
                "error": str(exc),
            },
        )

        raise HTTPException(
            status_code=503,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        _audit_failure(
            action="model_test",
            message="Local model test failed unexpectedly.",
            request_id=request_id,
            resource_id=target_model,
            model=target_model,
            task_type="test_console",
            duration_ms=_duration_ms(
                started_at
            ),
            metadata={
                "error_type": type(
                    exc
                ).__name__,
                "error": str(exc),
            },
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Local model test failed: "
                f"{exc}"
            ),
        ) from exc


# ---------------------------------------------------------------------------
# TASK ROUTING
# ---------------------------------------------------------------------------

@router.get("/routing")
def get_routing_config() -> Dict[str, Any]:
    return {
        "routing": get_task_routing(),
        "tasks": [
            {
                "id": "general",
                "label": "General Chat",
            },
            {
                "id": "coding",
                "label": "Coding",
            },
            {
                "id": "document",
                "label": "Document Analysis",
            },
            {
                "id": "reasoning",
                "label": "Reasoning",
            },
            {
                "id": "knowledge",
                "label": "Knowledge / RAG",
            },
            {
                "id": "mission",
                "label": "Mission Execution",
            },
        ],
    }


@router.post("/routing")
def update_routing_config(
    request: SetTaskRoutingRequest,
) -> Dict[str, Any]:
    started_at = time.perf_counter()
    request_id = create_request_id()

    valid_task_keys = {
        "general",
        "coding",
        "document",
        "reasoning",
        "knowledge",
        "mission",
    }

    try:
        for (
            task_key,
            model_name,
        ) in request.routing.items():

            if task_key not in valid_task_keys:
                _audit_failure(
                    action="routing_update",
                    message=(
                        "Task routing update was rejected "
                        "because an unknown task key was supplied."
                    ),
                    request_id=request_id,
                    task_type=task_key,
                    duration_ms=_duration_ms(
                        started_at
                    ),
                    metadata={
                        "unknown_task": task_key,
                    },
                )

                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Unknown routing task: "
                        f"{task_key}"
                    ),
                )

            clean_name = (
                str(
                    model_name or ""
                ).strip()
            )

            if not clean_name:
                _audit_failure(
                    action="routing_update",
                    message=(
                        "Task routing update was rejected "
                        "because a model assignment was empty."
                    ),
                    request_id=request_id,
                    task_type=task_key,
                    duration_ms=_duration_ms(
                        started_at
                    ),
                    metadata={
                        "task": task_key,
                    },
                )

                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Model assigned to "
                        f"'{task_key}' cannot be empty."
                    ),
                )

            if not ollama_manager.is_available():
                _audit_failure(
                    action="routing_update",
                    message=(
                        "Task routing update failed because "
                        "the local Ollama runtime is offline."
                    ),
                    request_id=request_id,
                    model=clean_name,
                    task_type=task_key,
                    duration_ms=_duration_ms(
                        started_at
                    ),
                    metadata={
                        "reason": "runtime_offline",
                    },
                )

                raise HTTPException(
                    status_code=503,
                    detail=(
                        "Local Ollama runtime is offline."
                    ),
                )

            if not ollama_manager.model_exists(
                clean_name
            ):
                _audit_failure(
                    action="routing_update",
                    message=(
                        "Task routing update failed because "
                        "the assigned model is not installed locally."
                    ),
                    request_id=request_id,
                    resource_id=task_key,
                    model=clean_name,
                    task_type=task_key,
                    duration_ms=_duration_ms(
                        started_at
                    ),
                    metadata={
                        "reason": "model_not_installed",
                    },
                )

                raise HTTPException(
                    status_code=404,
                    detail=(
                        f"Local model '{clean_name}' "
                        f"assigned to '{task_key}' "
                        "is not installed."
                    ),
                )

        previous_routing = get_task_routing()

        updated = set_task_routing(
            request.routing
        )

        _audit_success(
            action="routing_update",
            message=(
                "Task routing configuration saved successfully."
            ),
            request_id=request_id,
            duration_ms=_duration_ms(
                started_at
            ),
            metadata={
                "previous_routing": previous_routing,
                "updated_routing": updated,
                "task_count": len(
                    request.routing
                ),
            },
        )

        return {
            "status": "success",
            "routing": updated,
            "message": (
                "Task routing configuration "
                "saved successfully."
            ),
        }

    except HTTPException:
        raise

    except Exception as exc:
        _audit_failure(
            action="routing_update",
            message="Task routing configuration update failed.",
            request_id=request_id,
            duration_ms=_duration_ms(
                started_at
            ),
            metadata={
                "error_type": type(
                    exc
                ).__name__,
                "error": str(exc),
                "requested_routing": request.routing,
            },
        )

        raise HTTPException(
            status_code=500,
            detail=(
                f"Task routing update failed: {exc}"
            ),
        ) from exc


# ---------------------------------------------------------------------------
# VERIFIED ACTIVITY
# ---------------------------------------------------------------------------

@router.get("/activity")
def get_activity() -> Dict[str, Any]:
    activity = (
        get_verified_activity()
    )

    return {
        "activity": (
            activity
            if activity.get(
                "latest_model_used"
            )
            else None
        ),
    }


# ---------------------------------------------------------------------------
# ROUTING DECISION
# ---------------------------------------------------------------------------

@router.post("/route")
def route_model(
    request: RouteRequest,
) -> Dict[str, Any]:
    started_at = time.perf_counter()
    request_id = create_request_id()

    try:
        decision = route_request(
            request.text
        )

        _audit_success(
            action="routing_decision",
            message=(
                "Model routing decision completed successfully."
            ),
            request_id=request_id,
            resource_id=str(
                decision.model_name
            ),
            model=decision.model_name,
            task_type=decision.task_type.value,
            duration_ms=_duration_ms(
                started_at
            ),
            metadata={
                "matched_tasks": [
                    task.value
                    for task in
                    decision.matched_tasks
                ],
                "score": decision.score,
                "reason": decision.reason,
                "input_length": len(
                    request.text
                ),
            },
        )

        return {
            "model": decision.model_name,
            "task_type": (
                decision.task_type.value
            ),
            "matched_tasks": [
                task.value
                for task
                in decision.matched_tasks
            ],
            "score": decision.score,
            "reason": decision.reason,
        }

    except RuntimeError as exc:
        _audit_failure(
            action="routing_decision",
            message=(
                "Model routing decision failed "
                "during local routing evaluation."
            ),
            request_id=request_id,
            duration_ms=_duration_ms(
                started_at
            ),
            metadata={
                "error_type": type(
                    exc
                ).__name__,
                "error": str(exc),
                "input_length": len(
                    request.text
                ),
            },
        )

        raise HTTPException(
            status_code=503,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        _audit_failure(
            action="routing_decision",
            message="Model routing decision failed.",
            request_id=request_id,
            duration_ms=_duration_ms(
                started_at
            ),
            metadata={
                "error_type": type(
                    exc
                ).__name__,
                "error": str(exc),
                "input_length": len(
                    request.text
                ),
            },
        )

        raise HTTPException(
            status_code=500,
            detail=(
                f"Model routing failed: {exc}"
            ),
        ) from exc


# ---------------------------------------------------------------------------
# GENERATE
# ---------------------------------------------------------------------------

@router.post("/generate")
def generate_model_response(
    request: GenerateRequest,
) -> Dict[str, Any]:
    started_at = time.perf_counter()
    request_id = create_request_id()

    selected_model: str
    routing = None
    task_type: str = (
        request.task_type
        or "direct_generate"
    )

    try:
        if request.model:
            selected_model = (
                request.model.strip()
            )

            if not selected_model:
                _audit_failure(
                    action="model_generate",
                    message=(
                        "Model generation was rejected "
                        "because the model name was empty."
                    ),
                    request_id=request_id,
                    task_type=task_type,
                    duration_ms=_duration_ms(
                        started_at
                    ),
                )

                raise HTTPException(
                    status_code=400,
                    detail=(
                        "Model name cannot be empty."
                    ),
                )

            if not ollama_manager.is_available():
                _audit_failure(
                    action="model_generate",
                    message=(
                        "Model generation failed because "
                        "the local Ollama runtime is offline."
                    ),
                    request_id=request_id,
                    model=selected_model,
                    task_type=task_type,
                    duration_ms=_duration_ms(
                        started_at
                    ),
                    metadata={
                        "reason": "runtime_offline",
                    },
                )

                raise HTTPException(
                    status_code=503,
                    detail=(
                        "Local Ollama runtime is offline."
                    ),
                )

            if not ollama_manager.model_exists(
                selected_model
            ):
                _audit_failure(
                    action="model_generate",
                    message=(
                        "Model generation failed because "
                        "the requested local model is not installed."
                    ),
                    request_id=request_id,
                    model=selected_model,
                    task_type=task_type,
                    duration_ms=_duration_ms(
                        started_at
                    ),
                    metadata={
                        "reason": "model_not_installed",
                    },
                )

                raise HTTPException(
                    status_code=404,
                    detail=(
                        f"Local model "
                        f"'{selected_model}' "
                        "is not installed."
                    ),
                )

            task_type = (
                request.task_type
                or "direct_generate"
            )

        else:
            routing = route_request(
                request.prompt,
                task_key=request.task_type,
            )

            selected_model = (
                routing.model_name
            )

            task_type = (
                routing.task_type.value
            )

        result = (
            ollama_manager.generate(
                model=selected_model,
                prompt=request.prompt,
                system=request.system,
                temperature=request.temperature,
                num_predict=request.num_predict,
                stream=False,
                task_type=task_type,
            )
        )

        model_used = result.get(
            "model_used",
            selected_model,
        )

        response_text = str(
            result.get(
                "response",
                "",
            )
            or ""
        ).strip()

        latency_ms = result.get(
            "latency_ms"
        )

        _audit_success(
            action="model_generate",
            message=(
                "Local model generation completed successfully."
            ),
            request_id=request_id,
            resource_id=str(
                model_used
                or selected_model
            ),
            model=str(
                model_used
                or selected_model
            ),
            task_type=task_type,
            duration_ms=_duration_ms(
                started_at
            ),
            metadata={
                "requested_model": request.model,
                "selected_model": selected_model,
                "model_used": model_used,
                "latency_ms": latency_ms,
                "prompt_length": len(
                    request.prompt
                ),
                "response_length": len(
                    response_text
                ),
                "temperature": request.temperature,
                "num_predict": request.num_predict,
                "routing": (
                    {
                        "task_type": (
                            routing.task_type.value
                        ),
                        "matched_tasks": [
                            task.value
                            for task
                            in routing.matched_tasks
                        ],
                        "score": routing.score,
                        "reason": routing.reason,
                    }
                    if routing
                    else None
                ),
            },
        )

        return {
            "status": "SUCCESS",
            "model": model_used,
            "model_used": model_used,
            "response": response_text,
            "done": result.get(
                "done",
                True,
            ),
            "latency_ms": latency_ms,
            "routing": (
                {
                    "task_type": (
                        routing.task_type.value
                    ),
                    "matched_tasks": [
                        task.value
                        for task
                        in routing.matched_tasks
                    ],
                    "score": routing.score,
                    "reason": routing.reason,
                }
                if routing
                else None
            ),
        }

    except HTTPException:
        raise

    except ValueError as exc:
        _audit_failure(
            action="model_generate",
            message="Local model generation failed validation.",
            request_id=request_id,
            model=selected_model
            if "selected_model" in locals()
            else request.model,
            task_type=task_type,
            duration_ms=_duration_ms(
                started_at
            ),
            metadata={
                "error_type": type(
                    exc
                ).__name__,
                "error": str(exc),
            },
        )

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except RuntimeError as exc:
        _audit_failure(
            action="model_generate",
            message="Local model generation failed during execution.",
            request_id=request_id,
            model=selected_model
            if "selected_model" in locals()
            else request.model,
            task_type=task_type,
            duration_ms=_duration_ms(
                started_at
            ),
            metadata={
                "error_type": type(
                    exc
                ).__name__,
                "error": str(exc),
            },
        )

        raise HTTPException(
            status_code=503,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        _audit_failure(
            action="model_generate",
            message="Local model generation failed unexpectedly.",
            request_id=request_id,
            model=selected_model
            if "selected_model" in locals()
            else request.model,
            task_type=task_type,
            duration_ms=_duration_ms(
                started_at
            ),
            metadata={
                "error_type": type(
                    exc
                ).__name__,
                "error": str(exc),
            },
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Local model generation failed: "
                f"{exc}"
            ),
        ) from exc


# ---------------------------------------------------------------------------
# INDIVIDUAL MODEL DETAILS
# ---------------------------------------------------------------------------

@router.get("/{model_name}")
def get_model_details(
    model_name: str,
) -> Dict[str, Any]:
    """
    Return verified detailed metadata for an installed local model.

    This route is intentionally declared after all fixed routes so
    paths such as /active, /routing and /activity remain unambiguous.
    """

    clean_name = (
        model_name.strip()
    )

    if not clean_name:
        raise HTTPException(
            status_code=400,
            detail=(
                "Model name cannot be empty."
            ),
        )

    if not ollama_manager.is_available():
        raise HTTPException(
            status_code=503,
            detail=(
                "Local Ollama runtime is offline."
            ),
        )

    if not ollama_manager.model_exists(
        clean_name
    ):
        raise HTTPException(
            status_code=404,
            detail=(
                f"Local model '{clean_name}' "
                "is not installed."
            ),
        )

    try:
        details = (
            ollama_manager.get_model_details(
                clean_name
            )
        )

        profile = (
            MODEL_REGISTRY.get(
                clean_name
            )
        )

        return {
            "name": clean_name,
            "installed": True,
            "provider": "ollama",
            "profile": (
                {
                    "capabilities": profile.capabilities,
                    "description": profile.description,
                    "vision": profile.vision,
                    "code": profile.code,
                    "reasoning": profile.reasoning,
                }
                if profile
                else None
            ),
            "details": details,
        }

    except RuntimeError as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=(
                f"Unable to load model details: {exc}"
            ),
        ) from exc