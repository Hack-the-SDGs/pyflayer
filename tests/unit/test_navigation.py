"""Unit tests for NavigationAPI."""

import asyncio
from unittest.mock import MagicMock

import pytest

from pyflayer._bridge.event_relay import EventRelay
from pyflayer.api.navigation import NavigationAPI
from pyflayer.models.entity import EntityKind
from pyflayer.models.errors import BridgeError, NavigationError
from pyflayer.models.events import GoalFailedEvent, GoalReachedEvent
from pyflayer.models.vec3 import Vec3


class TestNavigationGoto:
    """Tests for NavigationAPI.goto() event racing."""

    @pytest.mark.asyncio
    async def test_goto_success(self) -> None:
        relay = EventRelay()
        relay.set_loop(asyncio.get_running_loop())
        host = MagicMock()
        ctrl = MagicMock()
        nav = NavigationAPI(host, ctrl, relay)

        async def post() -> None:
            await asyncio.sleep(0.01)
            relay._dispatch(
                GoalReachedEvent,
                GoalReachedEvent(position=Vec3(10, 64, 20)),
            )

        asyncio.create_task(post())
        await nav.goto(10, 64, 20)

        host.set_goal_near.assert_called_once_with(10, 64, 20, 1.0)
        assert nav.is_navigating is False

    @pytest.mark.asyncio
    async def test_goto_custom_radius(self) -> None:
        relay = EventRelay()
        relay.set_loop(asyncio.get_running_loop())
        host = MagicMock()
        ctrl = MagicMock()
        nav = NavigationAPI(host, ctrl, relay)

        async def post() -> None:
            await asyncio.sleep(0.01)
            relay._dispatch(
                GoalReachedEvent,
                GoalReachedEvent(position=Vec3(10, 64, 20)),
            )

        asyncio.create_task(post())
        await nav.goto(10, 64, 20, radius=5.0)

        host.set_goal_near.assert_called_once_with(10, 64, 20, 5.0)

    @pytest.mark.asyncio
    async def test_goto_failure_no_path(self) -> None:
        relay = EventRelay()
        relay.set_loop(asyncio.get_running_loop())
        host = MagicMock()
        ctrl = MagicMock()
        nav = NavigationAPI(host, ctrl, relay)

        async def post() -> None:
            await asyncio.sleep(0.01)
            relay._dispatch(
                GoalFailedEvent,
                GoalFailedEvent(reason="noPath"),
            )

        asyncio.create_task(post())
        with pytest.raises(NavigationError, match="noPath"):
            await nav.goto(10, 64, 20)

        host.stop_pathfinder.assert_called()
        assert nav.is_navigating is False

    @pytest.mark.asyncio
    async def test_goto_is_navigating_true_during_navigation(self) -> None:
        relay = EventRelay()
        relay.set_loop(asyncio.get_running_loop())
        host = MagicMock()
        ctrl = MagicMock()
        nav = NavigationAPI(host, ctrl, relay)

        observed: list[bool] = []

        async def post() -> None:
            await asyncio.sleep(0.01)
            observed.append(nav.is_navigating)
            relay._dispatch(
                GoalReachedEvent,
                GoalReachedEvent(position=Vec3(10, 64, 20)),
            )

        asyncio.create_task(post())
        await nav.goto(10, 64, 20)

        assert observed == [True]
        assert nav.is_navigating is False

    @pytest.mark.asyncio
    async def test_goto_cancelled_futures_raise_navigation_error(self) -> None:
        """stop() cancelling goto futures must produce NavigationError, not CancelledError."""
        relay = EventRelay()
        relay.set_loop(asyncio.get_running_loop())
        host = MagicMock()
        ctrl = MagicMock()
        nav = NavigationAPI(host, ctrl, relay)

        async def cancel_soon() -> None:
            await asyncio.sleep(0.01)
            await nav.stop()

        asyncio.create_task(cancel_soon())
        with pytest.raises(NavigationError, match="stopped"):
            await nav.goto(10, 64, 20)

        assert nav.is_navigating is False

    @pytest.mark.asyncio
    async def test_goto_set_goal_near_error_cleans_up_futures(self) -> None:
        relay = EventRelay()
        relay.set_loop(asyncio.get_running_loop())
        host = MagicMock()
        host.set_goal_near.side_effect = BridgeError("pathfinder not ready")
        ctrl = MagicMock()
        nav = NavigationAPI(host, ctrl, relay)

        with pytest.raises(BridgeError):
            await nav.goto(10, 64, 20)

        assert nav.is_navigating is False
        assert len(relay._waiters.get(GoalReachedEvent, [])) == 0
        assert len(relay._waiters.get(GoalFailedEvent, [])) == 0


class TestNavigationFollow:
    """Tests for NavigationAPI.follow()."""

    @pytest.mark.asyncio
    async def test_follow_success(self) -> None:
        relay = EventRelay()
        relay.set_loop(asyncio.get_running_loop())
        host = MagicMock()
        ctrl = MagicMock()
        js_entity = MagicMock()
        ctrl.get_entity_by_filter.return_value = js_entity
        nav = NavigationAPI(host, ctrl, relay)

        await nav.follow("Steve", distance=3.0)

        ctrl.get_entity_by_filter.assert_called_once_with(
            "Steve", EntityKind.PLAYER, 1e6
        )
        host.set_goal_follow.assert_called_once_with(js_entity, 3.0)
        assert nav.is_navigating is True

    @pytest.mark.asyncio
    async def test_follow_default_distance(self) -> None:
        relay = EventRelay()
        relay.set_loop(asyncio.get_running_loop())
        host = MagicMock()
        ctrl = MagicMock()
        ctrl.get_entity_by_filter.return_value = MagicMock()
        nav = NavigationAPI(host, ctrl, relay)

        await nav.follow("Steve")

        host.set_goal_follow.assert_called_once()
        _, args, _ = host.set_goal_follow.mock_calls[0]
        assert args[1] == 2.0

    @pytest.mark.asyncio
    async def test_follow_player_not_found(self) -> None:
        relay = EventRelay()
        relay.set_loop(asyncio.get_running_loop())
        host = MagicMock()
        ctrl = MagicMock()
        ctrl.get_entity_by_filter.return_value = None
        nav = NavigationAPI(host, ctrl, relay)

        with pytest.raises(NavigationError, match="not found"):
            await nav.follow("Unknown")

        assert nav.is_navigating is False

    @pytest.mark.asyncio
    async def test_follow_stops_previous_navigation(self) -> None:
        relay = EventRelay()
        relay.set_loop(asyncio.get_running_loop())
        host = MagicMock()
        ctrl = MagicMock()
        ctrl.get_entity_by_filter.return_value = MagicMock()
        nav = NavigationAPI(host, ctrl, relay)

        await nav.follow("Alice")
        assert nav.is_navigating is True

        await nav.follow("Bob")
        # stop_pathfinder called once for stopping Alice
        host.stop_pathfinder.assert_called_once()
        assert nav.is_navigating is True


class TestNavigationStop:
    """Tests for NavigationAPI.stop() and is_navigating."""

    @pytest.mark.asyncio
    async def test_stop_after_follow(self) -> None:
        relay = EventRelay()
        relay.set_loop(asyncio.get_running_loop())
        host = MagicMock()
        ctrl = MagicMock()
        ctrl.get_entity_by_filter.return_value = MagicMock()
        nav = NavigationAPI(host, ctrl, relay)

        await nav.follow("Steve")
        assert nav.is_navigating is True

        await nav.stop()
        host.stop_pathfinder.assert_called_once()
        assert nav.is_navigating is False

    def test_is_navigating_default_false(self) -> None:
        relay = EventRelay()
        host = MagicMock()
        ctrl = MagicMock()
        nav = NavigationAPI(host, ctrl, relay)
        assert nav.is_navigating is False

    @pytest.mark.asyncio
    async def test_stop_when_not_navigating(self) -> None:
        relay = EventRelay()
        relay.set_loop(asyncio.get_running_loop())
        host = MagicMock()
        ctrl = MagicMock()
        nav = NavigationAPI(host, ctrl, relay)

        await nav.stop()  # should not raise
        host.stop_pathfinder.assert_called_once()
        assert nav.is_navigating is False
