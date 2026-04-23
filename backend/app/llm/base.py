"""Abstract base class for LLM providers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class ClassificationResult:
    """Result of an email classification by the LLM."""

    category: str
    confidence: float
    explanation: str = ""
    is_spam: bool = False
    is_phishing: bool = False
    phishing_reasons: list[str] = field(default_factory=list)
    # Metadata
    provider: str = ""
    model: str = ""
    tokens_used: int = 0
    processing_time_ms: int = 0


@dataclass
class RuleInterpretation:
    """Result of a natural language rule interpretation."""

    matches: bool
    reason: str = ""


class BaseLLMProvider(ABC):
    """Abstract interface for LLM providers (Ollama, Anthropic, OpenAI, Mistral)."""

    provider_name: str = "unknown"

    @abstractmethod
    async def generate(self, system_prompt: str, user_prompt: str) -> str:
        """Send a prompt and return the raw text response."""
        ...

    @abstractmethod
    async def is_available(self) -> bool:
        """Check if the provider is reachable."""
        ...

    @abstractmethod
    def get_model_name(self) -> str:
        """Return the current model name."""
        ...
