"""Path-planning and movement control."""

import asyncio

from pyflayer._bridge.event_relay import EventRelay
from pyflayer._bridge.js_bot import JSBotController
from pyflayer._bridge.plugin_host import PluginHost
from pyflayer.models.entity import EntityKind
from pyflayer.models.errors import NavigationError
from pyflayer.models.events import GoalFailedEvent, GoalReachedEvent


class NavigationAPI:
    """Path-planning and movement control.

    Uses ``mineflayer-pathfinder`` for obstacle-aware A* navigation.

    Example::

        await bot.navigation.goto(100, 64, 200)
        await bot.navigation.follow("Steve", distance=3.0)
        await bot.navigation.stop()
    """

    def __init__(
        self,
        plugin_host: PluginHost,
        controller: JSBotController,
        relay: EventRelay,
    ) -> None:
        self._host = plugin_host
        self._ctrl = controller
        self._relay = relay
        self._navigating = False

    async def goto(
        self, x: float, y: float, z: float, *, radius: float = 1.0
    ) -> None:
        """Move to a position using A* pathfinding.

        Resolves when the bot arrives within *radius* of the target.

        Args:
            x: Target X coordinate.
            y: Target Y coordinate.
            z: Target Z coordinate.
            radius: Acceptable distance from the target.

        Raises:
            NavigationError: If the pathfinder cannot reach the goal
                or navigation times out.
        """
        if self._navigating:
            await self.stop()

        self._navigating = True
        reached_fut = asyncio.ensure_future(
            self._relay.wait_for(GoalReachedEvent, timeout=300.0)
        )
        failed_fut = asyncio.ensure_future(
            self._relay.wait_for(GoalFailedEvent, timeout=300.0)
        )
        try:
            self._host.set_goal_near(x, y, z, radius)

            done, pending = await asyncio.wait(
                [reached_fut, failed_fut],
                return_when=asyncio.FIRST_COMPLETED,
            )

            for task in pending:
                task.cancel()
            await asyncio.gather(*pending, return_exceptions=True)

            for task in done:
                exc = task.exception()
                if exc is not None:
                    self._host.stop_pathfinder()
                    if isinstance(exc, asyncio.TimeoutError):
                        raise NavigationError(
                            "Navigation timed out"
                        ) from exc
                    raise NavigationError(
                        f"Navigation failed: {exc}"
                    ) from exc

                result = task.result()
                if isinstance(result, GoalReachedEvent):
                    return
                if isinstance(result, GoalFailedEvent):
                    self._host.stop_pathfinder()
                    raise NavigationError(
                        f"Navigation failed: {result.reason}"
                    )
        except BaseException:
            reached_fut.cancel()
            failed_fut.cancel()
            await asyncio.gather(
                reached_fut, failed_fut, return_exceptions=True
            )
            raise
        finally:
            self._navigating = False

    async def follow(
        self, username: str, *, distance: float = 2.0
    ) -> None:
        """Start following a player continuously.

        Returns immediately once following begins.  The bot keeps
        following until :meth:`stop` is called.

        Args:
            username: Name of the player to follow.
            distance: Desired follow distance in blocks.

        Raises:
            NavigationError: If the player entity is not found.
        """
        if self._navigating:
            await self.stop()

        js_entity = self._ctrl.get_entity_by_filter(
            username, EntityKind.PLAYER, 1e6
        )
        if js_entity is None:
            raise NavigationError(f"Player '{username}' not found")
        self._host.set_goal_follow(js_entity, distance)
        self._navigating = True

    async def stop(self) -> None:
        """Stop current navigation."""
        self._host.stop_pathfinder()
        self._navigating = False

    @property
    def is_navigating(self) -> bool:
        """Whether the bot is currently navigating."""
        return self._navigating
