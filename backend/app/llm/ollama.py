"""Ollama LLM provider — local inference via the Ollama SDK."""

import logging

import ollama as ollama_sdk

from app.llm.base import BaseLLMProvider

logger = logging.getLogger(__name__)


class OllamaProvider(BaseLLMProvider):
    """LLM provider for Ollama (local models)."""

    provider_name = "ollama"

    def __init__(self, base_url: str = "http://localhost:11434", model: str = "qwen2.5:7b"):
        self.base_url = base_url
        self.model = model
        self._client = ollama_sdk.AsyncClient(host=base_url)

    async def generate(self, system_prompt: str, user_prompt: str) -> str:
        """Send a chat completion request to Ollama."""
        response = await self._client.chat(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            options={"temperature": 0.1},
            think=False,  # Disable thinking mode (qwen3, deepseek-r1, etc.)
        )
        content = response["message"]["content"]

        # Strip any residual <think>...</think> blocks some models add
        if "<think>" in content:
            import re
            content = re.sub(r"<think>.*?</think>\s*", "", content, flags=re.DOTALL)

        return content.strip()

    async def is_available(self) -> bool:
        """Check if Ollama is reachable and the model is loaded."""
        try:
            response = await self._client.list()
            models = response.models if hasattr(response, "models") else response.get("models", [])
            model_names = [_get_model_name(m) for m in models]
            # Check if our model (or a prefix match) is available
            return any(self.model in name for name in model_names)
        except Exception:
            logger.debug("Ollama not available at %s", self.base_url)
            return False

    def get_model_name(self) -> str:
        return self.model

    async def list_models(self) -> list[dict]:
        """List all models available in Ollama."""
        try:
            response = await self._client.list()
            models = response.models if hasattr(response, "models") else response.get("models", [])
            return [
                {
                    "name": _get_model_name(m),
                    "size": _format_size(getattr(m, "size", 0) if hasattr(m, "size") else m.get("size", 0)),
                    "modified_at": str(getattr(m, "modified_at", "") if hasattr(m, "modified_at") else m.get("modified_at", "")),
                }
                for m in models
            ]
        except Exception:
            logger.exception("Failed to list Ollama models")
            return []


def _get_model_name(m) -> str:
    """Extract model name from Ollama model object or dict (SDK v0.15+ uses Pydantic objects)."""
    if hasattr(m, "model"):
        return getattr(m, "model", "") or getattr(m, "name", "") or ""
    return m.get("model", "") or m.get("name", "") or ""


def _format_size(size_bytes: int) -> str:
    """Format bytes to human-readable size."""
    if size_bytes == 0:
        return "0 B"
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"
