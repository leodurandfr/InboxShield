"""Stub Ollama process manager.

The real implementation will start/stop a local Ollama binary when Ollama
is not running (Mac Mini production scenario). For now we only report the
state without managing any subprocess — this keeps the import graph
bootable and the health endpoint functional.
"""

import logging
import shutil

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class OllamaManager:
    def __init__(self) -> None:
        self._managed_by_us = False
        self._pid: int | None = None

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

    async def restart(self) -> None:
        """Placeholder — real restart logic is not implemented yet."""
        logger.info("OllamaManager.restart() called (stub)")


ollama_manager = OllamaManager()
