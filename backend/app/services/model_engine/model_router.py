from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from app.models.model_registry import (
    ModelProfile,
    get_enabled_models,
)
from app.services.model_engine.task_classifier import (
    TaskType,
    classify_task,
    classify_tasks,
)


@dataclass
class RoutingDecision:
    """
    Result of NOVA's model-selection process.
    """

    model_name: str
    task_type: TaskType
    matched_tasks: List[TaskType]
    score: float
    reason: str


# ---------------------------------------------------------------------------
# TASK → MODEL CAPABILITY MAPPING
# ---------------------------------------------------------------------------

TASK_CAPABILITY_MAP = {
    TaskType.GENERAL: "general",
    TaskType.CONVERSATION: "conversation",
    TaskType.CODING: "coding",
    TaskType.REASONING: "reasoning",
    TaskType.DOCUMENT: "document",
    TaskType.SUMMARIZATION: "summarization",
    TaskType.DATA_ANALYSIS: "data_analysis",
    TaskType.SPREADSHEET: "spreadsheet",
    TaskType.VISION: "vision",
    TaskType.CREATIVE: "creative",
}


# ---------------------------------------------------------------------------
# MODEL ROUTER
# ---------------------------------------------------------------------------

class ModelRouter:
    """
    Deterministic local model-selection engine for NOVA.

    The router evaluates every enabled model against
    every detected task and selects the highest-scoring
    compatible model.

    No external AI service is used.
    """

    def __init__(
        self,
        fallback_model: str = "llama3.2:latest",
    ) -> None:
        self.fallback_model = fallback_model

    def _fallback_profile(
        self,
    ) -> Optional[ModelProfile]:
        """
        Return the configured fallback model.
        """

        for model in get_enabled_models():
            if model.name == self.fallback_model:
                return model

        return None

    def _score_model(
        self,
        model: ModelProfile,
        tasks: List[TaskType],
    ) -> Tuple[float, List[str]]:
        """
        Calculate a compatibility score for a model.

        Higher score = better capability match.
        """

        score = 0.0
        matched_capabilities: List[str] = []

        for task in tasks:
            capability = TASK_CAPABILITY_MAP.get(
                task
            )

            if not capability:
                continue

            if capability in model.capabilities:
                score += 10.0
                matched_capabilities.append(
                    capability
                )

        # General models receive a small fallback bonus.
        if (
            not matched_capabilities
            and model.general
        ):
            score += 1.0

        # Lower priority number = higher routing priority.
        priority_bonus = max(
            0.0,
            5.0 - (model.priority / 20.0),
        )

        score += priority_bonus

        return score, matched_capabilities

    def route(
        self,
        text: str,
    ) -> RoutingDecision:
        """
        Select the best enabled local model.
        """

        primary_task = classify_task(text)

        matched_tasks = classify_tasks(text)

        enabled_models = get_enabled_models()

        if not enabled_models:
            raise RuntimeError(
                "NOVA has no enabled local models."
            )

        scored_models = []

        for model in enabled_models:
            score, capabilities = (
                self._score_model(
                    model,
                    matched_tasks,
                )
            )

            scored_models.append(
                (
                    score,
                    model,
                    capabilities,
                )
            )

        scored_models.sort(
            key=lambda item: (
                item[0],
                -item[1].priority,
            ),
            reverse=True,
        )

        best_score, best_model, matched_capabilities = (
            scored_models[0]
        )

        # If nothing meaningful matched, use fallback.
        if best_score <= 1.0:
            fallback = self._fallback_profile()

            if fallback:
                return RoutingDecision(
                    model_name=fallback.name,
                    task_type=primary_task,
                    matched_tasks=matched_tasks,
                    score=best_score,
                    reason=(
                        "No specialized capability matched "
                        f"the request. Using fallback model "
                        f"'{fallback.name}'."
                    ),
                )

        if matched_capabilities:
            reason = (
                f"Selected '{best_model.name}' "
                f"for capabilities: "
                f"{', '.join(matched_capabilities)}."
            )
        else:
            reason = (
                f"Selected '{best_model.name}' "
                "as the best available local model."
            )

        return RoutingDecision(
            model_name=best_model.name,
            task_type=primary_task,
            matched_tasks=matched_tasks,
            score=best_score,
            reason=reason,
        )


# ---------------------------------------------------------------------------
# SHARED ROUTER
# ---------------------------------------------------------------------------

model_router = ModelRouter()


def route_request(
    text: str,
) -> RoutingDecision:
    """
    Convenience function for routing a NOVA request.
    """

    return model_router.route(text)