"""Comprehensive tests for EventRelay."""

import asyncio
from types import SimpleNamespace

import pytest

from minethon._bridge._events import (
    DigDoneEvent,
    EquipDoneEvent,
    LookAtDoneEvent,
    PlaceDoneEvent,
)
from minethon._bridge.event_relay import EventRelay
from minethon.models.events import (
    ChatEvent,
    EntityMovedEvent,
    EntityUpdateEvent,
    GoalFailedEvent,
    GoalReachedEvent,
    HeldItemChangedEvent,
    MessageStrEvent,
    MoveEvent,
    PhysicsTickEvent,
    PlayerJoinedEvent,
    ScoreUpdatedEvent,
    SoundEffectHeardEvent,
    SpawnEvent,
    TeamCreatedEvent,
)
from minethon.models.vec3 import Vec3


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
            relay._dispatch(DigDoneEvent, DigDoneEvent(error=None))

        asyncio.create_task(post())
        event = await relay.wait_for(DigDoneEvent, timeout=1.0)
        assert event.error is None

    @pytest.mark.asyncio
    async def test_dig_done_error(self) -> None:
        relay = EventRelay()
        relay.set_loop(asyncio.get_running_loop())

        async def post() -> None:
            await asyncio.sleep(0.01)
            relay._dispatch(DigDoneEvent, DigDoneEvent(error="block out of reach"))

        asyncio.create_task(post())
        event = await relay.wait_for(DigDoneEvent, timeout=1.0)
        assert event.error == "block out of reach"

    @pytest.mark.asyncio
    async def test_place_done(self) -> None:
        relay = EventRelay()
        relay.set_loop(asyncio.get_running_loop())

        async def post() -> None:
            await asyncio.sleep(0.01)
            relay._dispatch(PlaceDoneEvent, PlaceDoneEvent())

        asyncio.create_task(post())
        event = await relay.wait_for(PlaceDoneEvent, timeout=1.0)
        assert event.error is None

    @pytest.mark.asyncio
    async def test_equip_done(self) -> None:
        relay = EventRelay()
        relay.set_loop(asyncio.get_running_loop())

        async def post() -> None:
            await asyncio.sleep(0.01)
            relay._dispatch(EquipDoneEvent, EquipDoneEvent())

        asyncio.create_task(post())
        event = await relay.wait_for(EquipDoneEvent, timeout=1.0)
        assert event.error is None

    @pytest.mark.asyncio
    async def test_look_at_done(self) -> None:
        relay = EventRelay()
        relay.set_loop(asyncio.get_running_loop())

        async def post() -> None:
            await asyncio.sleep(0.01)
            relay._dispatch(LookAtDoneEvent, LookAtDoneEvent())

        asyncio.create_task(post())
        event = await relay.wait_for(LookAtDoneEvent, timeout=1.0)
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


class TestEventRelayMineflayerParity:
    """Payload mapping and throttled event registration."""

    @staticmethod
    def _make_item(**overrides: object) -> SimpleNamespace:
        data = {
            "name": "stick",
            "displayName": "Stick",
            "count": 2,
            "slot": 5,
            "stackSize": 64,
            "enchants": None,
            "nbt": None,
        }
        data.update(overrides)
        return SimpleNamespace(**data)

    @staticmethod
    def _make_bot() -> SimpleNamespace:
        return SimpleNamespace(
            entity=SimpleNamespace(position=SimpleNamespace(x=1.0, y=64.0, z=2.0)),
            health=20,
            food=18,
            foodSaturation=5,
            experience=SimpleNamespace(level=1, points=3, progress=0.2),
            rainState=0.0,
            thunderState=0.0,
            time=SimpleNamespace(timeOfDay=6000, age=12000),
            quickBarSlot=0,
        )

    @pytest.mark.asyncio
    async def test_messagestr_uses_sender_and_verified_positions(self) -> None:
        relay = EventRelay(
            event_throttle_ms={"move": 0, "entityMoved": 0, "physicsTick": 0}
        )
        relay.set_loop(asyncio.get_running_loop())
        js_bot = self._make_bot()
        handlers: dict[str, object] = {}

        def on_fn(_bot: object, event_name: str):
            def decorator(fn):
                handlers[event_name] = fn
                return fn

            return decorator

        relay.register_js_events(js_bot, on_fn)

        received: list[MessageStrEvent] = []

        async def handler(event: MessageStrEvent) -> None:
            received.append(event)

        relay.add_handler(MessageStrEvent, handler)
        handlers["messagestr"](js_bot, "hello", "chat", object(), "uuid-1", True)
        await asyncio.sleep(0.01)

        assert received == [
            MessageStrEvent(
                message="hello",
                position="chat",
                sender="uuid-1",
                verified=True,
            )
        ]

    @pytest.mark.asyncio
    async def test_held_item_changed_converts_item_stack(self) -> None:
        relay = EventRelay()
        relay.set_loop(asyncio.get_running_loop())
        js_bot = self._make_bot()
        handlers: dict[str, object] = {}

        def on_fn(_bot: object, event_name: str):
            def decorator(fn):
                handlers[event_name] = fn
                return fn

            return decorator

        relay.register_js_events(js_bot, on_fn)

        received: list[HeldItemChangedEvent] = []

        async def handler(event: HeldItemChangedEvent) -> None:
            received.append(event)

        relay.add_handler(HeldItemChangedEvent, handler)
        handlers["heldItemChanged"](js_bot, self._make_item())
        await asyncio.sleep(0.01)

        assert received[0].item is not None
        assert received[0].item.name == "stick"
        assert received[0].item.display_name == "Stick"

    @pytest.mark.asyncio
    async def test_held_item_changed_snapshots_before_later_proxy_mutation(
        self,
    ) -> None:
        relay = EventRelay()
        relay.set_loop(asyncio.get_running_loop())
        js_bot = self._make_bot()
        handlers: dict[str, object] = {}

        def on_fn(_bot: object, event_name: str):
            def decorator(fn):
                handlers[event_name] = fn
                return fn

            return decorator

        relay.register_js_events(js_bot, on_fn)

        received: list[HeldItemChangedEvent] = []

        async def handler(event: HeldItemChangedEvent) -> None:
            received.append(event)

        relay.add_handler(HeldItemChangedEvent, handler)
        item = self._make_item()
        handlers["heldItemChanged"](js_bot, item)
        item.name = "diamond"
        item.displayName = "Diamond"
        item.count = 99
        await asyncio.sleep(0.01)

        assert len(received) == 1
        assert received[0].item is not None
        assert received[0].item.name == "stick"
        assert received[0].item.display_name == "Stick"
        assert received[0].item.count == 2

    @pytest.mark.asyncio
    async def test_player_and_named_events_snapshot_scalar_fields(self) -> None:
        relay = EventRelay()
        relay.set_loop(asyncio.get_running_loop())
        js_bot = self._make_bot()
        handlers: dict[str, object] = {}

        def on_fn(_bot: object, event_name: str):
            def decorator(fn):
                handlers[event_name] = fn
                return fn

            return decorator

        relay.register_js_events(js_bot, on_fn)

        players: list[PlayerJoinedEvent] = []
        teams: list[TeamCreatedEvent] = []

        async def player_handler(event: PlayerJoinedEvent) -> None:
            players.append(event)

        async def team_handler(event: TeamCreatedEvent) -> None:
            teams.append(event)

        relay.add_handler(PlayerJoinedEvent, player_handler)
        relay.add_handler(TeamCreatedEvent, team_handler)

        player = SimpleNamespace(username="Alex")
        team = SimpleNamespace(name="builders")
        handlers["playerJoined"](js_bot, player)
        handlers["teamCreated"](js_bot, team)
        player.username = "Steve"
        team.name = "raiders"
        await asyncio.sleep(0.01)

        assert players == [
            PlayerJoinedEvent(
                username="Alex",
                uuid="",
                ping=0,
                game_mode=0,
                display_name=None,
            )
        ]
        assert teams == [TeamCreatedEvent(name="builders")]

    @pytest.mark.asyncio
    async def test_sound_and_score_payloads_match_docs(self) -> None:
        relay = EventRelay()
        relay.set_loop(asyncio.get_running_loop())
        js_bot = self._make_bot()
        handlers: dict[str, object] = {}

        def on_fn(_bot: object, event_name: str):
            def decorator(fn):
                handlers[event_name] = fn
                return fn

            return decorator

        relay.register_js_events(js_bot, on_fn)

        sounds: list[SoundEffectHeardEvent] = []
        scores: list[ScoreUpdatedEvent] = []

        async def sound_handler(event: SoundEffectHeardEvent) -> None:
            sounds.append(event)

        async def score_handler(event: ScoreUpdatedEvent) -> None:
            scores.append(event)

        relay.add_handler(SoundEffectHeardEvent, sound_handler)
        relay.add_handler(ScoreUpdatedEvent, score_handler)

        position = SimpleNamespace(x=4.0, y=70.0, z=-3.0)
        handlers["soundEffectHeard"](js_bot, "entity.arrow.hit", position, 1.5, 63)
        handlers["scoreUpdated"](
            js_bot,
            SimpleNamespace(name="sidebar"),
            SimpleNamespace(name="Alex", value=12),
        )
        await asyncio.sleep(0.01)

        assert sounds == [
            SoundEffectHeardEvent(
                sound_name="entity.arrow.hit",
                position=Vec3(4.0, 70.0, -3.0),
                volume=1.5,
                pitch=63.0,
            )
        ]
        assert scores == [
            ScoreUpdatedEvent(
                scoreboard_name="sidebar",
                item_name="Alex",
                value=12,
            )
        ]

    @pytest.mark.asyncio
    async def test_high_frequency_events_dispatch_typed_events(self) -> None:
        relay = EventRelay(
            event_throttle_ms={"move": 0, "entityMoved": 0, "physicsTick": 0}
        )
        relay.set_loop(asyncio.get_running_loop())
        js_bot = self._make_bot()
        handlers: dict[str, object] = {}

        def on_fn(_bot: object, event_name: str):
            def decorator(fn):
                handlers[event_name] = fn
                return fn

            return decorator

        relay.register_js_events(js_bot, on_fn)

        moves: list[MoveEvent] = []
        entity_moves: list[EntityMovedEvent] = []
        ticks: list[PhysicsTickEvent] = []
        raw_entity_moves: list[dict] = []

        async def move_handler(event: MoveEvent) -> None:
            moves.append(event)

        async def entity_move_handler(event: EntityMovedEvent) -> None:
            entity_moves.append(event)

        async def tick_handler(event: PhysicsTickEvent) -> None:
            ticks.append(event)

        async def raw_entity_move_handler(data: dict) -> None:
            raw_entity_moves.append(data)

        relay.add_handler(MoveEvent, move_handler)
        relay.add_handler(EntityMovedEvent, entity_move_handler)
        relay.add_handler(PhysicsTickEvent, tick_handler)
        relay.add_raw_handler("entityMoved", raw_entity_move_handler)

        moving_entity = SimpleNamespace(
            id=99, position=SimpleNamespace(x=9.0, y=65.0, z=7.0)
        )
        handlers["move"](js_bot)
        handlers["entityMoved"](js_bot, moving_entity)
        handlers["physicsTick"](js_bot)
        await asyncio.sleep(0.01)

        assert moves == [MoveEvent(position=Vec3(1.0, 64.0, 2.0))]
        assert entity_moves == [
            EntityMovedEvent(entity_id=99, position=Vec3(9.0, 65.0, 7.0))
        ]
        assert len(ticks) == 1
        assert raw_entity_moves == [{"args": [moving_entity]}]

    @pytest.mark.asyncio
    async def test_entity_update_snapshots_before_later_proxy_mutation(self) -> None:
        relay = EventRelay(
            event_throttle_ms={
                "move": 0,
                "entityMoved": 0,
                "entityUpdate": 0,
                "physicsTick": 0,
            }
        )
        relay.set_loop(asyncio.get_running_loop())
        js_bot = self._make_bot()
        handlers: dict[str, object] = {}

        def on_fn(_bot: object, event_name: str):
            def decorator(fn):
                handlers[event_name] = fn
                return fn

            return decorator

        relay.register_js_events(js_bot, on_fn)

        updates: list[EntityUpdateEvent] = []

        async def handler(event: EntityUpdateEvent) -> None:
            updates.append(event)

        relay.add_handler(EntityUpdateEvent, handler)
        entity = SimpleNamespace(
            id=7,
            position=SimpleNamespace(x=1.0, y=65.0, z=2.0),
            velocity=SimpleNamespace(x=0.1, y=0.0, z=0.2),
            health=12.0,
            username="Alex",
            name="player",
            metadata=None,
            type="player",
        )

        handlers["entityUpdate"](js_bot, entity)
        entity.position.x = 99.0
        entity.velocity.z = 9.0
        entity.health = 1.0
        await asyncio.sleep(0.01)

        assert len(updates) == 1
        assert updates[0].entity is not None
        assert updates[0].entity.position == Vec3(1.0, 65.0, 2.0)
        assert updates[0].entity.velocity == Vec3(0.1, 0.0, 0.2)
        assert updates[0].entity.health == 12.0
