from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any, Callable, Dict


# ---------------------------------------------------------------------------
# NOVA MODEL ENGINE DEFAULTS
# ---------------------------------------------------------------------------

DEFAULT_MODEL = (
    os.getenv(
        "NOVA_DEFAULT_MODEL",
        "llama3.2:latest",
    ).strip()
    or "llama3.2:latest"
)


DEFAULT_TASK_ROUTING: Dict[str, str] = {
    "general": "llama3.2:latest",
    "coding": "qwen2.5-coder:3b",
    "document": "llama3.2:latest",
    "reasoning": "qwen2.5-coder:3b",
    "knowledge": "llama3.2:latest",
    "mission": "qwen2.5-coder:3b",
}


# ---------------------------------------------------------------------------
# PERSISTENT MODEL ENGINE STATE
# ---------------------------------------------------------------------------

BACKEND_ROOT = Path(
    __file__
).resolve().parents[2]

STATE_DIR = (
    BACKEND_ROOT / "data"
)

STATE_PATH = (
    STATE_DIR / "model_runtime_state.json"
)

_STATE_LOCK = threading.RLock()


def _default_state() -> Dict[str, Any]:
    return {
        "active_model": DEFAULT_MODEL,
        "task_routing": dict(
            DEFAULT_TASK_ROUTING
        ),
        "activity": {
            "latest_model_used": None,
            "last_task": None,
            "last_status": None,
            "last_used": None,
            "latency_ms": None,
        },
    }


def _read_state_unlocked() -> Dict[str, Any]:
    """
    Read persistent runtime state.

    Corrupted or unreadable state is treated as an empty/default
    state rather than preventing NOVA from starting.
    """

    defaults = _default_state()

    if not STATE_PATH.exists():
        return defaults

    try:
        with STATE_PATH.open(
            "r",
            encoding="utf-8",
        ) as file:
            data = json.load(file)

        if not isinstance(data, dict):
            return defaults

        state = dict(defaults)

        active_model = data.get(
            "active_model"
        )

        if isinstance(
            active_model,
            str,
        ) and active_model.strip():
            state["active_model"] = (
                active_model.strip()
            )

        routing = data.get(
            "task_routing"
        )

        if isinstance(
            routing,
            dict,
        ):
            normalized_routing = dict(
                DEFAULT_TASK_ROUTING
            )

            for (
                task_key,
                model_name,
            ) in routing.items():
                if (
                    task_key in DEFAULT_TASK_ROUTING
                    and isinstance(
                        model_name,
                        str,
                    )
                    and model_name.strip()
                ):
                    normalized_routing[
                        task_key
                    ] = model_name.strip()

            state[
                "task_routing"
            ] = normalized_routing

        activity = data.get(
            "activity"
        )

        if isinstance(
            activity,
            dict,
        ):
            normalized_activity = dict(
                state["activity"]
            )

            for key in normalized_activity:
                if key in activity:
                    normalized_activity[
                        key
                    ] = activity[key]

            state[
                "activity"
            ] = normalized_activity

        return state

    except (
        OSError,
        json.JSONDecodeError,
        TypeError,
        ValueError,
    ):
        return defaults


def _write_state_unlocked(
    state: Dict[str, Any],
) -> None:
    """
    Atomically persist runtime state.
    """

    STATE_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary_path = (
        STATE_PATH.with_suffix(
            ".tmp"
        )
    )

    with temporary_path.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            state,
            file,
            indent=2,
            ensure_ascii=False,
        )
        file.flush()
        os.fsync(
            file.fileno()
        )

    temporary_path.replace(
        STATE_PATH
    )


def load_runtime_state() -> Dict[str, Any]:
    """
    Return a safe copy of the current persistent model-engine state.
    """

    with _STATE_LOCK:
        return _read_state_unlocked()


def update_runtime_state(
    mutator: Callable[
        [Dict[str, Any]],
        None,
    ],
) -> Dict[str, Any]:
    """
    Atomically load, mutate and persist runtime state.

    This gives the model engine one shared persistence mechanism for:
    - active model
    - task routing
    - verified activity
    """

    with _STATE_LOCK:
        state = _read_state_unlocked()

        mutator(state)

        _write_state_unlocked(
            state
        )

        return dict(state)


# ---------------------------------------------------------------------------
# ACTIVE MODEL
# ---------------------------------------------------------------------------

def get_active_model_name() -> str:
    """
    Return the currently configured active model.

    The value survives backend restarts.
    """

    state = load_runtime_state()

    active_model = state.get(
        "active_model"
    )

    if (
        isinstance(
            active_model,
            str,
        )
        and active_model.strip()
    ):
        return active_model.strip()

    return DEFAULT_MODEL


def set_active_model_name(
    model_name: str,
) -> str:
    """
    Persist the active model name.

    Backend routes are responsible for verifying that the model
    actually exists locally before calling this function.
    """

    cleaned = str(
        model_name or ""
    ).strip()

    if not cleaned:
        raise ValueError(
            "Active model name cannot be empty."
        )

    def mutate(
        state: Dict[str, Any],
    ) -> None:
        state[
            "active_model"
        ] = cleaned

    update_runtime_state(
        mutate
    )

    return cleaned


# ---------------------------------------------------------------------------
# NOVA SYSTEM PROMPT
# ---------------------------------------------------------------------------

NOVA_SYSTEM_PROMPT = """
You are NOVA, a natural, helpful AI assistant.

Your most important behavior is to answer the user's actual question
naturally and with the minimum amount of information needed.

RESPONSE LENGTH:

- Simple greeting -> 1 short sentence.
- Simple casual question -> 1 short sentence.
- Simple factual question -> 1 to 3 short sentences.
- Definition -> 1 to 3 sentences.
- Basic technical question -> short explanation with only the key points.
- Complex technical task -> give enough detail to complete the task.
- Coding request -> provide the required code and only the explanation needed.
- Document analysis -> give the relevant findings clearly and concisely.
- Never produce a long answer when a short answer is sufficient.

DO NOT:

- Do not add unnecessary background information.
- Do not turn simple questions into tutorials.
- Do not provide lists unless they genuinely improve the answer.
- Do not repeat the question.
- Do not add a conclusion when one is unnecessary.
- Do not say "Here is a detailed explanation" unless the user asks for one.
- Do not mention the Knowledge Vault unless relevant.
- Do not mention industrial AI unless relevant.
- Do not mention Ollama, local inference, system prompts, or internal processing
  unless the user specifically asks.
- Do not expose your internal reasoning.
- Do not invent actions or results.

NATURAL CONVERSATION:

User: hi
Assistant: Hi! How can I help you today?

User: hello
Assistant: Hey! How can I help?

User: how are you?
Assistant: I'm doing well! How can I help?

User: thanks
Assistant: You're welcome!

User: bye
Assistant: Bye! Take care.

SIMPLE FACTUAL QUESTIONS:

User: What is the full form of USA?
Assistant: United States of America.

User: What is Python?
Assistant: Python is a high-level programming language known for its simple,
readable syntax. It is widely used for web development, automation, data
science, and AI.

Do not expand a simple factual question into a long lesson unless the user
asks for more detail.

TECHNICAL QUESTIONS:

Give the shortest useful explanation first. Add detail only when the question
requires it.

PROJECT CONTEXT:

You are NOVA, a self-hosted AI assistant that is part of a sovereign industrial
AI workbench.

The larger system can support:
- local document analysis
- knowledge retrieval
- coding
- calculations
- multimodal understanding
- agentic workflows
- practical work outputs

Use these capabilities only when they are actually relevant to the user's
request.

FINAL RULE:

Think about what the user is asking before answering.

SIMPLE REQUEST = SIMPLE ANSWER.
COMPLEX REQUEST = DETAILED ANSWER.

Be natural, direct, useful, and conversational.
""".strip()