"""API routes for application settings and LLM configuration."""

import asyncio
import logging
import time
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.schemas.settings import (
    LLMModelInfo,
    LLMModelsResponse,
    LLMTestResponse,
    SettingsResponse,
    SettingsUpdate,
)
from app.services.classifier import get_llm_provider, get_settings
from app.services.encryption import encrypt
from app.services.scheduler import update_poll_interval

logger = logging.getLogger(__name__)

router = APIRouter()

# Active pull tasks: pull_id -> {"task", "model", "status", "progress"}
_active_pulls: dict[str, dict] = {}

# Curated list of recommended Ollama models
RECOMMENDED_MODELS = {
    "qwen2.5:7b",
    "qwen2.5:14b",
    "llama3.1:8b",
    "mistral:7b",
    "gemma2:9b",
}


# ---------------------------------------------------------------------------
# GET / PUT settings
# ---------------------------------------------------------------------------


@router.get("", response_model=SettingsResponse)
async def get_current_settings(db: AsyncSession = Depends(get_db)):
    """Get current application settings."""
    settings = await get_settings(db)

    return _build_response(settings)


@router.put("", response_model=SettingsResponse)
async def update_settings(data: SettingsUpdate, db: AsyncSession = Depends(get_db)):
    """Update application settings."""
    settings = await get_settings(db)

    update_data = data.model_dump(exclude_unset=True)

    # Handle API key encryption
    if "llm_api_key" in update_data:
        api_key = update_data.pop("llm_api_key")
        if api_key:
            settings.llm_api_key_encrypted = encrypt(api_key)
        else:
            settings.llm_api_key_encrypted = None

    # Handle app password (store as-is for now; could hash later)
    if "app_password" in update_data:
        password = update_data.pop("app_password")
        settings.app_password = password if password else None

    # Apply other fields
    for key, value in update_data.items():
        if hasattr(settings, key):
            setattr(settings, key, value)

    # Update scheduler if polling interval changed
    if "polling_interval_minutes" in update_data:
        try:
            await update_poll_interval(settings.polling_interval_minutes)
        except Exception:
            pass  # Scheduler may not be running yet

    return _build_response(settings)


def _build_response(settings) -> SettingsResponse:
    """Build a SettingsResponse from the ORM model."""
    return SettingsResponse(
        llm_provider=settings.llm_provider,
        llm_model=settings.llm_model,
        llm_base_url=settings.llm_base_url,
        llm_temperature=settings.llm_temperature,
        polling_interval_minutes=settings.polling_interval_minutes,
        confidence_threshold=settings.confidence_threshold,
        auto_mode=settings.auto_mode,
        max_few_shot_examples=settings.max_few_shot_examples,
        body_excerpt_length=settings.body_excerpt_length,
        retention_days=settings.retention_days,
        email_retention_days=settings.email_retention_days,
        phishing_auto_quarantine=settings.phishing_auto_quarantine,
        initial_fetch_since=settings.initial_fetch_since,
        has_api_key=bool(settings.llm_api_key_encrypted),
        has_app_password=bool(settings.app_password),
    )


# ---------------------------------------------------------------------------
# LLM models & test
# ---------------------------------------------------------------------------


@router.get("/llm/models", response_model=LLMModelsResponse)
async def list_llm_models(
    provider: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """List available LLM models from the given or current provider."""
    settings = await get_settings(db)

    provider_name = provider or settings.llm_provider

    if provider_name == "ollama":
        from app.config import settings as app_settings
        from app.llm.ollama import OllamaProvider

        ollama_url = (
            settings.llm_base_url or app_settings.ollama_base_url or "http://localhost:11434"
        )
        provider = OllamaProvider(
            base_url=ollama_url,
            model=settings.llm_model,
        )
        try:
            models = await provider.list_models()
            return LLMModelsResponse(
                provider="ollama",
                models=[
                    LLMModelInfo(
                        name=m.get("name", ""),
                        size=m.get("size"),
                        modified_at=m.get("modified_at"),
                    )
                    for m in models
                    if m.get("name")
                ],
            )
        except Exception as e:
            raise HTTPException(
                status_code=503,
                detail=f"Impossible de contacter Ollama: {e}",
            )

    if provider_name == "anthropic":
        from app.llm.anthropic import AnthropicProvider

        return LLMModelsResponse(
            provider="anthropic",
            models=[LLMModelInfo(name=m["name"]) for m in AnthropicProvider.list_models()],
        )

    if provider_name in ("openai", "mistral"):
        # For OpenAI/Mistral, try dynamic listing via API; fall back to static list
        try:
            llm = await get_llm_provider(db)
            models = await llm.list_models()
            return LLMModelsResponse(
                provider=provider_name,
                models=[LLMModelInfo(name=m["name"]) for m in models if m.get("name")],
            )
        except Exception:
            # Fall back to static list
            if provider_name == "openai":
                from app.llm.openai import OPENAI_MODELS

                static = OPENAI_MODELS
            else:
                from app.llm.mistral import MISTRAL_MODELS

                static = MISTRAL_MODELS
            return LLMModelsResponse(
                provider=provider_name,
                models=[LLMModelInfo(name=m["name"]) for m in static],
            )

    return LLMModelsResponse(provider=provider_name, models=[])


# ---------------------------------------------------------------------------
# LLM model pull (with cancel support)
# ---------------------------------------------------------------------------


async def _do_pull(pull_id: str, model_name: str, ollama_url: str) -> None:
    """Background task to pull an Ollama model with progress tracking."""
    import ollama as ollama_sdk

    try:
        client = ollama_sdk.AsyncClient(host=ollama_url)
        async for progress in await client.pull(model_name, stream=True):
            if pull_id not in _active_pulls:
                break
            status = progress.get("status", "")
            total = progress.get("total", 0)
            completed = progress.get("completed", 0)
            pct = (completed / total * 100) if total else 0
            _active_pulls[pull_id]["status"] = status
            _active_pulls[pull_id]["progress"] = round(pct, 1)

        if pull_id in _active_pulls:
            _active_pulls[pull_id]["status"] = "done"
            _active_pulls[pull_id]["progress"] = 100
    except asyncio.CancelledError:
        logger.info("Pull cancelled for model %s (pull_id=%s)", model_name, pull_id)
        if pull_id in _active_pulls:
            _active_pulls[pull_id]["status"] = "cancelled"
        raise
    except Exception as e:
        logger.exception("Pull failed for model %s", model_name)
        if pull_id in _active_pulls:
            _active_pulls[pull_id]["status"] = f"error: {e}"


@router.post("/llm/pull")
async def pull_llm_model(data: dict, db: AsyncSession = Depends(get_db)):
    """Start pulling/downloading an Ollama model. Returns a pull_id for status/cancel."""
    settings = await get_settings(db)

    if settings.llm_provider != "ollama":
        raise HTTPException(status_code=400, detail="Pull uniquement disponible pour Ollama")

    model_name = data.get("model")
    if not model_name:
        raise HTTPException(status_code=400, detail="Nom du modèle requis")

    if model_name not in RECOMMENDED_MODELS:
        raise HTTPException(
            status_code=400,
            detail="Seuls les modèles recommandés peuvent être téléchargés via l'interface",
        )

    from app.config import settings as app_settings

    ollama_url = settings.llm_base_url or app_settings.ollama_base_url or "http://localhost:11434"

    pull_id = str(uuid.uuid4())[:8]
    task = asyncio.create_task(_do_pull(pull_id, model_name, ollama_url))
    _active_pulls[pull_id] = {
        "task": task,
        "model": model_name,
        "status": "starting",
        "progress": 0,
    }

    # Auto-cleanup when the task finishes
    def _cleanup(t: asyncio.Task) -> None:  # noqa: ARG001
        # Keep entry for a while so frontend can poll the final status
        pass

    task.add_done_callback(_cleanup)

    return {"pull_id": pull_id, "model": model_name, "status": "started"}


@router.get("/llm/pull/{pull_id}")
async def get_pull_status(pull_id: str):
    """Get the status of an ongoing model pull."""
    entry = _active_pulls.get(pull_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Pull introuvable")

    return {
        "pull_id": pull_id,
        "model": entry["model"],
        "status": entry["status"],
        "progress": entry["progress"],
    }


@router.delete("/llm/pull/{pull_id}")
async def cancel_pull(pull_id: str):
    """Cancel an ongoing model pull."""
    entry = _active_pulls.get(pull_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Pull introuvable")

    task: asyncio.Task = entry["task"]
    if not task.done():
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    _active_pulls.pop(pull_id, None)
    return {"pull_id": pull_id, "status": "cancelled"}


# ---------------------------------------------------------------------------
# LLM test
# ---------------------------------------------------------------------------


@router.post("/llm/test", response_model=LLMTestResponse)
async def test_llm(db: AsyncSession = Depends(get_db)):
    """Test LLM connectivity and response time."""
    settings = await get_settings(db)

    try:
        llm = await get_llm_provider(db)

        start = time.monotonic()
        available = await llm.is_available()
        latency = int((time.monotonic() - start) * 1000)

        if not available:
            return LLMTestResponse(
                success=False,
                provider=settings.llm_provider,
                model=settings.llm_model,
                error="LLM provider non disponible",
            )

        # Quick test: generate a simple response
        start = time.monotonic()
        await llm.generate(
            "Tu es un assistant de test.",
            "Réponds uniquement 'OK' si tu fonctionnes correctement.",
        )
        latency = int((time.monotonic() - start) * 1000)

        return LLMTestResponse(
            success=True,
            provider=settings.llm_provider,
            model=llm.get_model_name(),
            latency_ms=latency,
        )

    except Exception as e:
        return LLMTestResponse(
            success=False,
            provider=settings.llm_provider,
            model=settings.llm_model,
            error=str(e),
        )
