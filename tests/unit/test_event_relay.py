"""Comprehensive tests for EventRelay."""

import asyncio

import pytest

from pyflayer._bridge._events import (
    _DigDoneEvent,
    _EquipDoneEvent,
    _LookAtDoneEvent,
    _PlaceDoneEvent,
)
from pyflayer._bridge.event_relay import EventRelay
from pyflayer.models.events import (
    ChatEvent,
    GoalFailedEvent,
    GoalReachedEvent,
    SpawnEvent,
)
from pyflayer.models.vec3 import Vec3


class TestEventRelayBasic:
    """Core dispatch mechanics."""

    @pytest.mark.asyncio
    async def test_wait_for_resolves(self) -> None:
        relay = EventRelay()
        relay.set_loop(asyncio.get_running_loop())

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
        relay.set_loop(asyncio.get_running_loop())

        with pytest.raises(asyncio.TimeoutError):
            await relay.wait_for(SpawnEvent, timeout=0.01)

    @pytest.mark.asyncio
    async def test_wait_for_cleans_up_on_timeout(self) -> None:
        relay = EventRelay()
        relay.set_loop(asyncio.get_running_loop())

        with pytest.raises(asyncio.TimeoutError):
            await relay.wait_for(SpawnEvent, timeout=0.01)

        # Waiter should be removed after timeout
        assert len(relay._waiters.get(SpawnEvent, [])) == 0

    @pytest.mark.asyncio
    async def test_handler_called(self) -> None:
        relay = EventRelay()
        relay.set_loop(asyncio.get_running_loop())

        received: list[ChatEvent] = []

        async def handler(event: ChatEvent) -> None:
            received.append(event)

        relay.add_handler(ChatEvent, handler)
        event = ChatEvent(sender="Steve", message="hi", timestamp=0.0)
        relay._dispatch(ChatEvent, event)

        await asyncio.sleep(0.01)
        assert len(received) == 1
        assert received[0].sender == "Steve"

    @pytest.mark.asyncio
    async def test_multiple_handlers(self) -> None:
        relay = EventRelay()
        relay.set_loop(asyncio.get_running_loop())

        calls: list[str] = []

        async def handler_a(event: SpawnEvent) -> None:
            calls.append("a")

        async def handler_b(event: SpawnEvent) -> None:
            calls.append("b")

        relay.add_handler(SpawnEvent, handler_a)
        relay.add_handler(SpawnEvent, handler_b)
        relay._dispatch(SpawnEvent, SpawnEvent())

        await asyncio.sleep(0.01)
        assert sorted(calls) == ["a", "b"]

    @pytest.mark.asyncio
    async def test_remove_handler(self) -> None:
        relay = EventRelay()
        relay.set_loop(asyncio.get_running_loop())

        calls: list[str] = []

        async def handler(event: SpawnEvent) -> None:
            calls.append("called")

        relay.add_handler(SpawnEvent, handler)
        relay.remove_handler(SpawnEvent, handler)
        relay._dispatch(SpawnEvent, SpawnEvent())

        await asyncio.sleep(0.01)
        assert calls == []

    @pytest.mark.asyncio
    async def test_wait_for_no_loop_raises(self) -> None:
        relay = EventRelay()
        with pytest.raises(RuntimeError, match="no bound event loop"):
            await relay.wait_for(SpawnEvent, timeout=0.01)


class TestEventRelayReset:
    """Tests for reset() cleanup."""

    @pytest.mark.asyncio
    async def test_reset_clears_handler_refs(self) -> None:
        relay = EventRelay()
        relay._js_handler_refs.append("dummy_ref")
        relay.reset()
        assert relay._js_handler_refs == []

    @pytest.mark.asyncio
    async def test_reset_cancels_pending_waiters(self) -> None:
        relay = EventRelay()
        relay.set_loop(asyncio.get_running_loop())

        fut = asyncio.get_running_loop().create_future()
        relay._waiters[SpawnEvent].append(fut)

        relay.reset()
        assert fut.cancelled()
        assert len(relay._waiters) == 0

    @pytest.mark.asyncio
    async def test_reset_clears_loop(self) -> None:
        relay = EventRelay()
        relay.set_loop(asyncio.get_running_loop())
        relay.reset()
        assert relay._loop is None
        with pytest.raises(RuntimeError, match="no bound event loop"):
            await relay.wait_for(SpawnEvent, timeout=0.01)


class TestEventRelayRawEvents:
    """Tests for raw event dispatch."""

    @pytest.mark.asyncio
    async def test_raw_handler_called(self) -> None:
        relay = EventRelay()
        relay.set_loop(asyncio.get_running_loop())

        received: list[dict] = []

        async def handler(data: dict) -> None:
            received.append(data)

        relay.add_raw_handler("entityMoved", handler)
        relay._dispatch_raw("entityMoved", {"args": [1, 2, 3]})

        await asyncio.sleep(0.01)
        assert len(received) == 1
        assert received[0]["args"] == [1, 2, 3]

    @pytest.mark.asyncio
    async def test_remove_raw_handler(self) -> None:
        relay = EventRelay()
        relay.set_loop(asyncio.get_running_loop())

        calls: list[str] = []

        async def handler(data: dict) -> None:
            calls.append("called")

        relay.add_raw_handler("test", handler)
        relay.remove_raw_handler("test", handler)
        relay._dispatch_raw("test", {"args": []})

        await asyncio.sleep(0.01)
        assert calls == []


class TestEventRelayInternalEvents:
    """Tests for async operation completion events."""

    @pytest.mark.asyncio
    async def test_dig_done_success(self) -> None:
        relay = EventRelay()
        relay.set_loop(asyncio.get_running_loop())

        async def post() -> None:
            await asyncio.sleep(0.01)
            relay._dispatch(_DigDoneEvent, _DigDoneEvent(error=None))

        asyncio.create_task(post())
        event = await relay.wait_for(_DigDoneEvent, timeout=1.0)
        assert event.error is None

    @pytest.mark.asyncio
    async def test_dig_done_error(self) -> None:
        relay = EventRelay()
        relay.set_loop(asyncio.get_running_loop())

        async def post() -> None:
            await asyncio.sleep(0.01)
            relay._dispatch(_DigDoneEvent, _DigDoneEvent(error="block out of reach"))

        asyncio.create_task(post())
        event = await relay.wait_for(_DigDoneEvent, timeout=1.0)
        assert event.error == "block out of reach"

    @pytest.mark.asyncio
    async def test_place_done(self) -> None:
        relay = EventRelay()
        relay.set_loop(asyncio.get_running_loop())

        async def post() -> None:
            await asyncio.sleep(0.01)
            relay._dispatch(_PlaceDoneEvent, _PlaceDoneEvent())

        asyncio.create_task(post())
        event = await relay.wait_for(_PlaceDoneEvent, timeout=1.0)
        assert event.error is None

    @pytest.mark.asyncio
    async def test_equip_done(self) -> None:
        relay = EventRelay()
        relay.set_loop(asyncio.get_running_loop())

        async def post() -> None:
            await asyncio.sleep(0.01)
            relay._dispatch(_EquipDoneEvent, _EquipDoneEvent())

        asyncio.create_task(post())
        event = await relay.wait_for(_EquipDoneEvent, timeout=1.0)
        assert event.error is None

    @pytest.mark.asyncio
    async def test_look_at_done(self) -> None:
        relay = EventRelay()
        relay.set_loop(asyncio.get_running_loop())

        async def post() -> None:
            await asyncio.sleep(0.01)
            relay._dispatch(_LookAtDoneEvent, _LookAtDoneEvent())

        asyncio.create_task(post())
        event = await relay.wait_for(_LookAtDoneEvent, timeout=1.0)
        assert event.error is None


class TestEventRelayPost:
    """Tests for thread-safe _post mechanics."""

    @pytest.mark.asyncio
    async def test_post_without_loop_is_noop(self) -> None:
        relay = EventRelay()
        # No loop set — should not raise
        relay._post(SpawnEvent, SpawnEvent())

    @pytest.mark.asyncio
    async def test_post_dispatches_to_handler(self) -> None:
        relay = EventRelay()
        loop = asyncio.get_running_loop()
        relay.set_loop(loop)

        received: list[SpawnEvent] = []

        async def handler(event: SpawnEvent) -> None:
            received.append(event)

        relay.add_handler(SpawnEvent, handler)

        # Simulate calling from another thread via call_soon_threadsafe
        relay._post(SpawnEvent, SpawnEvent())
        await asyncio.sleep(0.02)
        assert len(received) == 1

    @pytest.mark.asyncio
    async def test_post_raw_without_loop_is_noop(self) -> None:
        relay = EventRelay()
        relay._post_raw("test", {"args": []})


class TestEventRelayGoalEvents:
    """Tests for navigation goal event dispatch."""

    @pytest.mark.asyncio
    async def test_goal_reached(self) -> None:
        relay = EventRelay()
        relay.set_loop(asyncio.get_running_loop())

        async def post() -> None:
            await asyncio.sleep(0.01)
            event = GoalReachedEvent(position=Vec3(10.0, 64.0, 20.0))
            relay._dispatch(GoalReachedEvent, event)

        asyncio.create_task(post())
        result = await relay.wait_for(GoalReachedEvent, timeout=1.0)
        assert result.position == Vec3(10.0, 64.0, 20.0)

    @pytest.mark.asyncio
    async def test_goal_failed(self) -> None:
        relay = EventRelay()
        relay.set_loop(asyncio.get_running_loop())

        async def post() -> None:
            await asyncio.sleep(0.01)
            relay._dispatch(GoalFailedEvent, GoalFailedEvent(reason="noPath"))

        asyncio.create_task(post())
        result = await relay.wait_for(GoalFailedEvent, timeout=1.0)
        assert result.reason == "noPath"

    @pytest.mark.asyncio
    async def test_multiple_waiters_all_resolved(self) -> None:
        """All pending waiters for a type should be resolved by one dispatch."""
        relay = EventRelay()
        loop = asyncio.get_running_loop()
        relay.set_loop(loop)

        fut1: asyncio.Future[SpawnEvent] = loop.create_future()
        fut2: asyncio.Future[SpawnEvent] = loop.create_future()
        relay._waiters[SpawnEvent].extend([fut1, fut2])

        relay._dispatch(SpawnEvent, SpawnEvent())

        assert fut1.done()
        assert fut2.done()
