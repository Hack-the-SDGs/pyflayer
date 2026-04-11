"""Pathfinder plugin bridge.

Ref: mineflayer-pathfinder — ``pathfinder.js``, ``goals.js``
"""

from typing import Any

from minethon._bridge._util import extract_js_stack
from minethon._bridge.plugins._base import PluginBridge
from minethon.models.errors import BridgeError


class PathfinderBridge(PluginBridge):
    """Bridge for ``mineflayer-pathfinder``.

    Manages loading the pathfinder plugin, configuring default
    ``Movements``, and setting navigation goals.

    Ref: mineflayer-pathfinder/index.js — ``pathfinder``, ``goals``
    """

    NPM_NAME = "mineflayer-pathfinder"

    def __init__(self, runtime: Any, js_bot: Any, relay: Any) -> None:
        super().__init__(runtime, js_bot, relay)
        self._pf_goals: Any = None

    def _do_load(self) -> None:
        """Load the pathfinder plugin into the JS bot.

        Ref: mineflayer-pathfinder/index.js — ``exports.pathfinder``
        """
        try:
            pf_mod = self._runtime.require(self.NPM_NAME)
            self._js_bot.loadPlugin(pf_mod.pathfinder)
            self._pf_goals = pf_mod.goals
        except Exception as exc:
            self._loaded = False
            raise BridgeError(
                f"load pathfinder failed: {exc}",
                js_stack=extract_js_stack(exc),
            ) from exc

    def setup_movements(self) -> None:
        """Configure default Movements.  Call after bot has spawned.

        The ``Movements`` constructor reads ``bot.registry`` internally
        so no separate ``minecraft-data`` import is needed.

        Ref: mineflayer-pathfinder/lib/movements.js — ``Movements``
        """
        try:
            pf_mod = self._runtime.require(self.NPM_NAME)
            movements = pf_mod.Movements(self._js_bot)
            self._js_bot.pathfinder.setMovements(movements)
        except Exception as exc:
            raise BridgeError(
                f"setup_movements failed: {exc}",
                js_stack=extract_js_stack(exc),
            ) from exc

    def set_goal_near(
        self, x: float, y: float, z: float, radius: float
    ) -> None:
        """Set a GoalNear target.  Pathfinder starts navigating immediately.

        Ref: mineflayer-pathfinder/lib/goals.js — ``GoalNear``
        """
        if not self._loaded:
            raise BridgeError(
                "set_goal_near failed: pathfinder has not been loaded"
            )
        try:
            goal = self._pf_goals.GoalNear(x, y, z, radius)
            self._js_bot.pathfinder.setGoal(goal)
        except Exception as exc:
            raise BridgeError(
                f"set_goal_near failed: {exc}",
                js_stack=extract_js_stack(exc),
            ) from exc

    def set_goal_follow(self, js_entity: Any, distance: float) -> None:
        """Set a GoalFollow target.  Pathfinder follows continuously.

        Args:
            js_entity: Raw JS entity proxy to follow.
            distance: Desired follow distance in blocks.

        Ref: mineflayer-pathfinder/lib/goals.js — ``GoalFollow``
        """
        if not self._loaded:
            raise BridgeError(
                "set_goal_follow failed: pathfinder has not been loaded"
            )
        try:
            goal = self._pf_goals.GoalFollow(js_entity, distance)
            dynamic = True  # GoalFollow requires dynamic=True
            self._js_bot.pathfinder.setGoal(goal, dynamic)
        except Exception as exc:
            raise BridgeError(
                f"set_goal_follow failed: {exc}",
                js_stack=extract_js_stack(exc),
            ) from exc

    def stop(self) -> None:
        """Clear the current pathfinder goal.  Best-effort cleanup.

        Silently returns when the pathfinder plugin is not loaded or the
        bot is mid-shutdown.

        Ref: mineflayer-pathfinder/index.js — ``setGoal(null)``
        """
        if not self._loaded:
            return
        try:
            pathfinder = getattr(self._js_bot, "pathfinder", None)
            if pathfinder is None:
                return
            pathfinder.setGoal(None)
        except (AttributeError, TypeError):
            return

    def is_pathfinding(self) -> bool:
        """Whether the pathfinder is actively moving along a path.

        Ref: mineflayer-pathfinder/index.js — ``isMoving()``
        """
        try:
            return bool(self._js_bot.pathfinder.isMoving())
        except (AttributeError, TypeError):
            return False

    def teardown(self) -> None:
        """Stop pathfinder on disconnect."""
        self.stop()
