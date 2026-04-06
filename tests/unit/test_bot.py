"""Unit tests for Bot and ObserveAPI using mocked bridge layer."""

import asyncio

import pytest

from minethon._bridge._events import (
    DigDoneEvent,
    EquipDoneEvent,
    LookAtDoneEvent,
    PlaceDoneEvent,
)
from minethon._bridge.event_relay import EventRelay
from minethon.api.observe import ObserveAPI
from minethon.bot import Bot
from minethon.models.errors import (
    NotSpawnedError,
    MinethonConnectionError,
)
from minethon.models.events import (
    ChatEvent,
    EndEvent,
    GoalFailedEvent,
    GoalReachedEvent,
    SpawnEvent,
)
from minethon.models.vec3 import Vec3


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

        assert "entityMoved" in api._pending_raw_events
        assert "entityMoved" not in api._bound_raw_events

    @pytest.mark.asyncio
    async def test_wait_for_no_loop_raises_connection_error(self) -> None:
        relay = EventRelay()
        api = ObserveAPI(relay)

        with pytest.raises(MinethonConnectionError):
            await api.wait_for(SpawnEvent, timeout=0.01)

    def test_on_raw_direct_call(self) -> None:
        relay = EventRelay()
        api = ObserveAPI(relay)

        async def handler(data: dict) -> None:
            pass

        api.on_raw("test_event", handler)
        assert "test_event" in api._pending_raw_events

    def test_off_raw(self) -> None:
        relay = EventRelay()
        api = ObserveAPI(relay)

        async def handler(data: dict) -> None:
            pass

        api.on_raw("test_event", handler)
        api.off_raw("test_event", handler)
        assert handler not in relay._raw_handlers.get("test_event", [])


class TestBotState:
    """Tests for Bot state without a real connection."""

    def test_not_connected_raises(self) -> None:
        bot = Bot(host="localhost")
        with pytest.raises(MinethonConnectionError):
            _ = bot.position

    def test_not_connected_health_raises(self) -> None:
        bot = Bot(host="localhost")
        with pytest.raises(MinethonConnectionError):
            _ = bot.health

    def test_not_connected_food_raises(self) -> None:
        bot = Bot(host="localhost")
        with pytest.raises(MinethonConnectionError):
            _ = bot.food

    def test_not_connected_game_mode_raises(self) -> None:
        bot = Bot(host="localhost")
        with pytest.raises(MinethonConnectionError):
            _ = bot.game_mode

    def test_not_connected_players_raises(self) -> None:
        bot = Bot(host="localhost")
        with pytest.raises(MinethonConnectionError):
            _ = bot.players

    def test_is_connected_default(self) -> None:
        bot = Bot(host="localhost")
        assert bot.is_connected is False

    def test_username_from_config(self) -> None:
        bot = Bot(host="localhost", username="TestBot")
        assert bot.username == "TestBot"

    def test_not_spawned_position_raises(self) -> None:
        """Even if we force _connected, position requires spawned."""
        bot = Bot(host="localhost")
        bot._connected = True
        bot._controller = object()  # type: ignore[assignment]
        with pytest.raises(NotSpawnedError):
            _ = bot.position

    def test_navigation_not_connected_raises(self) -> None:
        bot = Bot(host="localhost")
        with pytest.raises(MinethonConnectionError):
            _ = bot.navigation

    def test_not_spawned_is_alive_raises(self) -> None:
        bot = Bot(host="localhost")
        bot._connected = True
        bot._controller = object()  # type: ignore[assignment]
        with pytest.raises(NotSpawnedError):
            _ = bot.is_alive

    @pytest.mark.asyncio
    async def test_chat_not_connected_raises(self) -> None:
        bot = Bot(host="localhost")
        with pytest.raises(MinethonConnectionError):
            await bot.chat("hello")

    @pytest.mark.asyncio
    async def test_whisper_not_connected_raises(self) -> None:
        bot = Bot(host="localhost")
        with pytest.raises(MinethonConnectionError):
            await bot.whisper("Steve", "hello")

    @pytest.mark.asyncio
    async def test_dig_not_connected_raises(self) -> None:
        from minethon.models.block import Block

        bot = Bot(host="localhost")
        block = Block("stone", "Stone", Vec3(0, 0, 0), 1.5, True, False, "block")
        with pytest.raises(MinethonConnectionError):
            await bot.dig(block)

    @pytest.mark.asyncio
    async def test_goto_not_spawned_raises(self) -> None:
        bot = Bot(host="localhost")
        bot._connected = True
        bot._controller = object()  # type: ignore[assignment]
        with pytest.raises(NotSpawnedError):
            await bot.goto(0, 64, 0)

    @pytest.mark.asyncio
    async def test_stop_not_connected_raises(self) -> None:
        bot = Bot(host="localhost")
        with pytest.raises(MinethonConnectionError):
            await bot.stop()

    @pytest.mark.asyncio
    async def test_disconnect_when_not_connected(self) -> None:
        bot = Bot(host="localhost")
        # Should not raise
        await bot.disconnect()
        assert bot.is_connected is False


class TestBotEndEvent:
    """Tests for EndEvent handling on the Bot."""

    @pytest.mark.asyncio
    async def test_end_event_flips_connected(self) -> None:
        """Simulate an EndEvent dispatch and check Bot state."""
        bot = Bot(host="localhost")
        loop = asyncio.get_running_loop()
        bot._relay.set_loop(loop)
        bot._connected = True
        bot._spawned = True

        # Register the internal handler like connect() does
        async def _on_end(_event: EndEvent) -> None:
            bot._connected = False
            bot._spawned = False

        bot._relay.add_handler(EndEvent, _on_end)  # type: ignore[arg-type]

        # Dispatch EndEvent
        bot._relay._dispatch(EndEvent, EndEvent(reason="disconnect"))
        await asyncio.sleep(0.01)

        assert bot.is_connected is False
        assert bot._spawned is False


class TestBotAsyncOperations:
    """Tests for the event-driven async action flow (dig, place, etc.)."""

    @pytest.mark.asyncio
    async def test_dig_done_success_flow(self) -> None:
        """Simulate dig completing via DigDoneEvent."""
        relay = EventRelay()
        relay.set_loop(asyncio.get_running_loop())

        async def post() -> None:
            await asyncio.sleep(0.01)
            relay._dispatch(DigDoneEvent, DigDoneEvent(error=None))

        asyncio.create_task(post())
        event = await relay.wait_for(DigDoneEvent, timeout=1.0)
        assert event.error is None

    @pytest.mark.asyncio
    async def test_dig_done_error_flow(self) -> None:
        """Simulate dig failing via DigDoneEvent with error."""
        relay = EventRelay()
        relay.set_loop(asyncio.get_running_loop())

        async def post() -> None:
            await asyncio.sleep(0.01)
            relay._dispatch(
                DigDoneEvent,
                DigDoneEvent(error="cannot dig this block"),
            )

        asyncio.create_task(post())
        event = await relay.wait_for(DigDoneEvent, timeout=1.0)
        assert event.error == "cannot dig this block"

    @pytest.mark.asyncio
    async def test_place_done_flow(self) -> None:
        relay = EventRelay()
        relay.set_loop(asyncio.get_running_loop())

        async def post() -> None:
            await asyncio.sleep(0.01)
            relay._dispatch(PlaceDoneEvent, PlaceDoneEvent())

        asyncio.create_task(post())
        event = await relay.wait_for(PlaceDoneEvent, timeout=1.0)
        assert event.error is None

    @pytest.mark.asyncio
    async def test_equip_done_flow(self) -> None:
        relay = EventRelay()
        relay.set_loop(asyncio.get_running_loop())

        async def post() -> None:
            await asyncio.sleep(0.01)
            relay._dispatch(EquipDoneEvent, EquipDoneEvent())

        asyncio.create_task(post())
        event = await relay.wait_for(EquipDoneEvent, timeout=1.0)
        assert event.error is None

    @pytest.mark.asyncio
    async def test_look_at_done_flow(self) -> None:
        relay = EventRelay()
        relay.set_loop(asyncio.get_running_loop())

        async def post() -> None:
            await asyncio.sleep(0.01)
            relay._dispatch(LookAtDoneEvent, LookAtDoneEvent())

        asyncio.create_task(post())
        event = await relay.wait_for(LookAtDoneEvent, timeout=1.0)
        assert event.error is None


class TestBotGotoFlow:
    """Tests for goto() event racing logic."""

    @pytest.mark.asyncio
    async def test_goal_reached_wins(self) -> None:
        """GoalReachedEvent should make goto() return successfully."""
        relay = EventRelay()
        relay.set_loop(asyncio.get_running_loop())

        async def post() -> None:
            await asyncio.sleep(0.01)
            relay._dispatch(
                GoalReachedEvent,
                GoalReachedEvent(position=Vec3(10, 64, 20)),
            )

        asyncio.create_task(post())

        reached_fut = asyncio.ensure_future(
            relay.wait_for(GoalReachedEvent, timeout=1.0)
        )
        failed_fut = asyncio.ensure_future(
            relay.wait_for(GoalFailedEvent, timeout=1.0)
        )

        done, pending = await asyncio.wait(
            [reached_fut, failed_fut],
            return_when=asyncio.FIRST_COMPLETED,
        )
        for t in pending:
            t.cancel()
        await asyncio.gather(*pending, return_exceptions=True)

        result = done.pop().result()
        assert isinstance(result, GoalReachedEvent)

    @pytest.mark.asyncio
    async def test_goal_failed_raises(self) -> None:
        """GoalFailedEvent should be detected as a failure."""
        relay = EventRelay()
        relay.set_loop(asyncio.get_running_loop())

        async def post() -> None:
            await asyncio.sleep(0.01)
            relay._dispatch(GoalFailedEvent, GoalFailedEvent(reason="noPath"))

        asyncio.create_task(post())

        reached_fut = asyncio.ensure_future(
            relay.wait_for(GoalReachedEvent, timeout=1.0)
        )
        failed_fut = asyncio.ensure_future(
            relay.wait_for(GoalFailedEvent, timeout=1.0)
        )

        done, pending = await asyncio.wait(
            [reached_fut, failed_fut],
            return_when=asyncio.FIRST_COMPLETED,
        )
        for t in pending:
            t.cancel()
        await asyncio.gather(*pending, return_exceptions=True)

        result = done.pop().result()
        assert isinstance(result, GoalFailedEvent)
        assert result.reason == "noPath"
