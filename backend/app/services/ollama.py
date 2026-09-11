import httpx

from app.core.ai_config import NOVA_SYSTEM_PROMPT


OLLAMA_BASE_URL = "http://127.0.0.1:11434"
DEFAULT_MODEL = "llama3.2:latest"


async def generate_response(
    prompt: str,
    model: str = DEFAULT_MODEL,
) -> str:
    payload = {
        "model": model,
        "system": NOVA_SYSTEM_PROMPT,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.4,
            "num_predict": 256,
        },
    }

    async with httpx.AsyncClient(
        timeout=120.0
    ) as client:
        response = await client.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json=payload,
        )

    response.raise_for_status()

    data = response.json()

    return data.get(
        "response",
        "",
    ).strip()