"""Unit tests for WebInventoryService and related bridge events."""

import asyncio
from unittest.mock import MagicMock

import pytest

from minethon._bridge._events import WebInvStartDoneEvent, WebInvStopDoneEvent
from minethon._bridge.event_relay import EventRelay
from minethon._bridge.services.web_inventory import WebInventoryService
from minethon.models.errors import BridgeError

# -- Done event dataclass tests --


class TestWebInvStartDoneEvent:
    def test_success(self) -> None:
        event = WebInvStartDoneEvent()
        assert event.error is None

    def test_error(self) -> None:
        event = WebInvStartDoneEvent(error="EADDRINUSE")
        assert event.error == "EADDRINUSE"

    def test_frozen(self) -> None:
        event = WebInvStartDoneEvent()
        with pytest.raises(AttributeError):
            event.error = "x"  # type: ignore[misc]


class TestWebInvStopDoneEvent:
    def test_success(self) -> None:
        assert WebInvStopDoneEvent().error is None

    def test_error(self) -> None:
        assert WebInvStopDoneEvent(error="timeout").error == "timeout"

    def test_frozen(self) -> None:
        event = WebInvStopDoneEvent()
        with pytest.raises(AttributeError):
            event.error = "x"  # type: ignore[misc]


# -- WebInventoryService tests --


def _make_runtime_mock() -> MagicMock:
    """Create a mock BridgeRuntime with a working require()."""
    runtime = MagicMock()
    # require("mineflayer-web-inventory") returns a callable module
    mod_fn = MagicMock()
    runtime.require.return_value = mod_fn
    return runtime


def _make_service(
    *, runtime: MagicMock | None = None
) -> tuple[WebInventoryService, MagicMock, MagicMock, EventRelay]:
    """Create a WebInventoryService with mocked dependencies.

    Returns:
        (service, runtime_mock, js_bot_mock, relay)
    """
    rt = runtime or _make_runtime_mock()
    js_bot = MagicMock()
    relay = EventRelay()
    service = WebInventoryService(rt, js_bot, relay)
    return service, rt, js_bot, relay


class TestWebInventoryServiceInit:
    """Tests for the __init__ and property defaults."""

    def test_defaults(self) -> None:
        service, _, _, _ = _make_service()
        assert service.is_initialized is False
        assert service.is_running is False
        assert service.port is None

    @pytest.mark.asyncio
    async def test_initialize_with_start_on_load(self) -> None:
        service, rt, _js_bot, _ = _make_service()
        await service.initialize(port=9000, start_on_load=True)

        assert service.is_initialized is True
        assert service.is_running is True
        assert service.port == 9000
        rt.require.assert_called_with("mineflayer-web-inventory")

    @pytest.mark.asyncio
    async def test_initialize_without_start(self) -> None:
        service, _rt, _js_bot, _ = _make_service()
        await service.initialize(port=4000, start_on_load=False)

        assert service.is_initialized is True
        assert service.is_running is False
        assert service.port == 4000

    @pytest.mark.asyncio
    async def test_initialize_default_port(self) -> None:
        service, _, _, _ = _make_service()
        await service.initialize()
        assert service.port == 3008

    @pytest.mark.asyncio
    async def test_double_initialize_raises(self) -> None:
        service, _, _, _ = _make_service()
        await service.initialize()

        with pytest.raises(BridgeError, match="already initialised"):
            await service.initialize()


class TestWebInventoryServiceStart:
    """Tests for the start() method."""

    @pytest.mark.asyncio
    async def test_start_not_initialized_raises(self) -> None:
        service, _, _, _ = _make_service()
        with pytest.raises(BridgeError, match="not initialised"):
            await service.start()

    @pytest.mark.asyncio
    async def test_start_already_running_raises(self) -> None:
        service, _, _, _ = _make_service()
        await service.initialize(start_on_load=True)
        # Already running because start_on_load=True

        with pytest.raises(BridgeError, match="already running"):
            await service.start()

    @pytest.mark.asyncio
    async def test_start_success(self) -> None:
        service, _, _, relay = _make_service()
        relay.set_loop(asyncio.get_running_loop())
        await service.initialize(start_on_load=False)

        async def post_done() -> None:
            await asyncio.sleep(0.01)
            relay._dispatch(WebInvStartDoneEvent, WebInvStartDoneEvent())

        asyncio.create_task(post_done())
        await service.start()

        assert service.is_running is True

    @pytest.mark.asyncio
    async def test_start_error_from_js(self) -> None:
        service, _, _, relay = _make_service()
        relay.set_loop(asyncio.get_running_loop())
        await service.initialize(start_on_load=False)

        async def post_error() -> None:
            await asyncio.sleep(0.01)
            relay._dispatch(
                WebInvStartDoneEvent,
                WebInvStartDoneEvent(error="EADDRINUSE"),
            )

        asyncio.create_task(post_error())
        with pytest.raises(BridgeError, match="EADDRINUSE"):
            await service.start()

        assert service.is_running is False


class TestWebInventoryServiceStop:
    """Tests for the stop() method."""

    @pytest.mark.asyncio
    async def test_stop_not_initialized_raises(self) -> None:
        service, _, _, _ = _make_service()
        with pytest.raises(BridgeError, match="not initialised"):
            await service.stop()

    @pytest.mark.asyncio
    async def test_stop_not_running_raises(self) -> None:
        service, _, _, _ = _make_service()
        await service.initialize(start_on_load=False)

        with pytest.raises(BridgeError, match="not running"):
            await service.stop()

    @pytest.mark.asyncio
    async def test_stop_success(self) -> None:
        service, _, _, relay = _make_service()
        relay.set_loop(asyncio.get_running_loop())
        await service.initialize(start_on_load=True)

        async def post_done() -> None:
            await asyncio.sleep(0.01)
            relay._dispatch(WebInvStopDoneEvent, WebInvStopDoneEvent())

        asyncio.create_task(post_done())
        await service.stop()

        assert service.is_running is False

    @pytest.mark.asyncio
    async def test_stop_error_from_js(self) -> None:
        service, _, _, relay = _make_service()
        relay.set_loop(asyncio.get_running_loop())
        await service.initialize(start_on_load=True)

        async def post_error() -> None:
            await asyncio.sleep(0.01)
            relay._dispatch(
                WebInvStopDoneEvent,
                WebInvStopDoneEvent(error="server error"),
            )

        asyncio.create_task(post_error())
        with pytest.raises(BridgeError, match="server error"):
            await service.stop()

        # Still marked as running since stop failed
        assert service.is_running is True
