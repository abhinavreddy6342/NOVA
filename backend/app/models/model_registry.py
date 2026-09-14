from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class ModelProfile:
    """
    Describes a locally available NOVA model.
    """

    name: str
    provider: str = "ollama"
    capabilities: List[str] = field(default_factory=list)

    context_window: int = 4096
    vision: bool = False
    code: bool = False
    reasoning: bool = False
    general: bool = True

    priority: int = 100
    enabled: bool = True

    description: str = ""


# ---------------------------------------------------------------------------
# NOVA LOCAL MODEL REGISTRY
# ---------------------------------------------------------------------------

MODEL_REGISTRY: Dict[str, ModelProfile] = {
    "llama3.2:latest": ModelProfile(
        name="llama3.2:latest",
        provider="ollama",
        capabilities=[
            "general",
            "conversation",
            "summarization",
            "basic_reasoning",
        ],
        context_window=4096,
        vision=False,
        code=False,
        reasoning=False,
        general=True,
        priority=100,
        enabled=True,
        description=(
            "Primary local general-purpose NOVA model."
        ),
    ),

    "qwen2.5-coder:3b": ModelProfile(
        name="qwen2.5-coder:3b",
        provider="ollama",
        capabilities=[
            "code",
            "coding",
            "programming",
            "debugging",
            "software_development",
            "reasoning",
        ],
        context_window=32768,
        vision=False,
        code=True,
        reasoning=True,
        general=False,
        priority=10,
        enabled=True,
        description=(
            "Local coding-focused open-weight model "
            "for software development and technical tasks."
        ),
    ),
}


# ---------------------------------------------------------------------------
# REGISTRY HELPERS
# ---------------------------------------------------------------------------

def get_model(
    model_name: str,
) -> Optional[ModelProfile]:
    """
    Return a registered model profile.
    """

    return MODEL_REGISTRY.get(model_name)


def get_enabled_models() -> List[ModelProfile]:
    """
    Return all enabled models ordered by priority.
    """

    return sorted(
        [
            model
            for model in MODEL_REGISTRY.values()
            if model.enabled
        ],
        key=lambda model: model.priority,
    )


def get_models_by_capability(
    capability: str,
) -> List[ModelProfile]:
    """
    Find enabled models supporting a capability.
    """

    capability = capability.lower().strip()

    return sorted(
        [
            model
            for model in MODEL_REGISTRY.values()
            if model.enabled
            and capability in model.capabilities
        ],
        key=lambda model: model.priority,
    )


def register_model(
    profile: ModelProfile,
) -> None:
    """
    Add or replace a model in the local registry.
    """

    MODEL_REGISTRY[profile.name] = profile


def remove_model(
    model_name: str,
) -> bool:
    """
    Remove a model from the registry.

    Returns True when removed, otherwise False.
    """

    if model_name not in MODEL_REGISTRY:
        return False

    del MODEL_REGISTRY[model_name]

    return True


def list_model_names() -> List[str]:
    """
    Return the names of all registered models.
    """

    return list(MODEL_REGISTRY.keys())