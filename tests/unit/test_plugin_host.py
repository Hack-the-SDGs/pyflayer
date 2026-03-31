"""Unit tests for PluginHost using mocked JS runtime."""

from unittest.mock import MagicMock

import pytest

from pyflayer._bridge.plugin_host import PluginHost
from pyflayer.models.errors import BridgeError


class TestPluginHostPathfinder:
    """Pathfinder plugin loading and goal management."""

    def _make_host(self) -> tuple[PluginHost, MagicMock, MagicMock, MagicMock]:
        """Create a PluginHost with mocked runtime and js_bot."""
        runtime = MagicMock()
        js_bot = MagicMock()
        pf_mod = MagicMock()
        runtime.require.return_value = pf_mod
        host = PluginHost(runtime, js_bot)
        return host, runtime, js_bot, pf_mod

    def test_load_pathfinder(self) -> None:
        host, _rt, js_bot, pf_mod = self._make_host()
        host.load_pathfinder()
        js_bot.loadPlugin.assert_called_once_with(pf_mod.pathfinder)

    def test_load_pathfinder_idempotent(self) -> None:
        host, _rt, js_bot, _pf = self._make_host()
        host.load_pathfinder()
        host.load_pathfinder()
        js_bot.loadPlugin.assert_called_once()

    def test_setup_pathfinder_movements(self) -> None:
        host, runtime, js_bot, pf_mod = self._make_host()
        mcdata_fn = MagicMock()
        mcdata = MagicMock()
        mcdata_fn.return_value = mcdata
        movements = MagicMock()
        pf_mod.Movements.return_value = movements

        def side_effect(module: str) -> MagicMock:
            if module == "mineflayer-pathfinder":
                return pf_mod
            if module == "minecraft-data":
                return mcdata_fn
            return MagicMock()

        runtime.require.side_effect = side_effect
        js_bot.version = "1.20.4"

        host.load_pathfinder()
        host.setup_pathfinder_movements()
        pf_mod.Movements.assert_called_once_with(js_bot, mcdata)
        js_bot.pathfinder.setMovements.assert_called_once_with(movements)
        # Conservative defaults: no digging, no scaffolding
        assert movements.canDig is False
        assert movements.allow1by1towers is False
        assert movements.scafoldingBlocks == []

    def test_set_goal_near(self) -> None:
        host, _rt, js_bot, pf_mod = self._make_host()
        goal = MagicMock()
        pf_mod.goals.GoalNear.return_value = goal
        host.load_pathfinder()

        host.set_goal_near(10.0, 64.0, 20.0, 1.0)
        pf_mod.goals.GoalNear.assert_called_once_with(10.0, 64.0, 20.0, 1.0)
        js_bot.pathfinder.setGoal.assert_called_once_with(goal)

    def test_set_goal_follow(self) -> None:
        host, _rt, js_bot, pf_mod = self._make_host()
        goal = MagicMock()
        pf_mod.goals.GoalFollow.return_value = goal
        entity = MagicMock()
        host.load_pathfinder()

        host.set_goal_follow(entity, 2.0)
        pf_mod.goals.GoalFollow.assert_called_once_with(entity, 2.0)
        js_bot.pathfinder.setGoal.assert_called_once_with(goal, True)

    def test_stop_pathfinder(self) -> None:
        host, _rt, js_bot, _pf = self._make_host()
        host.load_pathfinder()
        host.stop_pathfinder()
        js_bot.pathfinder.setGoal.assert_called_once_with(None)

    def test_is_pathfinding_false(self) -> None:
        host, _rt, js_bot, _pf = self._make_host()
        js_bot.pathfinder.isMoving.return_value = False
        host.load_pathfinder()
        assert host.is_pathfinding() is False

    def test_is_pathfinding_true(self) -> None:
        host, _rt, js_bot, _pf = self._make_host()
        js_bot.pathfinder.isMoving.return_value = True
        host.load_pathfinder()
        assert host.is_pathfinding() is True

    def test_load_pathfinder_js_error_raises_bridge_error(self) -> None:
        runtime = MagicMock()
        js_bot = MagicMock()
        runtime.require.side_effect = Exception("npm install failed")
        host = PluginHost(runtime, js_bot)
        with pytest.raises(BridgeError, match="load_pathfinder"):
            host.load_pathfinder()

    def test_set_goal_near_error_raises_bridge_error(self) -> None:
        host, _rt, js_bot, _pf = self._make_host()
        host.load_pathfinder()
        js_bot.pathfinder.setGoal.side_effect = Exception("boom")
        with pytest.raises(BridgeError, match="set_goal_near"):
            host.set_goal_near(0, 0, 0, 1)

    def test_set_goal_near_not_loaded_raises_bridge_error(self) -> None:
        runtime = MagicMock()
        js_bot = MagicMock()
        host = PluginHost(runtime, js_bot)
        with pytest.raises(BridgeError, match="load_pathfinder"):
            host.set_goal_near(0, 0, 0, 1)

    def test_set_goal_follow_not_loaded_raises_bridge_error(self) -> None:
        runtime = MagicMock()
        js_bot = MagicMock()
        host = PluginHost(runtime, js_bot)
        with pytest.raises(BridgeError, match="load_pathfinder"):
            host.set_goal_follow(MagicMock(), 2.0)

    def test_set_goal_follow_error_raises_bridge_error(self) -> None:
        host, _rt, js_bot, _pf = self._make_host()
        host.load_pathfinder()
        js_bot.pathfinder.setGoal.side_effect = Exception("boom")
        with pytest.raises(BridgeError, match="set_goal_follow"):
            host.set_goal_follow(MagicMock(), 2.0)
