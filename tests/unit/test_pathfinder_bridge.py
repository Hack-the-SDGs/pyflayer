"""Unit tests for PathfinderBridge using mocked JS runtime."""

from unittest.mock import MagicMock

import pytest

from minethon._bridge.plugins.pathfinder import PathfinderBridge
from minethon.models.errors import BridgeError


class TestPathfinderBridgeLoad:
    """PathfinderBridge loading and idempotency."""

    def _make_bridge(self) -> tuple[PathfinderBridge, MagicMock, MagicMock, MagicMock]:
        runtime = MagicMock()
        js_bot = MagicMock()
        relay = MagicMock()
        pf_mod = MagicMock()
        runtime.require.return_value = pf_mod
        bridge = PathfinderBridge(runtime, js_bot, relay)
        return bridge, runtime, js_bot, pf_mod

    def test_load(self) -> None:
        bridge, _rt, js_bot, pf_mod = self._make_bridge()
        bridge.load()
        js_bot.loadPlugin.assert_called_once_with(pf_mod.pathfinder)
        assert bridge.is_loaded is True

    def test_load_idempotent(self) -> None:
        bridge, _rt, js_bot, _pf = self._make_bridge()
        bridge.load()
        bridge.load()
        js_bot.loadPlugin.assert_called_once()

    def test_load_js_error_raises_bridge_error(self) -> None:
        runtime = MagicMock()
        js_bot = MagicMock()
        relay = MagicMock()
        runtime.require.side_effect = Exception("npm install failed")
        bridge = PathfinderBridge(runtime, js_bot, relay)
        with pytest.raises(BridgeError, match="load pathfinder"):
            bridge.load()
        assert bridge.is_loaded is False


class TestPathfinderBridgeMovements:
    """setup_movements after spawn."""

    def _loaded_bridge(self) -> tuple[PathfinderBridge, MagicMock, MagicMock, MagicMock]:
        runtime = MagicMock()
        js_bot = MagicMock()
        relay = MagicMock()
        pf_mod = MagicMock()
        runtime.require.return_value = pf_mod
        bridge = PathfinderBridge(runtime, js_bot, relay)
        bridge.load()
        return bridge, runtime, js_bot, pf_mod

    def test_setup_movements(self) -> None:
        bridge, _rt, js_bot, pf_mod = self._loaded_bridge()
        movements = MagicMock()
        pf_mod.Movements.return_value = movements
        bridge.setup_movements()
        pf_mod.Movements.assert_called_once_with(js_bot)
        js_bot.pathfinder.setMovements.assert_called_once_with(movements)


class TestPathfinderBridgeGoals:
    """Goal setting and stopping."""

    def _loaded_bridge(self) -> tuple[PathfinderBridge, MagicMock, MagicMock, MagicMock]:
        runtime = MagicMock()
        js_bot = MagicMock()
        relay = MagicMock()
        pf_mod = MagicMock()
        runtime.require.return_value = pf_mod
        bridge = PathfinderBridge(runtime, js_bot, relay)
        bridge.load()
        return bridge, runtime, js_bot, pf_mod

    def test_set_goal_near(self) -> None:
        bridge, _rt, js_bot, pf_mod = self._loaded_bridge()
        goal = MagicMock()
        pf_mod.goals.GoalNear.return_value = goal
        bridge.set_goal_near(10.0, 64.0, 20.0, 1.0)
        pf_mod.goals.GoalNear.assert_called_once_with(10.0, 64.0, 20.0, 1.0)
        js_bot.pathfinder.setGoal.assert_called_once_with(goal)

    def test_set_goal_near_not_loaded_raises(self) -> None:
        runtime = MagicMock()
        js_bot = MagicMock()
        relay = MagicMock()
        bridge = PathfinderBridge(runtime, js_bot, relay)
        with pytest.raises(BridgeError, match="pathfinder has not been loaded"):
            bridge.set_goal_near(0, 0, 0, 1)

    def test_set_goal_near_error_raises(self) -> None:
        bridge, _rt, js_bot, _pf = self._loaded_bridge()
        js_bot.pathfinder.setGoal.side_effect = Exception("boom")
        with pytest.raises(BridgeError, match="set_goal_near"):
            bridge.set_goal_near(0, 0, 0, 1)

    def test_set_goal_follow(self) -> None:
        bridge, _rt, js_bot, pf_mod = self._loaded_bridge()
        goal = MagicMock()
        pf_mod.goals.GoalFollow.return_value = goal
        entity = MagicMock()
        bridge.set_goal_follow(entity, 2.0)
        pf_mod.goals.GoalFollow.assert_called_once_with(entity, 2.0)
        js_bot.pathfinder.setGoal.assert_called_once_with(goal, True)

    def test_set_goal_follow_not_loaded_raises(self) -> None:
        runtime = MagicMock()
        js_bot = MagicMock()
        relay = MagicMock()
        bridge = PathfinderBridge(runtime, js_bot, relay)
        with pytest.raises(BridgeError, match="pathfinder has not been loaded"):
            bridge.set_goal_follow(MagicMock(), 2.0)

    def test_set_goal_follow_error_raises(self) -> None:
        bridge, _rt, js_bot, _pf = self._loaded_bridge()
        js_bot.pathfinder.setGoal.side_effect = Exception("boom")
        with pytest.raises(BridgeError, match="set_goal_follow"):
            bridge.set_goal_follow(MagicMock(), 2.0)


class TestPathfinderBridgeStop:
    """Stopping and is_pathfinding."""

    def _loaded_bridge(self) -> tuple[PathfinderBridge, MagicMock]:
        runtime = MagicMock()
        js_bot = MagicMock()
        relay = MagicMock()
        pf_mod = MagicMock()
        runtime.require.return_value = pf_mod
        bridge = PathfinderBridge(runtime, js_bot, relay)
        bridge.load()
        return bridge, js_bot

    def test_stop(self) -> None:
        bridge, js_bot = self._loaded_bridge()
        bridge.stop()
        js_bot.pathfinder.setGoal.assert_called_once_with(None)

    def test_stop_not_loaded_is_noop(self) -> None:
        runtime = MagicMock()
        js_bot = MagicMock()
        relay = MagicMock()
        bridge = PathfinderBridge(runtime, js_bot, relay)
        bridge.stop()
        js_bot.pathfinder.setGoal.assert_not_called()

    def test_stop_swallows_attribute_error(self) -> None:
        bridge, js_bot = self._loaded_bridge()
        js_bot.pathfinder.setGoal.side_effect = AttributeError("gone")
        bridge.stop()  # should not raise

    def test_is_pathfinding_false(self) -> None:
        bridge, js_bot = self._loaded_bridge()
        js_bot.pathfinder.isMoving.return_value = False
        assert bridge.is_pathfinding() is False

    def test_is_pathfinding_true(self) -> None:
        bridge, js_bot = self._loaded_bridge()
        js_bot.pathfinder.isMoving.return_value = True
        assert bridge.is_pathfinding() is True

    def test_teardown_calls_stop(self) -> None:
        bridge, js_bot = self._loaded_bridge()
        bridge.teardown()
        js_bot.pathfinder.setGoal.assert_called_once_with(None)
