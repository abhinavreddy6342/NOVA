import httpx
from typing import Any, Dict, List, Optional


OLLAMA_BASE_URL = "http://127.0.0.1:11434"
OLLAMA_TAGS_URL = f"{OLLAMA_BASE_URL}/api/tags"
OLLAMA_GENERATE_URL = f"{OLLAMA_BASE_URL}/api/generate"


class OllamaManager:
    """
    Local Ollama control layer for NOVA.

    This class is responsible for:
    - checking Ollama availability
    - discovering locally installed models
    - checking whether a specific model exists
    - generating responses from a selected local model
    """

    def __init__(
        self,
        base_url: str = OLLAMA_BASE_URL,
        timeout: float = 120.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _client(self) -> httpx.Client:
        return httpx.Client(
            base_url=self.base_url,
            timeout=self.timeout,
        )

    def is_available(self) -> bool:
        """
        Check whether the local Ollama server is reachable.
        """

        try:
            with self._client() as client:
                response = client.get("/api/tags")

            return response.is_success

        except (
            httpx.ConnectError,
            httpx.TimeoutException,
            httpx.RequestError,
        ):
            return False

    def list_models(self) -> List[Dict[str, Any]]:
        """
        Return locally installed Ollama models.
        """

        try:
            with self._client() as client:
                response = client.get("/api/tags")
                response.raise_for_status()

            data = response.json()

            return data.get("models", [])

        except (
            httpx.ConnectError,
            httpx.TimeoutException,
            httpx.RequestError,
            ValueError,
        ):
            return []

    def model_exists(self, model_name: str) -> bool:
        """
        Check whether a model is installed locally.
        """

        model_name = model_name.strip()

        if not model_name:
            return False

        models = self.list_models()

        for model in models:
            installed_name = model.get("name")

            if installed_name == model_name:
                return True

        return False

    def generate(
        self,
        model: str,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.4,
        num_predict: int = 512,
        stream: bool = False,
    ) -> Dict[str, Any]:
        """
        Generate a response using a local Ollama model.

        Returns Ollama's JSON response.
        """

        model = model.strip()
        prompt = prompt.strip()

        if not model:
            raise ValueError(
                "Ollama model name cannot be empty."
            )

        if not prompt:
            raise ValueError(
                "Ollama prompt cannot be empty."
            )

        if not self.model_exists(model):
            raise ValueError(
                f"Local Ollama model '{model}' is not installed."
            )

        payload: Dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "stream": stream,
            "options": {
                "temperature": temperature,
                "num_predict": num_predict,
            },
        }

        if system:
            payload["system"] = system

        try:
            with self._client() as client:
                response = client.post(
                    "/api/generate",
                    json=payload,
                )

                response.raise_for_status()

            return response.json()

        except httpx.HTTPStatusError as exc:
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
            raise RuntimeError(
                "Could not connect to local Ollama."
            ) from exc


# Shared NOVA instance.
ollama_manager = OllamaManager()


def ollama_available() -> bool:
    """
    Convenience helper for checking Ollama status.
    """

    return ollama_manager.is_available()


def get_local_models() -> List[Dict[str, Any]]:
    """
    Convenience helper for retrieving local models.
    """

    return ollama_manager.list_models()