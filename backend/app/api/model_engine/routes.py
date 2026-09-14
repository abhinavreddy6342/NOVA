from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.models.model_registry import (
    get_enabled_models,
)
from app.services.model_engine.model_router import (
    route_request,
)
from app.services.model_engine.ollama_manager import (
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
        description="Prompt to send to the selected local model.",
    )

    model: Optional[str] = Field(
        default=None,
        description="Optional explicit local model name.",
    )

    system: Optional[str] = Field(
        default=None,
        description="Optional system prompt.",
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


# ---------------------------------------------------------------------------
# MODEL LIST
# ---------------------------------------------------------------------------

@router.get("")
def list_models() -> Dict[str, Any]:
    """
    Return NOVA's registered and locally available models.
    """

    registered = get_enabled_models()

    local_models = ollama_manager.list_models()

    local_names = {
        model.get("name")
        for model in local_models
    }

    models: List[Dict[str, Any]] = []

    for profile in registered:
        models.append(
            {
                "name": profile.name,
                "provider": profile.provider,
                "capabilities": profile.capabilities,
                "context_window": profile.context_window,
                "vision": profile.vision,
                "code": profile.code,
                "reasoning": profile.reasoning,
                "enabled": profile.enabled,
                "installed": profile.name in local_names,
                "description": profile.description,
            }
        )

    return {
        "count": len(models),
        "models": models,
    }


# ---------------------------------------------------------------------------
# MODEL STATUS
# ---------------------------------------------------------------------------

@router.get("/status")
def model_status() -> Dict[str, Any]:
    """
    Return the health of the local Ollama model engine.
    """

    ollama_online = (
        ollama_manager.is_available()
    )

    local_models = (
        ollama_manager.list_models()
        if ollama_online
        else []
    )

    return {
        "status": (
            "online"
            if ollama_online
            else "offline"
        ),
        "provider": "ollama",
        "endpoint": ollama_manager.base_url,
        "local_model_count": len(
            local_models
        ),
        "local_models": [
            model.get("name")
            for model in local_models
        ],
    }


# ---------------------------------------------------------------------------
# ROUTE REQUEST
# ---------------------------------------------------------------------------

@router.post("/route")
def route_model(
    request: RouteRequest,
) -> Dict[str, Any]:
    """
    Classify a request and determine the best local model.
    """

    try:
        decision = route_request(
            request.text
        )

        return {
    "model": decision.model_name,
    "task_type": decision.task_type.value,
    "matched_tasks": [
        task.value
        for task in decision.matched_tasks
    ],
    "score": decision.score,
    "reason": decision.reason,
}

    except RuntimeError as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        ) from exc


# ---------------------------------------------------------------------------
# GENERATE
# ---------------------------------------------------------------------------

@router.post("/generate")
def generate_model_response(
    request: GenerateRequest,
) -> Dict[str, Any]:
    """
    Generate a response using a selected local model.

    When no model is supplied, NOVA's router
    selects one automatically.
    """

    try:
        if request.model:
            selected_model = (
                request.model.strip()
            )

            if not ollama_manager.model_exists(
                selected_model
            ):
                raise HTTPException(
                    status_code=404,
                    detail=(
                        f"Local model "
                        f"'{selected_model}' "
                        "is not installed."
                    ),
                )

            routing = None

        else:
            routing = route_request(
                request.prompt
            )

            selected_model = (
                routing.model_name
            )

        result = ollama_manager.generate(
            model=selected_model,
            prompt=request.prompt,
            system=request.system,
            temperature=request.temperature,
            num_predict=request.num_predict,
            stream=False,
        )

        response_text = (
            result.get("response", "")
            .strip()
        )

        return {
            "model": selected_model,
            "response": response_text,
            "done": result.get(
                "done",
                True,
            ),
            "routing": (
                {
                    "task_type": (
                        routing.task_type.value
                    ),
                    "matched_tasks": [
                        task.value
                        for task in routing.matched_tasks
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
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except RuntimeError as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        ) from exc