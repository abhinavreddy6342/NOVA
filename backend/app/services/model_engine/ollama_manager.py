from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx

from app.core.ai_config import (
    update_runtime_state,
)


# ---------------------------------------------------------------------------
# OLLAMA CONFIGURATION
# ---------------------------------------------------------------------------

OLLAMA_BASE_URL = (
    os.getenv(
        "OLLAMA_BASE_URL",
        "http://127.0.0.1:11434",
    ).strip()
    or "http://127.0.0.1:11434"
).rstrip("/")


def format_size(
    size_in_bytes: Optional[int],
) -> str:

    if (
        not size_in_bytes
        or size_in_bytes <= 0
    ):
        return "NOT AVAILABLE"

    gb = (
        size_in_bytes
        / (1024 ** 3)
    )

    if gb >= 1.0:
        return f"{gb:.2f} GB"

    mb = (
        size_in_bytes
        / (1024 ** 2)
    )

    return f"{mb:.1f} MB"


def _normalize_context_length(
    value: Any,
) -> Optional[int]:

    if isinstance(
        value,
        bool,
    ):
        return None

    if isinstance(
        value,
        int,
    ) and value > 0:
        return value

    if isinstance(
        value,
        float,
    ) and value > 0:
        return int(value)

    if isinstance(
        value,
        str,
    ):
        digits = "".join(
            character
            for character in value
            if character.isdigit()
        )

        if digits:
            parsed = int(
                digits
            )

            if parsed > 0:
                return parsed

    return None


def _extract_context_length(
    details: Dict[str, Any],
    model_info: Dict[str, Any],
) -> Optional[int]:

    direct = (
        _normalize_context_length(
            details.get(
                "context_length"
            )
        )
        or _normalize_context_length(
            model_info.get(
                "context_length"
            )
        )
    )

    if direct:
        return direct

    for key, value in (
        model_info.items()
    ):
        normalized_key = (
            str(key).lower()
        )

        if (
            normalized_key.endswith(
                ".context_length"
            )
            or normalized_key.endswith(
                ".context-length"
            )
            or normalized_key
            == "context_length"
        ):
            parsed = (
                _normalize_context_length(
                    value
                )
            )

            if parsed:
                return parsed

    return None


def _format_context_length(
    value: Any,
) -> str:

    parsed = (
        _normalize_context_length(
            value
        )
    )

    if not parsed:
        return "NOT AVAILABLE"

    return f"{parsed:,} tokens"


# ---------------------------------------------------------------------------
# VERIFIED ACTIVITY
# ---------------------------------------------------------------------------

def record_verified_activity(
    model_id: str,
    task_type: str,
    status: str,
    latency_ms: Optional[float] = None,
) -> None:

    activity = {
        "latest_model_used": str(
            model_id or ""
        ).strip()
        or "unknown",
        "last_task": str(
            task_type or ""
        ).strip()
        or "general",
        "last_status": str(
            status or ""
        ).strip()
        or "FAILED",
        "last_used": datetime.now(
            timezone.utc
        ).isoformat(),
        "latency_ms": latency_ms,
    }

    def mutate(
        state: Dict[str, Any],
    ) -> None:
        state[
            "activity"
        ] = activity

    update_runtime_state(
        mutate
    )


def get_verified_activity() -> Dict[str, Any]:

    from app.core.ai_config import (
        load_runtime_state,
    )

    state = load_runtime_state()

    activity = state.get(
        "activity",
        {},
    )

    if not isinstance(
        activity,
        dict,
    ):
        return {
            "latest_model_used": None,
            "last_task": None,
            "last_status": None,
            "last_used": None,
            "latency_ms": None,
        }

    return dict(
        activity
    )


# ---------------------------------------------------------------------------
# OLLAMA MANAGER
# ---------------------------------------------------------------------------

class OllamaManager:

    def __init__(
        self,
        base_url: str = OLLAMA_BASE_URL,
        timeout: float = 120.0,
    ) -> None:

        self.base_url = (
            base_url.rstrip("/")
        )

        self.timeout = timeout


    def _client(
        self,
    ) -> httpx.Client:

        return httpx.Client(
            base_url=self.base_url,
            timeout=self.timeout,
        )


    # -----------------------------------------------------------------------
    # HEALTH
    # -----------------------------------------------------------------------

    def is_available(self) -> bool:

        try:
            with self._client() as client:
                response = client.get(
                    "/api/tags"
                )

            return response.is_success

        except (
            httpx.ConnectError,
            httpx.TimeoutException,
            httpx.RequestError,
        ):
            return False


    # -----------------------------------------------------------------------
    # MODEL DETAILS
    # -----------------------------------------------------------------------

    def get_model_details(
        self,
        model_name: str,
    ) -> Dict[str, Any]:

        clean_name = str(
            model_name or ""
        ).strip()

        if not clean_name:
            raise ValueError(
                "Model name cannot be empty."
            )

        try:
            with self._client() as client:
                response = client.post(
                    "/api/show",
                    json={
                        "name": clean_name
                    },
                )

                response.raise_for_status()

            data = response.json()

            if not isinstance(
                data,
                dict,
            ):
                return {}

            return data

        except (
            httpx.ConnectError,
            httpx.TimeoutException,
            httpx.RequestError,
        ) as exc:
            raise RuntimeError(
                "Could not connect to local Ollama."
            ) from exc

        except httpx.HTTPStatusError as exc:
            raise RuntimeError(
                "Ollama model metadata request failed "
                f"with HTTP {exc.response.status_code}: "
                f"{exc.response.text}"
            ) from exc

        except (
            ValueError,
            TypeError,
        ):
            return {}


    # -----------------------------------------------------------------------
    # MODEL DISCOVERY
    # -----------------------------------------------------------------------

    def list_models(
        self,
        enrich: bool = False,
    ) -> List[Dict[str, Any]]:

        try:
            with self._client() as client:
                response = client.get(
                    "/api/tags"
                )

                response.raise_for_status()

            data = response.json()

            if not isinstance(
                data,
                dict,
            ):
                return []

            raw_models = data.get(
                "models",
                [],
            )

            if not isinstance(
                raw_models,
                list,
            ):
                return []

            processed: List[
                Dict[str, Any]
            ] = []

            for item in raw_models:

                if not isinstance(
                    item,
                    dict,
                ):
                    continue

                name = str(
                    item.get(
                        "name",
                        "",
                    )
                    or ""
                ).strip()

                if not name:
                    continue

                details = (
                    item.get(
                        "details",
                        {},
                    )
                )

                if not isinstance(
                    details,
                    dict,
                ):
                    details = {}

                size_bytes = item.get(
                    "size",
                    0,
                )

                try:
                    size_bytes = int(
                        size_bytes or 0
                    )

                except (
                    TypeError,
                    ValueError,
                ):
                    size_bytes = 0

                context_length = (
                    _normalize_context_length(
                        details.get(
                            "context_length"
                        )
                    )
                )

                model_info: Dict[
                    str,
                    Any,
                ] = {}

                if (
                    enrich
                    and not context_length
                ):
                    try:
                        show_data = (
                            self.get_model_details(
                                name
                            )
                        )

                        show_details = (
                            show_data.get(
                                "details",
                                {},
                            )
                        )

                        if isinstance(
                            show_details,
                            dict,
                        ):
                            merged_details = dict(
                                details
                            )

                            merged_details.update(
                                {
                                    key: value
                                    for key, value
                                    in show_details.items()
                                    if value is not None
                                }
                            )

                            details = (
                                merged_details
                            )

                        raw_model_info = (
                            show_data.get(
                                "model_info",
                                {},
                            )
                        )

                        if isinstance(
                            raw_model_info,
                            dict,
                        ):
                            model_info = (
                                raw_model_info
                            )

                        context_length = (
                            _extract_context_length(
                                details,
                                model_info,
                            )
                        )

                    except Exception:
                        model_info = {}

                processed.append(
                    {
                        "name": name,
                        "model": item.get(
                            "model",
                            name,
                        ),
                        "digest": item.get(
                            "digest",
                            "",
                        ),
                        "modified_at": item.get(
                            "modified_at",
                            "",
                        ),
                        "size_bytes": size_bytes,
                        "size_human": format_size(
                            size_bytes
                        ),
                        "format": details.get(
                            "format",
                            "NOT AVAILABLE",
                        ),
                        "family": details.get(
                            "family",
                            "NOT AVAILABLE",
                        ),
                        "families": details.get(
                            "families",
                            [],
                        ),
                        "parameter_size": details.get(
                            "parameter_size",
                            "NOT AVAILABLE",
                        ),
                        "quantization_level": details.get(
                            "quantization_level",
                            "NOT AVAILABLE",
                        ),
                        "context_length": (
                            _format_context_length(
                                context_length
                            )
                        ),
                        "details": details,
                        "model_info": model_info,
                    }
                )

            return processed

        except (
            httpx.ConnectError,
            httpx.TimeoutException,
            httpx.RequestError,
            httpx.HTTPStatusError,
            ValueError,
            TypeError,
        ):
            return []


    # -----------------------------------------------------------------------
    # MODEL EXISTENCE
    # -----------------------------------------------------------------------

    def model_exists(
        self,
        model_name: str,
    ) -> bool:

        clean_name = str(
            model_name or ""
        ).strip()

        if not clean_name:
            return False

        models = self.list_models()

        return any(
            str(
                model.get(
                    "name",
                    "",
                )
            ).strip()
            == clean_name
            for model in models
        )


    # -----------------------------------------------------------------------
    # LOCAL INFERENCE
    # -----------------------------------------------------------------------

    def generate(
        self,
        model: str,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.4,
        num_predict: int = 512,
        stream: bool = False,
        task_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Execute real local Ollama inference.

        When task_type is omitted, use the most recent routing decision
        from the current request context. This preserves task attribution
        for existing Agent/Planner/Synthesizer callers that already call
        route_request() before generate().
        """

        clean_model = str(
            model or ""
        ).strip()

        clean_prompt = str(
            prompt or ""
        ).strip()

        if task_type is None or not str(
            task_type
        ).strip():

            resolved_task = "general"

            try:
                from app.services.model_engine.model_router import (
                    get_last_routing_decision,
                )

                routing = (
                    get_last_routing_decision()
                )

                if routing is not None:
                    resolved_task = (
                        routing.task_type.value
                    )

            except Exception:
                resolved_task = "general"

        else:
            resolved_task = str(
                task_type
            ).strip()

        if not clean_model:
            record_verified_activity(
                "unknown",
                resolved_task,
                "FAILED",
            )

            raise ValueError(
                "Ollama model name cannot be empty."
            )

        if not clean_prompt:
            record_verified_activity(
                clean_model,
                resolved_task,
                "FAILED",
            )

            raise ValueError(
                "Ollama prompt cannot be empty."
            )

        if not self.model_exists(
            clean_model
        ):
            record_verified_activity(
                clean_model,
                resolved_task,
                "FAILED",
            )

            raise ValueError(
                f"Local Ollama model '{clean_model}' "
                "is not installed."
            )

        payload: Dict[str, Any] = {
            "model": clean_model,
            "prompt": clean_prompt,
            "stream": stream,
            "options": {
                "temperature": temperature,
                "num_predict": num_predict,
            },
        }

        if system:
            payload[
                "system"
            ] = system

        start_time = (
            time.perf_counter()
        )

        try:
            with self._client() as client:
                response = client.post(
                    "/api/generate",
                    json=payload,
                )

                response.raise_for_status()

            duration_ms = round(
                (
                    time.perf_counter()
                    - start_time
                )
                * 1000,
                2,
            )

            result = response.json()

            if not isinstance(
                result,
                dict,
            ):
                raise ValueError(
                    "Ollama returned an invalid response."
                )

            response_text = str(
                result.get(
                    "response",
                    "",
                )
                or ""
            ).strip()

            if not response_text:

                record_verified_activity(
                    clean_model,
                    resolved_task,
                    "FAILED",
                    duration_ms,
                )

                raise RuntimeError(
                    "Ollama returned an empty response."
                )

            result[
                "latency_ms"
            ] = duration_ms

            result[
                "model_used"
            ] = clean_model

            result[
                "task_type"
            ] = resolved_task

            record_verified_activity(
                model_id=clean_model,
                task_type=resolved_task,
                status="SUCCESS",
                latency_ms=duration_ms,
            )

            return result

        except httpx.HTTPStatusError as exc:

            duration_ms = round(
                (
                    time.perf_counter()
                    - start_time
                )
                * 1000,
                2,
            )

            record_verified_activity(
                model_id=clean_model,
                task_type=resolved_task,
                status="FAILED",
                latency_ms=duration_ms,
            )

            raise RuntimeError(
                "Ollama generation failed with "
                f"HTTP {exc.response.status_code}: "
                f"{exc.response.text}"
            ) from exc

        except (
            httpx.ConnectError,
            httpx.TimeoutException,
            httpx.RequestError,
        ) as exc:

            duration_ms = round(
                (
                    time.perf_counter()
                    - start_time
                )
                * 1000,
                2,
            )

            record_verified_activity(
                model_id=clean_model,
                task_type=resolved_task,
                status="FAILED",
                latency_ms=duration_ms,
            )

            raise RuntimeError(
                "Could not connect to local Ollama."
            ) from exc

        except (
            ValueError,
            TypeError,
        ) as exc:

            duration_ms = round(
                (
                    time.perf_counter()
                    - start_time
                )
                * 1000,
                2,
            )

            record_verified_activity(
                model_id=clean_model,
                task_type=resolved_task,
                status="FAILED",
                latency_ms=duration_ms,
            )

            raise RuntimeError(
                f"Invalid Ollama response: {exc}"
            ) from exc


# ---------------------------------------------------------------------------
# SHARED NOVA INSTANCE
# ---------------------------------------------------------------------------

ollama_manager = OllamaManager()


def ollama_available() -> bool:
    return ollama_manager.is_available()


def get_local_models() -> List[Dict[str, Any]]:
    return ollama_manager.list_models()