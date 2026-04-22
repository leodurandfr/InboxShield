"""OpenAI (GPT) LLM provider."""

import logging

from openai import AsyncOpenAI

from app.llm.base import BaseLLMProvider

logger = logging.getLogger(__name__)

# Common models available via the OpenAI API.
OPENAI_MODELS = [
    {"name": "gpt-4o", "size": None},
    {"name": "gpt-4o-mini", "size": None},
    {"name": "gpt-4-turbo", "size": None},
    {"name": "gpt-3.5-turbo", "size": None},
]


class OpenAIProvider(BaseLLMProvider):
    """LLM provider for OpenAI GPT models."""

    provider_name = "openai"

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-mini",
        base_url: str | None = None,
        temperature: float = 0.1,
        max_tokens: int = 1024,
    ):
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self._client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,  # Allows OpenAI-compatible APIs (e.g. Azure, local)
        )

    async def generate(self, system_prompt: str, user_prompt: str) -> str:
        """Send a chat completion request to OpenAI."""
        response = await self._client.chat.completions.create(
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
            response = await self._client.models.list()
            return bool(response.data)
        except Exception:
            logger.debug("OpenAI not available for model %s", self.model)
            return False

    def get_model_name(self) -> str:
        return self.model

    async def list_models(self) -> list[dict]:
        """List models from the OpenAI API."""
        try:
            response = await self._client.models.list()
            return [
                {"name": m.id, "size": None}
                for m in sorted(response.data, key=lambda m: m.id)
                if "gpt" in m.id or "o1" in m.id or "o3" in m.id
            ]
        except Exception:
            logger.exception("Failed to list OpenAI models")
            return [{"name": m["name"], "size": m["size"]} for m in OPENAI_MODELS]
