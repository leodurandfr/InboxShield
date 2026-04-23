"""Tests for OllamaManager — all HTTP calls are mocked via respx/httpx.

We don't hit a real Ollama instance; every test patches the module's
httpx client calls to return canned payloads.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.services.ollama_manager import OllamaManager

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_async_client(get=None, post=None):
    """Build an AsyncClient context manager mock with configurable GET/POST."""
    client = AsyncMock()
    client.__aenter__.return_value = client
    client.__aexit__.return_value = None
    if get is not None:
        client.get = AsyncMock(return_value=get)
    if post is not None:
        client.post = AsyncMock(return_value=post)
    return client


def _response(status: int, json_data: dict | None = None) -> MagicMock:
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status
    resp.json = MagicMock(return_value=json_data or {})
    resp.raise_for_status = MagicMock()
    if status >= 400:
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "err", request=MagicMock(), response=resp
        )
    return resp


# ---------------------------------------------------------------------------
# is_running / get_status
# ---------------------------------------------------------------------------


class TestIsRunning:
    @pytest.mark.asyncio
    async def test_returns_true_on_200(self):
        mgr = OllamaManager()
        client = _mock_async_client(get=_response(200, {"models": []}))
        with patch("app.services.ollama_manager.httpx.AsyncClient", return_value=client):
            assert await mgr.is_running() is True

    @pytest.mark.asyncio
    async def test_returns_false_on_transport_error(self):
        mgr = OllamaManager()
        client = AsyncMock()
        client.__aenter__.return_value = client
        client.__aexit__.return_value = None
        client.get = AsyncMock(side_effect=httpx.ConnectError("refused"))
        with patch("app.services.ollama_manager.httpx.AsyncClient", return_value=client):
            assert await mgr.is_running() is False


class TestGetStatus:
    def test_service_status_running_when_http_ok(self):
        mgr = OllamaManager()
        sync_client = MagicMock()
        sync_client.__enter__.return_value = sync_client
        sync_client.__exit__.return_value = None
        sync_client.get.return_value = _response(200, {"models": []})
        with patch("app.services.ollama_manager.httpx.Client", return_value=sync_client):
            status = mgr.get_status()
        assert status["running"] is True
        assert status["service_status"] == "running"

    def test_service_status_not_installed_when_no_binary(self):
        mgr = OllamaManager()
        sync_client = MagicMock()
        sync_client.__enter__.return_value = sync_client
        sync_client.__exit__.return_value = None
        sync_client.get.side_effect = httpx.ConnectError("refused")
        with (
            patch("app.services.ollama_manager.httpx.Client", return_value=sync_client),
            patch("app.services.ollama_manager.shutil.which", return_value=None),
            patch.object(mgr, "detect_install_method", return_value="unknown"),
        ):
            status = mgr.get_status()
        assert status["running"] is False
        assert status["service_status"] == "not-installed"

    def test_service_status_stopped_when_binary_present_but_down(self):
        mgr = OllamaManager()
        sync_client = MagicMock()
        sync_client.__enter__.return_value = sync_client
        sync_client.__exit__.return_value = None
        sync_client.get.side_effect = httpx.ConnectError("refused")
        with (
            patch("app.services.ollama_manager.httpx.Client", return_value=sync_client),
            patch("app.services.ollama_manager.shutil.which", return_value="/usr/bin/ollama"),
            patch.object(mgr, "detect_install_method", return_value="homebrew"),
        ):
            status = mgr.get_status()
        assert status["running"] is False
        assert status["service_status"] == "stopped"


# ---------------------------------------------------------------------------
# detect_install_method
# ---------------------------------------------------------------------------


class TestDetectInstallMethod:
    def test_app_bundle_detected(self):
        mgr = OllamaManager()
        with patch("app.services.ollama_manager.os.path.exists", return_value=True):
            assert mgr.detect_install_method() == "app"

    def test_homebrew_detected_when_brew_list_returns_zero(self):
        mgr = OllamaManager()
        fake = MagicMock()
        fake.returncode = 0
        fake.stdout = "ollama"
        with (
            patch("app.services.ollama_manager.os.path.exists", return_value=False),
            patch(
                "app.services.ollama_manager.shutil.which",
                side_effect=lambda n: "/opt/homebrew/bin/brew" if n == "brew" else None,
            ),
            patch("app.services.ollama_manager.subprocess.run", return_value=fake),
        ):
            assert mgr.detect_install_method() == "homebrew"

    def test_unknown_when_nothing_matches(self):
        mgr = OllamaManager()
        with (
            patch("app.services.ollama_manager.os.path.exists", return_value=False),
            patch("app.services.ollama_manager.shutil.which", return_value=None),
        ):
            assert mgr.detect_install_method() == "unknown"


# ---------------------------------------------------------------------------
# list_installed_models / has_model
# ---------------------------------------------------------------------------


class TestListInstalledModels:
    @pytest.mark.asyncio
    async def test_returns_models_from_api_tags(self):
        mgr = OllamaManager()
        payload = {
            "models": [
                {"name": "qwen3:8b", "size": 5_200_000_000, "digest": "abc"},
                {"name": "llama3.2:1b", "size": 1_300_000_000, "digest": "def"},
            ]
        }
        client = _mock_async_client(get=_response(200, payload))
        with patch("app.services.ollama_manager.httpx.AsyncClient", return_value=client):
            models = await mgr.list_installed_models()
        assert len(models) == 2
        assert models[0]["name"] == "qwen3:8b"

    @pytest.mark.asyncio
    async def test_returns_empty_on_error(self):
        mgr = OllamaManager()
        client = AsyncMock()
        client.__aenter__.return_value = client
        client.__aexit__.return_value = None
        client.get = AsyncMock(side_effect=httpx.ConnectError("refused"))
        with patch("app.services.ollama_manager.httpx.AsyncClient", return_value=client):
            assert await mgr.list_installed_models() == []

    @pytest.mark.asyncio
    async def test_has_model_positive_and_negative(self):
        mgr = OllamaManager()
        payload = {"models": [{"name": "qwen3:8b", "size": 1}]}
        client = _mock_async_client(get=_response(200, payload))
        with patch("app.services.ollama_manager.httpx.AsyncClient", return_value=client):
            assert await mgr.has_model("qwen3:8b") is True

        client = _mock_async_client(get=_response(200, payload))
        with patch("app.services.ollama_manager.httpx.AsyncClient", return_value=client):
            assert await mgr.has_model("missing:latest") is False


# ---------------------------------------------------------------------------
# get_loaded_models
# ---------------------------------------------------------------------------


class TestGetLoadedModels:
    @pytest.mark.asyncio
    async def test_parses_ps_payload(self):
        mgr = OllamaManager()
        payload = {
            "models": [
                {
                    "name": "qwen3:8b",
                    "size": 5_200_000_000,
                    "size_vram": 4_800_000_000,
                    "context_length": 8192,
                    "expires_at": "2026-04-23T12:34:56Z",
                }
            ]
        }
        client = _mock_async_client(get=_response(200, payload))
        with patch("app.services.ollama_manager.httpx.AsyncClient", return_value=client):
            loaded = await mgr.get_loaded_models()
        assert len(loaded) == 1
        assert loaded[0]["name"] == "qwen3:8b"
        assert loaded[0]["size_bytes"] == 5_200_000_000
        assert loaded[0]["size_vram_bytes"] == 4_800_000_000
        assert loaded[0]["context_length"] == 8192
        assert isinstance(loaded[0]["expires_at"], datetime)
        assert loaded[0]["expires_at"].tzinfo is not None

    @pytest.mark.asyncio
    async def test_empty_when_no_models_loaded(self):
        mgr = OllamaManager()
        client = _mock_async_client(get=_response(200, {"models": []}))
        with patch("app.services.ollama_manager.httpx.AsyncClient", return_value=client):
            assert await mgr.get_loaded_models() == []

    @pytest.mark.asyncio
    async def test_tolerates_missing_fields(self):
        mgr = OllamaManager()
        payload = {"models": [{"model": "foo:latest"}]}
        client = _mock_async_client(get=_response(200, payload))
        with patch("app.services.ollama_manager.httpx.AsyncClient", return_value=client):
            loaded = await mgr.get_loaded_models()
        assert loaded[0]["name"] == "foo:latest"
        assert loaded[0]["size_bytes"] == 0
        assert loaded[0]["size_vram_bytes"] == 0
        assert loaded[0]["context_length"] == 0
        assert loaded[0]["expires_at"] is None

    @pytest.mark.asyncio
    async def test_cpu_only_host_has_zero_vram(self):
        """On a CPU-only host, Ollama reports size_vram=0 alongside size."""
        mgr = OllamaManager()
        payload = {
            "models": [
                {"name": "qwen3:8b", "size": 5_200_000_000, "size_vram": 0},
            ]
        }
        client = _mock_async_client(get=_response(200, payload))
        with patch("app.services.ollama_manager.httpx.AsyncClient", return_value=client):
            loaded = await mgr.get_loaded_models()
        assert loaded[0]["size_bytes"] == 5_200_000_000
        assert loaded[0]["size_vram_bytes"] == 0


# ---------------------------------------------------------------------------
# unload_model
# ---------------------------------------------------------------------------


class TestUnloadModel:
    @pytest.mark.asyncio
    async def test_returns_true_on_200(self):
        mgr = OllamaManager()
        client = _mock_async_client(post=_response(200, {"done": True}))
        with patch("app.services.ollama_manager.httpx.AsyncClient", return_value=client):
            assert await mgr.unload_model("qwen3:8b") is True
        # Verify keep_alive=0 payload
        call_kwargs = client.post.call_args.kwargs
        assert call_kwargs["json"]["keep_alive"] == 0
        assert call_kwargs["json"]["model"] == "qwen3:8b"

    @pytest.mark.asyncio
    async def test_returns_false_on_transport_error(self):
        mgr = OllamaManager()
        client = AsyncMock()
        client.__aenter__.return_value = client
        client.__aexit__.return_value = None
        client.post = AsyncMock(side_effect=httpx.ConnectError("refused"))
        with patch("app.services.ollama_manager.httpx.AsyncClient", return_value=client):
            assert await mgr.unload_model("qwen3:8b") is False


# ---------------------------------------------------------------------------
# get_disk_usage
# ---------------------------------------------------------------------------


class TestGetDiskUsage:
    @pytest.mark.asyncio
    async def test_sums_model_sizes(self):
        mgr = OllamaManager()
        payload = {
            "models": [
                {"name": "a", "size": 1_000_000_000},
                {"name": "b", "size": 2_500_000_000},
            ]
        }
        client = _mock_async_client(get=_response(200, payload))
        with patch("app.services.ollama_manager.httpx.AsyncClient", return_value=client):
            usage = await mgr.get_disk_usage()
        assert usage["total_bytes"] == 3_500_000_000
        assert usage["model_count"] == 2

    @pytest.mark.asyncio
    async def test_zero_when_unreachable(self):
        mgr = OllamaManager()
        client = AsyncMock()
        client.__aenter__.return_value = client
        client.__aexit__.return_value = None
        client.get = AsyncMock(side_effect=httpx.ConnectError("refused"))
        with patch("app.services.ollama_manager.httpx.AsyncClient", return_value=client):
            usage = await mgr.get_disk_usage()
        assert usage == {"total_bytes": 0, "model_count": 0}


# ---------------------------------------------------------------------------
# datetime freshness sanity (no time-of-day flakiness)
# ---------------------------------------------------------------------------


def test_datetime_import_is_timezone_aware():
    """Ensure our test reference datetime construction works."""
    assert datetime.now(UTC).tzinfo is not None
