"""Unit tests for Bot and ObserveAPI using mocked bridge layer."""

import asyncio

import pytest

from pyflayer._bridge.event_relay import EventRelay
from pyflayer.bot import Bot, ObserveAPI
from pyflayer.models.errors import PyflayerConnectionError
from pyflayer.models.events import ChatEvent, SpawnEvent


class TestObserveAPI:
    """Tests for ObserveAPI handler registration (no JS needed)."""

    def test_on_decorator(self) -> None:
        relay = EventRelay()
        api = ObserveAPI(relay)

        @api.on(ChatEvent)
        async def handler(event: ChatEvent) -> None:
            pass

        assert handler in relay._handlers[ChatEvent]

    def test_on_direct(self) -> None:
        relay = EventRelay()
        api = ObserveAPI(relay)

        async def handler(event: ChatEvent) -> None:
            pass

        api.on(ChatEvent, handler)
        assert handler in relay._handlers[ChatEvent]

    def test_off(self) -> None:
        relay = EventRelay()
        api = ObserveAPI(relay)

        async def handler(event: ChatEvent) -> None:
            pass

        api.on(ChatEvent, handler)
        api.off(ChatEvent, handler)
        assert handler not in relay._handlers[ChatEvent]

    def test_on_raw_queues_before_bind(self) -> None:
        relay = EventRelay()
        api = ObserveAPI(relay)

        @api.on_raw("entityMoved")
        async def handler(data: dict) -> None:
            pass

        # Before _bind_js, event should be pending
        assert "entityMoved" in api._pending_raw_events
        assert "entityMoved" not in api._bound_raw_events


class TestBotState:
    """Tests for Bot state without a real connection."""

    def test_not_connected_raises(self) -> None:
        bot = Bot(host="localhost")
        with pytest.raises(PyflayerConnectionError):
            _ = bot.position

    def test_not_connected_health_raises(self) -> None:
        bot = Bot(host="localhost")
        with pytest.raises(PyflayerConnectionError):
            _ = bot.health

    def test_is_connected_default(self) -> None:
        bot = Bot(host="localhost")
        assert bot.is_connected is False

    def test_username_from_config(self) -> None:
        bot = Bot(host="localhost", username="TestBot")
        assert bot.username == "TestBot"


class TestEventRelayDispatch:
    """Tests for EventRelay dispatch mechanics."""

    @pytest.mark.asyncio
    async def test_wait_for_resolves(self) -> None:
        relay = EventRelay()
        loop = asyncio.get_running_loop()
        relay.set_loop(loop)

        event = SpawnEvent()

        async def post_later() -> None:
            await asyncio.sleep(0.01)
            relay._dispatch(SpawnEvent, event)

        asyncio.create_task(post_later())
        result = await relay.wait_for(SpawnEvent, timeout=1.0)
        assert isinstance(result, SpawnEvent)

    @pytest.mark.asyncio
    async def test_wait_for_timeout(self) -> None:
        relay = EventRelay()
        loop = asyncio.get_running_loop()
        relay.set_loop(loop)

        with pytest.raises(asyncio.TimeoutError):
            await relay.wait_for(SpawnEvent, timeout=0.01)

    @pytest.mark.asyncio
    async def test_handler_called(self) -> None:
        relay = EventRelay()
        loop = asyncio.get_running_loop()
        relay.set_loop(loop)

        received: list[ChatEvent] = []

        async def handler(event: ChatEvent) -> None:
            received.append(event)

        relay.add_handler(ChatEvent, handler)

        event = ChatEvent(sender="Steve", message="hi", timestamp=0.0)
        relay._dispatch(ChatEvent, event)

        # Give the task a chance to run
        await asyncio.sleep(0.01)
        assert len(received) == 1
        assert received[0].sender == "Steve"
