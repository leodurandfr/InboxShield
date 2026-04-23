"""Ollama health, model inspection, and pull helpers.

Subprocess management is deliberately out of scope — on production (Mac
Mini) Ollama runs natively under launchd; inside Docker the `ollama`
container is managed by Compose. This module only talks to the HTTP API.
"""

import json
import logging
import os
import shutil
import subprocess
from collections.abc import AsyncIterator, Callable
from datetime import datetime
from typing import Literal

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

InstallMethod = Literal["homebrew", "systemd", "app", "docker", "unknown"]
ServiceStatus = Literal["running", "stopped", "not-installed"]


class OllamaManager:
    def __init__(self) -> None:
        self._managed_by_us = False
        self._pid: int | None = None

    # ------------------------------------------------------------------
    # Status / inspection
    # ------------------------------------------------------------------

    def get_status(self) -> dict:
        running = self._is_running_sync()
        binary_path = shutil.which("ollama")
        install_method = self.detect_install_method()
        if running:
            service_status: ServiceStatus = "running"
        elif install_method == "unknown" and binary_path is None:
            service_status = "not-installed"
        else:
            service_status = "stopped"
        return {
            "running": running,
            "managed_by_us": self._managed_by_us,
            "pid": self._pid,
            "binary_path": binary_path,
            "install_method": install_method,
            "service_status": service_status,
        }

    def detect_install_method(self) -> InstallMethod:
        """Best-effort heuristic for how Ollama was installed on this host.

        The backend often runs inside Docker, so filesystem probes for
        `/Applications/Ollama.app` or `brew` typically fail — in that case
        we return "docker" when the configured base URL points to the
        in-stack container, otherwise "unknown".
        """
        base_url = settings.ollama_base_url or ""
        if "ollama:" in base_url and not os.path.exists("/Applications/Ollama.app"):
            # Inside docker compose, backend → service named "ollama".
            if not shutil.which("ollama") and not os.path.exists("/usr/bin/brew"):
                return "docker"

        try:
            if os.path.exists("/Applications/Ollama.app"):
                return "app"
        except OSError:
            pass

        brew = shutil.which("brew")
        if brew:
            try:
                res = subprocess.run(
                    [brew, "list", "ollama"],
                    capture_output=True,
                    text=True,
                    timeout=3,
                )
                if res.returncode == 0:
                    return "homebrew"
            except (subprocess.TimeoutExpired, OSError):
                pass

        systemctl = shutil.which("systemctl")
        if systemctl:
            try:
                res = subprocess.run(
                    [systemctl, "is-active", "ollama"],
                    capture_output=True,
                    text=True,
                    timeout=3,
                )
                if res.returncode == 0 and "active" in (res.stdout or ""):
                    return "systemd"
            except (subprocess.TimeoutExpired, OSError):
                pass

        return "unknown"

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

    async def get_loaded_models(self) -> list[dict]:
        """Return models currently loaded in memory (equivalent of `ollama ps`).

        Each dict has keys: name, size_bytes, size_vram_bytes, context_length,
        expires_at. `size_bytes` is total RAM footprint, `size_vram_bytes` is
        the GPU/Metal-resident portion (0 on CPU-only hosts).
        """
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                r = await client.get(f"{settings.ollama_base_url}/api/ps")
                r.raise_for_status()
                data = r.json()
        except Exception as exc:
            logger.debug("get_loaded_models: %s", exc)
            return []

        out: list[dict] = []
        for m in data.get("models", []) or []:
            details = m.get("details") or {}
            ctx = m.get("context_length") or m.get("size_ctx") or details.get("context_length") or 0
            expires_raw = m.get("expires_at")
            expires_at: datetime | None = None
            if expires_raw:
                try:
                    expires_at = datetime.fromisoformat(expires_raw.replace("Z", "+00:00"))
                except (ValueError, AttributeError):
                    expires_at = None
            out.append(
                {
                    "name": m.get("name") or m.get("model") or "",
                    "size_bytes": int(m.get("size") or 0),
                    "size_vram_bytes": int(m.get("size_vram") or 0),
                    "context_length": int(ctx or 0),
                    "expires_at": expires_at,
                }
            )
        return out

    async def unload_model(self, name: str) -> bool:
        """Force-unload a model from RAM by setting keep_alive to 0."""
        url = f"{settings.ollama_base_url}/api/generate"
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                r = await client.post(
                    url,
                    json={"model": name, "prompt": "", "keep_alive": 0, "stream": False},
                )
                return r.status_code == 200
        except httpx.HTTPError as exc:
            logger.warning("unload_model(%s) transport error: %s", name, exc)
            return False

    async def get_disk_usage(self) -> dict:
        """Sum the sizes reported by /api/tags. Returns total_bytes + model_count."""
        models = await self.list_installed_models()
        total = 0
        for m in models:
            try:
                total += int(m.get("size") or 0)
            except (TypeError, ValueError):
                continue
        return {"total_bytes": total, "model_count": len(models)}

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
                async with client.stream("POST", url, json={"name": name, "stream": True}) as resp:
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
            async with client.stream("POST", url, json={"name": name, "stream": True}) as resp:
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
