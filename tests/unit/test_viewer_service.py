"""Unit tests for ViewerService (prismarine-viewer bridge)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from minethon._bridge.services.viewer import ViewerService
from minethon.bot import Bot
from minethon.models.errors import MinethonConnectionError


class TestViewerServiceLifecycle:
    """Tests for ViewerService start/stop/is_started behavior."""

    def _make_service(self) -> tuple[ViewerService, MagicMock, MagicMock]:
        """Create a ViewerService with mocked runtime and js_bot."""
        runtime = MagicMock()
        js_bot = MagicMock()
        service = ViewerService(runtime, js_bot)
        return service, runtime, js_bot

    def test_initial_state(self) -> None:
        """Service should not be started after construction."""
        service, _runtime, _js_bot = self._make_service()
        assert service.is_started is False

    def test_start_calls_require_and_mineflayer(self) -> None:
        """start() should require prismarine-viewer and call mod.mineflayer()."""
        service, runtime, js_bot = self._make_service()
        mod = MagicMock()
        runtime.require.return_value = mod

        service.start(port=8080, view_distance=4, first_person=True)

        runtime.require.assert_called_once_with("prismarine-viewer")
        mod.mineflayer.assert_called_once_with(
            js_bot,
            {
                "viewDistance": 4,
                "firstPerson": True,
                "port": 8080,
            },
        )
        assert service.is_started is True

    def test_start_default_options(self) -> None:
        """start() with no args should use default port=3007, viewDistance=6, firstPerson=False."""
        service, runtime, js_bot = self._make_service()
        mod = MagicMock()
        runtime.require.return_value = mod

        service.start()

        mod.mineflayer.assert_called_once_with(
            js_bot,
            {
                "viewDistance": 6,
                "firstPerson": False,
                "port": 3007,
            },
        )

    def test_start_is_idempotent(self) -> None:
        """Calling start() twice should only call require/mineflayer once."""
        service, runtime, _js_bot = self._make_service()
        runtime.require.return_value = MagicMock()

        service.start()
        service.start()

        runtime.require.assert_called_once()

    def test_stop_when_started(self) -> None:
        """stop() should call viewer.close() and reset is_started."""
        service, runtime, js_bot = self._make_service()
        runtime.require.return_value = MagicMock()

        service.start()
        assert service.is_started is True

        service.stop()
        js_bot.viewer.close.assert_called_once()
        assert service.is_started is False

    def test_stop_when_not_started(self) -> None:
        """stop() on an unstarted service should be a no-op."""
        service, _runtime, js_bot = self._make_service()

        service.stop()  # should not raise

        js_bot.viewer.close.assert_not_called()
        assert service.is_started is False

    def test_stop_survives_attribute_error(self) -> None:
        """stop() should not raise if viewer.close() raises AttributeError."""
        service, runtime, js_bot = self._make_service()
        runtime.require.return_value = MagicMock()
        service.start()

        js_bot.viewer.close.side_effect = AttributeError("no viewer")

        service.stop()  # should not raise
        assert service.is_started is False

    def test_stop_survives_type_error(self) -> None:
        """stop() should not raise if viewer.close() raises TypeError."""
        service, runtime, js_bot = self._make_service()
        runtime.require.return_value = MagicMock()
        service.start()

        js_bot.viewer.close.side_effect = TypeError("bad call")

        service.stop()  # should not raise
        assert service.is_started is False

    def test_start_after_stop_restarts(self) -> None:
        """After stop(), start() should re-initialize the viewer."""
        service, runtime, _js_bot = self._make_service()
        mod = MagicMock()
        runtime.require.return_value = mod

        service.start()
        service.stop()
        service.start()

        assert runtime.require.call_count == 2
        assert service.is_started is True


class TestBotViewerProperty:
    """Tests for Bot.viewer lazy property."""

    def test_viewer_raises_when_not_connected(self) -> None:
        """Accessing bot.viewer before connect() should raise."""
        bot = Bot(host="localhost")
        with pytest.raises(MinethonConnectionError):
            _ = bot.viewer

    @pytest.mark.asyncio
    async def test_viewer_cleared_after_disconnect(self) -> None:
        """bot._viewer_service should be None after disconnect()."""
        bot = Bot(host="localhost")
        # Simulate a viewer service being set
        service = MagicMock()
        bot._viewer_service = service

        await bot.disconnect()

        service.stop.assert_called_once()
        assert bot._viewer_service is None
