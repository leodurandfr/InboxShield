"""Mistral AI LLM provider."""

import logging

from mistralai import Mistral

from app.llm.base import BaseLLMProvider

logger = logging.getLogger(__name__)

# Common Mistral models.
MISTRAL_MODELS = [
    {"name": "mistral-large-latest", "size": None},
    {"name": "mistral-medium-latest", "size": None},
    {"name": "mistral-small-latest", "size": None},
    {"name": "open-mistral-nemo", "size": None},
    {"name": "codestral-latest", "size": None},
]


class MistralProvider(BaseLLMProvider):
    """LLM provider for Mistral AI models."""

    provider_name = "mistral"

    def __init__(
        self,
        api_key: str,
        model: str = "mistral-small-latest",
        temperature: float = 0.1,
        max_tokens: int = 1024,
    ):
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self._client = Mistral(api_key=api_key)

    async def generate(self, system_prompt: str, user_prompt: str) -> str:
        """Send a chat completion request to Mistral."""
        response = await self._client.chat.complete_async(
            model=self.model,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        return response.choices[0].message.content or ""

    async def is_available(self) -> bool:
        """Check connectivity by listing models."""
        try:
            response = await self._client.models.list_async()
            return bool(response.data)
        except Exception:
            logger.debug("Mistral not available for model %s", self.model)
            return False

    def get_model_name(self) -> str:
        return self.model

    async def list_models(self) -> list[dict]:
        """List models from the Mistral API."""
        try:
            response = await self._client.models.list_async()
            return [
                {"name": m.id, "size": None}
                for m in sorted(response.data, key=lambda m: m.id)
            ]
        except Exception:
            logger.exception("Failed to list Mistral models")
            return [{"name": m["name"], "size": m["size"]} for m in MISTRAL_MODELS]
