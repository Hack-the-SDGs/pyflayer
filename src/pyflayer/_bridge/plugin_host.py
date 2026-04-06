"""JS plugin loading and management."""

from typing import Any

from pyflayer._bridge._util import extract_js_stack
from pyflayer._bridge.runtime import BridgeRuntime
from pyflayer.models.errors import BridgeError


class PluginHost:
    """Manages loading and configuring mineflayer JS plugins.

    This is a bridge-layer component.  Public APIs should not
    expose this class or its return values directly.
    """

    def __init__(self, runtime: BridgeRuntime, js_bot: Any) -> None:
        self._runtime = runtime
        self._js_bot = js_bot
        # -- pathfinder state --
        self._pf_goals: Any = None
        self._pf_loaded = False

    # -- Pathfinder --------------------------------------------------------

    def load_pathfinder(self) -> None:
        """Load the mineflayer-pathfinder plugin.  Idempotent."""
        if self._pf_loaded:
            return
        try:
            pf_mod = self._runtime.require("mineflayer-pathfinder")
            self._js_bot.loadPlugin(pf_mod.pathfinder)
            self._pf_goals = pf_mod.goals
            self._pf_loaded = True
        except Exception as exc:
            raise BridgeError(f"load_pathfinder failed: {exc}", js_stack=extract_js_stack(exc)) from exc

    def setup_pathfinder_movements(self) -> None:
        """Configure default Movements.  Call after bot has spawned.

        Uses the pathfinder's built-in defaults which enable digging,
        scaffolding, parkour and sprinting.  The ``Movements``
        constructor reads ``bot.registry`` internally so no separate
        ``minecraft-data`` import is needed.
        """
        try:
            pf_mod = self._runtime.require("mineflayer-pathfinder")
            movements = pf_mod.Movements(self._js_bot)
            self._js_bot.pathfinder.setMovements(movements)
        except Exception as exc:
            raise BridgeError(
                f"setup_pathfinder_movements failed: {exc}",
                js_stack=extract_js_stack(exc),
            ) from exc

    def set_goal_near(
        self, x: float, y: float, z: float, radius: float
    ) -> None:
        """Set a GoalNear target.  Pathfinder starts navigating immediately."""
        if not self._pf_loaded:
            raise BridgeError(
                "set_goal_near failed: load_pathfinder() has not been called"
            )
        try:
            goal = self._pf_goals.GoalNear(x, y, z, radius)
            self._js_bot.pathfinder.setGoal(goal)
        except Exception as exc:
            raise BridgeError(f"set_goal_near failed: {exc}", js_stack=extract_js_stack(exc)) from exc

    def set_goal_follow(self, js_entity: Any, distance: float) -> None:
        """Set a GoalFollow target.  Pathfinder follows continuously.

        Args:
            js_entity: Raw JS entity proxy to follow.
            distance: Desired follow distance in blocks.
        """
        if not self._pf_loaded:
            raise BridgeError(
                "set_goal_follow failed: load_pathfinder() has not been called"
            )
        try:
            goal = self._pf_goals.GoalFollow(js_entity, distance)
            self._js_bot.pathfinder.setGoal(goal, True)
        except Exception as exc:
            raise BridgeError(f"set_goal_follow failed: {exc}", js_stack=extract_js_stack(exc)) from exc

    def stop_pathfinder(self) -> None:
        """Clear the current pathfinder goal.  Best-effort cleanup.

        Silently returns when the pathfinder plugin is not loaded or the
        bot is mid-shutdown, so that cleanup code never masks the
        original error that triggered the stop.
        """
        if not self._pf_loaded:
            return
        try:
            pathfinder = getattr(self._js_bot, "pathfinder", None)
            if pathfinder is None:
                return
            pathfinder.setGoal(None)
        except (AttributeError, TypeError):
            return

    def is_pathfinding(self) -> bool:
        """Whether the pathfinder is actively moving along a path."""
        try:
            return bool(self._js_bot.pathfinder.isMoving())
        except (AttributeError, TypeError):
            return False

    def raw_plugin(self, name: str) -> Any:
        """Load and return a raw JS plugin module.

        This is an escape hatch for plugins not yet wrapped by pyflayer.

        Args:
            name: npm package name of the plugin.

        Returns:
            The raw JS module proxy.

        Warning:
            The returned object is a JSPyBridge proxy with no type
            safety or stability guarantees.
        """
        try:
            return self._runtime.require(name)
        except Exception as exc:
            raise BridgeError(f"raw_plugin '{name}' failed: {exc}", js_stack=extract_js_stack(exc)) from exc
