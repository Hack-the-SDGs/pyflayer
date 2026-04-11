"""Path-planning and movement control."""

import asyncio
from typing import TYPE_CHECKING

from minethon.models.entity import EntityKind
from minethon.models.errors import NavigationError
from minethon.models.events import GoalFailedEvent, GoalReachedEvent

if TYPE_CHECKING:
    from minethon._bridge.event_relay import EventRelay
    from minethon._bridge.js_bot import JSBotController
    from minethon._bridge.plugins.pathfinder import PathfinderBridge


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
        pathfinder: PathfinderBridge,
        controller: JSBotController,
        relay: EventRelay,
    ) -> None:
        self._pf = pathfinder
        self._ctrl = controller
        self._relay = relay
        self._navigating = False
        self._goto_futs: list[asyncio.Future[object]] = []

    async def goto(self, x: float, y: float, z: float, *, radius: float = 1.0) -> None:
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
            BridgeError: If the underlying pathfinder plugin call fails.
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
        self._goto_futs = [reached_fut, failed_fut]
        try:
            self._pf.set_goal_near(x, y, z, radius)

            done, pending = await asyncio.wait(
                [reached_fut, failed_fut],
                return_when=asyncio.FIRST_COMPLETED,
            )

            for task in pending:
                task.cancel()
            await asyncio.gather(*pending, return_exceptions=True)

            # Check futures in deterministic order: prioritise a
            # successful GoalReachedEvent over GoalFailedEvent when
            # both complete in the same tick.
            if reached_fut in done:
                if reached_fut.cancelled():
                    raise NavigationError("Navigation stopped")
                exc = reached_fut.exception()
                if exc is None:
                    return  # goal reached — success
                self._pf.stop()
                if isinstance(exc, asyncio.TimeoutError):
                    raise NavigationError("Navigation timed out") from exc
                raise NavigationError(f"Navigation failed: {exc}") from exc

            if failed_fut in done:
                if failed_fut.cancelled():
                    raise NavigationError("Navigation stopped")
                exc = failed_fut.exception()
                if exc is not None:
                    self._pf.stop()
                    if isinstance(exc, asyncio.TimeoutError):
                        raise NavigationError("Navigation timed out") from exc
                    raise NavigationError(f"Navigation failed: {exc}") from exc
                result = failed_fut.result()
                if isinstance(result, GoalFailedEvent):
                    self._pf.stop()
                    raise NavigationError(f"Navigation failed: {result.reason}")
        except BaseException:
            # Stop the underlying pathfinder goal so the bot doesn't
            # keep navigating after caller cancellation / other errors.
            self._pf.stop()
            reached_fut.cancel()
            failed_fut.cancel()
            await asyncio.gather(reached_fut, failed_fut, return_exceptions=True)
            raise
        finally:
            self._goto_futs = []
            self._navigating = False

    async def follow(self, username: str, *, distance: float = 2.0) -> None:
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

        js_entity = self._ctrl.get_entity_by_filter(username, EntityKind.PLAYER, 1e6)
        if js_entity is None:
            raise NavigationError(f"Player '{username}' not found")
        self._pf.set_goal_follow(js_entity, distance)
        self._navigating = True

    async def stop(self) -> None:
        """Stop current navigation.

        Cancels any in-flight ``goto()`` waiters so they unblock
        immediately instead of waiting until the timeout.
        """
        self._pf.stop()
        for fut in self._goto_futs:
            if not fut.done():
                fut.cancel()
        self._goto_futs = []
        self._navigating = False

    @property
    def is_navigating(self) -> bool:
        """Whether the bot is currently navigating."""
        return self._navigating
