from contextvars import ContextVar
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from app.core.ai_config import (
    DEFAULT_MODEL,
    DEFAULT_TASK_ROUTING,
    get_active_model_name,
    load_runtime_state,
    update_runtime_state,
)
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
    Result of NOVA's deterministic local model-selection process.
    """

    model_name: str
    task_type: TaskType
    matched_tasks: List[TaskType]
    score: float
    reason: str


# ---------------------------------------------------------------------------
# REQUEST-SCOPED ROUTING CONTEXT
# ---------------------------------------------------------------------------

_LAST_ROUTING_DECISION: ContextVar[
    Optional[RoutingDecision]
] = ContextVar(
    "nova_last_routing_decision",
    default=None,
)


def get_last_routing_decision() -> Optional[RoutingDecision]:
    """
    Return the most recent routing decision for the current
    execution context.

    ContextVar keeps this request-local and avoids leaking one
    user's routing decision into another concurrent request.
    """

    return _LAST_ROUTING_DECISION.get()


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
    TaskType.MISSION: "mission",
}


# ---------------------------------------------------------------------------
# ROUTING CONFIGURATION
# ---------------------------------------------------------------------------

def get_task_routing() -> Dict[str, str]:
    """
    Return the persisted NOVA task-routing configuration.
    """

    state = load_runtime_state()

    routing = dict(
        DEFAULT_TASK_ROUTING
    )

    stored = state.get(
        "task_routing"
    )

    if isinstance(
        stored,
        dict,
    ):
        for (
            task_key,
            model_name,
        ) in stored.items():

            if (
                task_key in DEFAULT_TASK_ROUTING
                and isinstance(
                    model_name,
                    str,
                )
                and model_name.strip()
            ):
                routing[
                    task_key
                ] = model_name.strip()

    return routing


def set_task_routing(
    new_routing: Dict[str, str],
) -> Dict[str, str]:
    """
    Persist valid task-routing entries.
    """

    current = get_task_routing()

    for (
        task_key,
        model_name,
    ) in new_routing.items():

        if (
            task_key in DEFAULT_TASK_ROUTING
            and isinstance(
                model_name,
                str,
            )
            and model_name.strip()
        ):
            current[
                task_key
            ] = model_name.strip()

    def mutate(
        state: Dict,
    ) -> None:
        state[
            "task_routing"
        ] = dict(current)

    update_runtime_state(
        mutate
    )

    return dict(current)


# ---------------------------------------------------------------------------
# ROUTING HELPERS
# ---------------------------------------------------------------------------

def _resolve_config_key(
    text: str,
    primary_task: TaskType,
) -> Optional[str]:
    """
    Resolve the NOVA task-routing key.
    """

    normalized = (
        " ".join(
            (text or "")
            .lower()
            .strip()
            .split()
        )
    )

    mission_markers = (
        "mission",
        "mission control",
        "mission execution",
        "run this mission",
        "execute this mission",
        "start mission",
        "autonomous mission",
        "autonomous multi-step",
    )

    knowledge_markers = (
        "knowledge vault",
        "knowledge base",
        "knowledge retrieval",
        "rag",
        "search my vault",
        "search the vault",
        "local knowledge",
        "retrieve from vault",
    )

    if any(
        marker in normalized
        for marker in mission_markers
    ):
        return "mission"

    if any(
        marker in normalized
        for marker in knowledge_markers
    ):
        return "knowledge"

    if primary_task == TaskType.MISSION:
        return "mission"

    if primary_task == TaskType.CODING:
        return "coding"

    if primary_task in (
        TaskType.REASONING,
        TaskType.DATA_ANALYSIS,
    ):
        return "reasoning"

    if primary_task in (
        TaskType.DOCUMENT,
        TaskType.SUMMARIZATION,
        TaskType.SPREADSHEET,
    ):
        return "document"

    if primary_task in (
        TaskType.GENERAL,
        TaskType.CONVERSATION,
        TaskType.CREATIVE,
    ):
        return "general"

    return None


def _verified_installed_models():
    """
    Return actual locally installed model information.
    """

    from app.services.model_engine.ollama_manager import (
        ollama_manager,
    )

    return ollama_manager.list_models()


# ---------------------------------------------------------------------------
# MODEL ROUTER
# ---------------------------------------------------------------------------

class ModelRouter:
    """
    Deterministic local model-selection engine.

    Routing priority:

    1. Explicit task-routing configuration
    2. Verified local availability
    3. Active local model
    4. First verified locally installed model
    5. Capability scoring
    """

    def __init__(
        self,
        fallback_model: str = DEFAULT_MODEL,
    ) -> None:
        self.fallback_model = (
            fallback_model.strip()
            or DEFAULT_MODEL
        )

    def _fallback_installed_name(
        self,
        installed_models: List[Dict],
    ) -> Optional[str]:

        installed_names = [
            str(
                item.get(
                    "name",
                    "",
                )
            ).strip()
            for item in installed_models
            if str(
                item.get(
                    "name",
                    "",
                )
            ).strip()
        ]

        active_model = (
            get_active_model_name()
        )

        if (
            active_model
            and active_model in installed_names
        ):
            return active_model

        if (
            self.fallback_model
            and self.fallback_model
            in installed_names
        ):
            return self.fallback_model

        return (
            installed_names[0]
            if installed_names
            else None
        )

    def _score_model(
        self,
        model: ModelProfile,
        tasks: List[TaskType],
    ) -> Tuple[
        float,
        List[str],
    ]:

        score = 0.0
        matched_capabilities: List[str] = []

        for task in tasks:
            capability = (
                TASK_CAPABILITY_MAP.get(
                    task
                )
            )

            if not capability:
                continue

            if (
                capability
                in model.capabilities
            ):
                score += 10.0
                matched_capabilities.append(
                    capability
                )

        if (
            not matched_capabilities
            and model.general
        ):
            score += 1.0

        priority_bonus = max(
            0.0,
            5.0 - (
                model.priority / 20.0
            ),
        )

        score += priority_bonus

        return (
            score,
            matched_capabilities,
        )

    def route(
        self,
        text: str,
        task_key: Optional[str] = None,
    ) -> RoutingDecision:

        normalized_text = (
            str(
                text or ""
            ).strip()
        )

        primary_task = classify_task(
            normalized_text
        )

        matched_tasks = classify_tasks(
            normalized_text
        )

        installed_models = (
            _verified_installed_models()
        )

        if not installed_models:
            raise RuntimeError(
                "No locally installed Ollama models are available."
            )

        installed_names = {
            str(
                item.get(
                    "name",
                    "",
                )
            ).strip()
            for item in installed_models
            if str(
                item.get(
                    "name",
                    "",
                )
            ).strip()
        }

        configured_task_key = (
            task_key.strip().lower()
            if isinstance(
                task_key,
                str,
            )
            and task_key.strip()
            else _resolve_config_key(
                normalized_text,
                primary_task,
            )
        )

        routing = get_task_routing()

        if (
            configured_task_key
            and configured_task_key
            in routing
        ):

            configured_model = (
                routing[
                    configured_task_key
                ]
            )

            if (
                configured_model
                in installed_names
            ):
                return RoutingDecision(
                    model_name=(
                        configured_model
                    ),
                    task_type=primary_task,
                    matched_tasks=matched_tasks,
                    score=100.0,
                    reason=(
                        "Routed using the persisted NOVA "
                        "task configuration: "
                        f"{configured_task_key} -> "
                        f"{configured_model}."
                    ),
                )

            fallback_name = (
                self._fallback_installed_name(
                    installed_models
                )
            )

            if not fallback_name:
                raise RuntimeError(
                    f"Configured model '{configured_model}' "
                    "is unavailable and no local fallback exists."
                )

            return RoutingDecision(
                model_name=fallback_name,
                task_type=primary_task,
                matched_tasks=matched_tasks,
                score=10.0,
                reason=(
                    f"Configured model '{configured_model}' "
                    f"for task '{configured_task_key}' is not "
                    "currently installed. "
                    f"Verified fallback: '{fallback_name}'."
                ),
            )

        enabled_models = (
            get_enabled_models()
        )

        installed_profiles = [
            model
            for model in enabled_models
            if model.name in installed_names
        ]

        if not installed_profiles:
            fallback_name = (
                self._fallback_installed_name(
                    installed_models
                )
            )

            if not fallback_name:
                raise RuntimeError(
                    "No enabled local NOVA model is available."
                )

            return RoutingDecision(
                model_name=fallback_name,
                task_type=primary_task,
                matched_tasks=matched_tasks,
                score=1.0,
                reason=(
                    "No specialized routing profile matched. "
                    f"Using verified local model '{fallback_name}'."
                ),
            )

        scored_models = []

        for model in installed_profiles:
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

        best_score, best_model, capabilities = (
            scored_models[0]
        )

        if best_score <= 1.0:
            fallback_name = (
                self._fallback_installed_name(
                    installed_models
                )
            )

            if fallback_name:
                return RoutingDecision(
                    model_name=fallback_name,
                    task_type=primary_task,
                    matched_tasks=matched_tasks,
                    score=best_score,
                    reason=(
                        "No specialized capability matched "
                        "the request. "
                        f"Using verified fallback '{fallback_name}'."
                    ),
                )

        if capabilities:
            reason = (
                f"Selected '{best_model.name}' "
                "for capabilities: "
                f"{', '.join(capabilities)}."
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
    task_key: Optional[str] = None,
) -> RoutingDecision:
    """
    Route a request and retain the decision in request-local context.

    The request-local context is used by callers that invoke
    ollama_manager.generate() immediately after route_request()
    without explicitly passing task_type.
    """

    decision = model_router.route(
        text,
        task_key=task_key,
    )

    _LAST_ROUTING_DECISION.set(
        decision
    )

    return decision