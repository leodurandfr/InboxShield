"""Anthropic (Claude) LLM provider."""

import logging

from anthropic import AsyncAnthropic

from app.llm.base import BaseLLMProvider

logger = logging.getLogger(__name__)

# Models available via the Anthropic API (ordered by capability).
ANTHROPIC_MODELS = [
    {"name": "claude-sonnet-4-20250514", "size": None},
    {"name": "claude-haiku-4-20250414", "size": None},
    {"name": "claude-3-5-sonnet-20241022", "size": None},
    {"name": "claude-3-5-haiku-20241022", "size": None},
]


class AnthropicProvider(BaseLLMProvider):
    """LLM provider for Anthropic Claude models."""

    provider_name = "anthropic"

    def __init__(
        self,
        api_key: str,
        model: str = "claude-sonnet-4-20250514",
        temperature: float = 0.1,
        max_tokens: int = 1024,
    ):
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self._client = AsyncAnthropic(api_key=api_key)

    async def generate(self, system_prompt: str, user_prompt: str) -> str:
        """Send a chat completion request to Claude."""
        message = await self._client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        return message.content[0].text

    async def is_available(self) -> bool:
        """Check connectivity by sending a minimal request."""
        try:
            msg = await self._client.messages.create(
                model=self.model,
                max_tokens=8,
                messages=[{"role": "user", "content": "ping"}],
            )
            return bool(msg.content)
        except Exception:
            logger.debug("Anthropic not available for model %s", self.model)
            return False

    def get_model_name(self) -> str:
        return self.model

    @staticmethod
    def list_models() -> list[dict]:
        """Return known Anthropic models (static list, no API call needed)."""
        return [{"name": m["name"], "size": m["size"]} for m in ANTHROPIC_MODELS]
