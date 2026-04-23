"""Ollama health, model inspection, and pull helpers.

Subprocess management is deliberately out of scope — on production (Mac
Mini) Ollama runs natively under launchd; inside Docker the `ollama`
container is managed by Compose. This module only talks to the HTTP API.
"""

import json
import logging
import shutil
from collections.abc import AsyncIterator, Callable

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class OllamaManager:
    def __init__(self) -> None:
        self._managed_by_us = False
        self._pid: int | None = None

    # ------------------------------------------------------------------
    # Status / inspection
    # ------------------------------------------------------------------

    def get_status(self) -> dict:
        running = self._is_running_sync()
        return {
            "running": running,
            "managed_by_us": self._managed_by_us,
            "pid": self._pid,
            "binary_path": shutil.which("ollama"),
        }

    def _is_running_sync(self) -> bool:
        try:
            with httpx.Client(timeout=1.5) as client:
                r = client.get(f"{settings.ollama_base_url}/api/tags")
                return r.status_code == 200
        except Exception:
            return False

    async def is_running(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                r = await client.get(f"{settings.ollama_base_url}/api/tags")
                return r.status_code == 200
        except Exception:
            return False

    async def list_installed_models(self) -> list[dict]:
        """Return the list of models Ollama currently has on disk.

        Each dict has keys: name, size, digest, modified_at.
        Empty list if Ollama is unreachable.
        """
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                r = await client.get(f"{settings.ollama_base_url}/api/tags")
                r.raise_for_status()
                data = r.json()
        except Exception as exc:
            logger.debug("list_installed_models: %s", exc)
            return []
        return data.get("models", []) or []

    async def has_model(self, name: str) -> bool:
        models = await self.list_installed_models()
        return any(m.get("name") == name for m in models)

    # ------------------------------------------------------------------
    # Pulling
    # ------------------------------------------------------------------

    async def pull_model(
        self,
        name: str,
        on_progress: Callable[[dict], None] | None = None,
    ) -> bool:
        """Pull a model via POST /api/pull, streaming progress to on_progress.

        Returns True on success, False if Ollama returned an error or is
        unreachable. Does not raise — callers can poll a progress dict.
        """
        url = f"{settings.ollama_base_url}/api/pull"
        try:
            async with httpx.AsyncClient(timeout=None) as client:
                async with client.stream(
                    "POST", url, json={"name": name, "stream": True}
                ) as resp:
                    if resp.status_code != 200:
                        logger.warning("pull_model(%s): HTTP %s", name, resp.status_code)
                        return False
                    async for line in resp.aiter_lines():
                        if not line:
                            continue
                        try:
                            event = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        if on_progress:
                            try:
                                on_progress(event)
                            except Exception:
                                logger.exception("pull_model: progress callback raised")
                        if event.get("error"):
                            logger.warning("pull_model(%s) error: %s", name, event["error"])
                            return False
        except httpx.HTTPError as exc:
            logger.warning("pull_model(%s) transport error: %s", name, exc)
            return False
        return True

    async def stream_pull(self, name: str) -> AsyncIterator[dict]:
        """Lower-level streaming helper — yields each progress event."""
        url = f"{settings.ollama_base_url}/api/pull"
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream(
                "POST", url, json={"name": name, "stream": True}
            ) as resp:
                if resp.status_code != 200:
                    return
                async for line in resp.aiter_lines():
                    if not line:
                        continue
                    try:
                        yield json.loads(line)
                    except json.JSONDecodeError:
                        continue

    async def auto_pull_if_missing(self, name: str) -> bool:
        """Pull `name` only if it isn't already installed.

        Use this on startup to ensure the default model is ready.
        Returns True if the model is available after the call.
        """
        if not await self.is_running():
            return False
        if await self.has_model(name):
            return True
        logger.info("Model %s missing — starting auto-pull", name)
        return await self.pull_model(name)

    async def delete_model(self, name: str) -> bool:
        url = f"{settings.ollama_base_url}/api/delete"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                r = await client.request("DELETE", url, json={"name": name})
                return r.status_code in (200, 204)
        except httpx.HTTPError as exc:
            logger.warning("delete_model(%s) transport error: %s", name, exc)
            return False

    # ------------------------------------------------------------------
    # Lifecycle (no-op outside Mac native scenario)
    # ------------------------------------------------------------------

    async def restart(self) -> None:
        logger.info("OllamaManager.restart() called (no-op — use your process manager)")


ollama_manager = OllamaManager()
