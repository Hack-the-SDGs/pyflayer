"""JS plugin loading and management."""

from typing import Any

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
            raise BridgeError(f"load_pathfinder failed: {exc}") from exc

    def setup_pathfinder_movements(self) -> None:
        """Configure default Movements.  Call after bot has spawned.

        The defaults are conservative: digging and scaffolding are
        disabled so the bot only walks/jumps around obstacles.  Users
        who need dig-through or pillar-up behaviour can reconfigure
        via ``bot.raw``.
        """
        try:
            pf_mod = self._runtime.require("mineflayer-pathfinder")
            mcdata = self._runtime.require("minecraft-data")(
                self._js_bot.version
            )
            movements = pf_mod.Movements(self._js_bot, mcdata)
            movements.canDig = False
            movements.allow1by1towers = False
            movements.scafoldingBlocks = []
            self._js_bot.pathfinder.setMovements(movements)
        except Exception as exc:
            raise BridgeError(
                f"setup_pathfinder_movements failed: {exc}"
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
            raise BridgeError(f"set_goal_near failed: {exc}") from exc

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
            raise BridgeError(f"set_goal_follow failed: {exc}") from exc

    def stop_pathfinder(self) -> None:
        """Clear the current pathfinder goal."""
        try:
            self._js_bot.pathfinder.setGoal(None)
        except Exception as exc:
            raise BridgeError(f"stop_pathfinder failed: {exc}") from exc

    def is_pathfinding(self) -> bool:
        """Whether the pathfinder is actively moving along a path."""
        try:
            return bool(self._js_bot.pathfinder.isMoving())
        except (AttributeError, TypeError):
            return False
