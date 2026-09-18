from __future__ import annotations

import asyncio
from typing import Any, Dict, Optional, Union

from app.core.ai_config import (
    NOVA_SYSTEM_PROMPT,
    get_active_model_name,
)
from app.services.model_engine.model_router import (
    route_request,
)
from app.services.model_engine.ollama_manager import (
    ollama_manager,
)


async def generate_response(
    prompt: str,
    model: Optional[str] = None,
    task_type: Optional[str] = None,
    system: Optional[str] = None,
    temperature: float = 0.4,
    num_predict: int = 256,
    return_metadata: bool = False,
) -> Union[
    str,
    Dict[str, Any],
]:
    """
    Execute Local Chat through NOVA's central model engine.

    Behaviour:

    - explicit model -> use that verified model directly
    - no model -> use NOVA task routing
    - task_type -> can explicitly select a routing category
    """

    clean_prompt = str(
        prompt or ""
    ).strip()

    if not clean_prompt:
        raise ValueError(
            "NOVA prompt cannot be empty."
        )

    selected_model = (
        str(
            model or ""
        ).strip()
    )

    routing = None

    if selected_model:
        if not ollama_manager.model_exists(
            selected_model
        ):
            raise ValueError(
                f"Local Ollama model '{selected_model}' "
                "is not installed."
            )

        resolved_task = (
            str(
                task_type
                or "direct_chat"
            ).strip()
            or "direct_chat"
        )

    else:
        routing = route_request(
            clean_prompt,
            task_key=task_type,
        )

        selected_model = (
            routing.model_name
        )

        resolved_task = (
            routing.task_type.value
        )

    result = await asyncio.to_thread(
        ollama_manager.generate,
        model=selected_model,
        prompt=clean_prompt,
        system=(
            system
            if system is not None
            else NOVA_SYSTEM_PROMPT
        ),
        temperature=temperature,
        num_predict=num_predict,
        stream=False,
        task_type=resolved_task,
    )

    response_text = str(
        result.get(
            "response",
            "",
        )
        or ""
    ).strip()

    if not response_text:
        raise RuntimeError(
            "NOVA returned an empty response."
        )

    payload = {
        "response": response_text,
        "model_used": result.get(
            "model_used",
            selected_model,
        ),
        "latency_ms": result.get(
            "latency_ms"
        ),
        "done": result.get(
            "done",
            True,
        ),
        "task_type": resolved_task,
        "routing": (
            {
                "model": routing.model_name,
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

    if return_metadata:
        return payload

    return response_text