"""Bot -- the public entry point for pyflayer."""

import asyncio
from collections.abc import Awaitable, Coroutine
from typing import Any, Callable, TypeVar, overload

from pyflayer._bridge.event_relay import EventRelay
from pyflayer._bridge.js_bot import JSBotController
from pyflayer._bridge.marshalling import (
    js_block_to_block,
    js_entity_to_entity,
)
from pyflayer._bridge.runtime import BridgeRuntime
from pyflayer.config import BotConfig
from pyflayer.models.block import Block
from pyflayer.models.entity import Entity, EntityKind
from pyflayer.models.errors import ConnectionError, NavigationError, NotSpawnedError
from pyflayer.models.events import GoalFailedEvent, GoalReachedEvent, SpawnEvent
from pyflayer.models.vec3 import Vec3

E = TypeVar("E")

_Handler = Callable[[E], Coroutine[Any, Any, None]]

# Type mapping from EntityKind enum to JS entity type strings
_ENTITY_KIND_TO_JS: dict[EntityKind, str] = {
    EntityKind.PLAYER: "player",
    EntityKind.MOB: "mob",
    EntityKind.ANIMAL: "animal",
    EntityKind.HOSTILE: "hostile",
    EntityKind.PROJECTILE: "projectile",
    EntityKind.OBJECT: "object",
    EntityKind.OTHER: "other",
}


class ObserveAPI:
    """Event subscription API.

    Supports decorator-style and method-style registration, plus
    one-shot ``wait_for`` and raw JS event access.
    """

    def __init__(self, relay: EventRelay) -> None:
        self._relay = relay
        self._bound_raw_events: set[str] = set()
        self._js_bot: Any = None
        self._on_fn: Any = None

    def _bind_js(self, js_bot: Any, on_fn: Any) -> None:
        """Store JS references for lazy raw event binding."""
        self._js_bot = js_bot
        self._on_fn = on_fn

    @overload
    def on(self, event_type: type[E]) -> Callable[[_Handler[E]], _Handler[E]]: ...

    @overload
    def on(self, event_type: type[E], handler: _Handler[E]) -> None: ...

    def on(
        self,
        event_type: type[E],
        handler: _Handler[E] | None = None,
    ) -> Callable[[_Handler[E]], _Handler[E]] | None:
        """Subscribe to an event type.

        Can be used as a decorator::

            @bot.observe.on(ChatEvent)
            async def on_chat(event: ChatEvent):
                ...

        Or called directly::

            bot.observe.on(ChatEvent, handle_chat)
        """
        if handler is not None:
            self._relay.add_handler(event_type, handler)  # type: ignore[arg-type]
            return None

        def decorator(fn: _Handler[E]) -> _Handler[E]:
            self._relay.add_handler(event_type, fn)  # type: ignore[arg-type]
            return fn

        return decorator

    def off(self, event_type: type[E], handler: _Handler[E]) -> None:
        """Unsubscribe a handler."""
        self._relay.remove_handler(event_type, handler)  # type: ignore[arg-type]

    async def wait_for(self, event_type: type[E], *, timeout: float = 30.0) -> E:
        """Wait for a single event occurrence."""
        return await self._relay.wait_for(event_type, timeout=timeout)  # type: ignore[return-value]

    @overload
    def on_raw(
        self, event_name: str
    ) -> Callable[
        [Callable[[dict], Awaitable[None]]], Callable[[dict], Awaitable[None]]
    ]: ...

    @overload
    def on_raw(
        self, event_name: str, handler: Callable[[dict], Awaitable[None]]
    ) -> None: ...

    def on_raw(
        self,
        event_name: str,
        handler: Callable[[dict], Awaitable[None]] | None = None,
    ) -> (
        Callable[
            [Callable[[dict], Awaitable[None]]], Callable[[dict], Awaitable[None]]
        ]
        | None
    ):
        """Subscribe to a raw JS event by name.

        This is an escape hatch for events not covered by the typed API.
        The handler receives a ``dict`` with an ``"args"`` key containing
        the raw JS callback arguments.

        Can be used as a decorator::

            @bot.observe.on_raw("entityMoved")
            async def on_entity_moved(data: dict):
                ...

        Or called directly::

            bot.observe.on_raw("entityMoved", handler)

        Warning:
            Raw event data is not typed or validated.
        """
        def _register(fn: Callable[[dict], Awaitable[None]]) -> None:
            # Lazily bind the JS event the first time someone subscribes
            if (
                event_name not in self._bound_raw_events
                and self._js_bot is not None
                and self._on_fn is not None
            ):
                self._relay.bind_raw_js_event(
                    self._js_bot, self._on_fn, event_name
                )
                self._bound_raw_events.add(event_name)
            self._relay.add_raw_handler(event_name, fn)  # type: ignore[arg-type]

        if handler is not None:
            _register(handler)
            return None

        def decorator(
            fn: Callable[[dict], Awaitable[None]],
        ) -> Callable[[dict], Awaitable[None]]:
            _register(fn)
            return fn

        return decorator

    def off_raw(
        self, event_name: str, handler: Callable[[dict], Awaitable[None]]
    ) -> None:
        """Unsubscribe a raw event handler."""
        self._relay.remove_raw_handler(event_name, handler)  # type: ignore[arg-type]


class Bot:
    """pyflayer entry point.

    Example::

        async def main():
            bot = Bot(host="localhost", username="Steve")
            await bot.connect()
            await bot.wait_until_spawned()
            await bot.chat("Hello!")
            await bot.disconnect()
    """

    def __init__(
        self,
        host: str,
        port: int = 25565,
        username: str = "pyflayer",
        version: str | None = None,
        auth: str | None = None,
        hide_errors: bool = False,
    ) -> None:
        self._config = BotConfig(
            host=host,
            port=port,
            username=username,
            version=version,
            auth=auth,
            hide_errors=hide_errors,
        )
        self._relay = EventRelay()
        self._observe = ObserveAPI(self._relay)
        self._runtime: BridgeRuntime | None = None
        self._controller: JSBotController | None = None
        self._connected = False
        self._spawned = False

    def _ensure_connected(self) -> JSBotController:
        """Return the controller or raise if not connected."""
        if self._controller is None or not self._connected:
            raise ConnectionError("Bot is not connected.")
        return self._controller

    # -- Lifecycle --

    async def connect(self) -> None:
        """Connect to the Minecraft server.

        Initializes the JSPyBridge runtime and calls
        ``mineflayer.createBot()``.
        """
        if self._connected:
            return
        loop = asyncio.get_running_loop()
        self._relay.set_loop(loop)

        self._runtime = BridgeRuntime()
        self._runtime.start()

        self._controller = JSBotController(self._runtime, self._config)
        self._controller.create_bot()

        self._controller.load_pathfinder()

        self._relay.register_js_events(
            self._controller.js_bot,
            self._runtime.js_module.On,
        )
        self._observe._bind_js(
            self._controller.js_bot,
            self._runtime.js_module.On,
        )
        self._connected = True

    async def disconnect(self) -> None:
        """Disconnect from the server and clean up."""
        if not self._connected:
            return
        if self._controller is not None:
            self._controller.quit()
        if self._runtime is not None:
            self._runtime.shutdown()
        self._connected = False
        self._spawned = False

    async def wait_until_spawned(self, timeout: float = 30.0) -> None:
        """Block until the bot has spawned in the world."""
        if self._spawned:
            return
        await self._observe.wait_for(SpawnEvent, timeout=timeout)
        self._spawned = True
        if self._controller is not None:
            self._controller.setup_pathfinder_movements()

    # -- State properties --

    @property
    def is_connected(self) -> bool:
        """Whether the bot is currently connected."""
        return self._connected

    @property
    def is_alive(self) -> bool:
        """Whether the bot entity is alive (health > 0)."""
        ctrl = self._ensure_connected()
        return ctrl.is_alive()

    @property
    def position(self) -> Vec3:
        """Current bot position."""
        ctrl = self._ensure_connected()
        data = ctrl.get_position()
        return Vec3(x=data["x"], y=data["y"], z=data["z"])

    @property
    def health(self) -> float:
        """Bot health (0–20)."""
        ctrl = self._ensure_connected()
        return ctrl.get_health()

    @property
    def food(self) -> float:
        """Bot food level (0–20)."""
        ctrl = self._ensure_connected()
        return ctrl.get_food()

    @property
    def username(self) -> str:
        """Bot username."""
        return self._config.username

    @property
    def game_mode(self) -> str:
        """Current game mode (``"survival"``, ``"creative"``, etc.)."""
        ctrl = self._ensure_connected()
        return ctrl.get_game_mode()

    @property
    def players(self) -> dict[str, dict]:
        """Online players as ``{username: info_dict}``."""
        ctrl = self._ensure_connected()
        js_players = ctrl.get_players()
        result: dict[str, dict] = {}
        for key in js_players:
            p = js_players[key]
            result[str(key)] = {
                "username": str(p.username),
                "ping": int(p.ping) if hasattr(p, "ping") else 0,
            }
        return result

    # -- Chat --

    async def chat(self, message: str) -> None:
        """Send a chat message."""
        ctrl = self._ensure_connected()
        ctrl.chat(message)

    async def whisper(self, username: str, message: str) -> None:
        """Send a whisper (private message) to a player.

        Args:
            username: Target player name.
            message: Message content.
        """
        ctrl = self._ensure_connected()
        ctrl.whisper(username, message)

    # -- World queries --

    async def find_block(
        self,
        name: str,
        *,
        max_distance: float = 64,
        count: int = 1,
    ) -> list[Block]:
        """Find blocks by name near the bot.

        Args:
            name: Block name (e.g. ``"oak_log"``).
            max_distance: Search radius in blocks.
            count: Maximum number of results.

        Returns:
            List of :class:`Block` snapshots, closest first.
        """
        ctrl = self._ensure_connected()
        js_blocks = ctrl.find_blocks(name, max_distance, count)
        return [js_block_to_block(b) for b in js_blocks]

    async def block_at(self, x: int, y: int, z: int) -> Block | None:
        """Get the block at a specific position.

        Args:
            x: Block X coordinate.
            y: Block Y coordinate.
            z: Block Z coordinate.

        Returns:
            A :class:`Block` snapshot, or ``None`` if the chunk is not loaded.
        """
        ctrl = self._ensure_connected()
        js_block = ctrl.block_at(x, y, z)
        if js_block is None:
            return None
        return js_block_to_block(js_block)

    async def find_entity(
        self,
        *,
        name: str | None = None,
        kind: EntityKind | None = None,
        max_distance: float = 32,
    ) -> Entity | None:
        """Find the nearest entity matching the given criteria.

        Args:
            name: Entity name filter (e.g. ``"zombie"`` or a player name).
            kind: Entity kind filter.
            max_distance: Search radius in blocks.

        Returns:
            The nearest matching :class:`Entity`, or ``None``.
        """
        ctrl = self._ensure_connected()
        entity_type = _ENTITY_KIND_TO_JS.get(kind) if kind is not None else None
        js_entity = ctrl.get_entity_by_filter(name, entity_type, max_distance)
        if js_entity is None:
            return None
        return js_entity_to_entity(js_entity)

    # -- Actions --

    async def dig(self, block: Block) -> None:
        """Dig (break) a block.

        Args:
            block: The :class:`Block` to dig. Use :meth:`find_block` or
                :meth:`block_at` to obtain one.

        Raises:
            NotSpawnedError: If the bot is not connected.
        """
        ctrl = self._ensure_connected()
        # We need the JS block proxy, so re-query by position
        js_block = ctrl.block_at(
            int(block.position.x),
            int(block.position.y),
            int(block.position.z),
        )
        if js_block is None:
            return
        ctrl.dig(js_block)

    async def place_block(
        self,
        reference_block: Block,
        face: Vec3,
        *,
        item_name: str | None = None,
    ) -> None:
        """Place a block against a reference block face.

        Args:
            reference_block: The block to place against.
            face: Direction vector for the face (e.g. ``Vec3(0, 1, 0)``
                for the top face).
            item_name: If provided, equip this item before placing.

        Raises:
            NotSpawnedError: If the bot is not connected.
        """
        ctrl = self._ensure_connected()
        if item_name is not None:
            ctrl.equip_item(item_name)
        js_block = ctrl.block_at(
            int(reference_block.position.x),
            int(reference_block.position.y),
            int(reference_block.position.z),
        )
        if js_block is None:
            return
        ctrl.place_block(js_block, face.x, face.y, face.z)

    async def use_item(self) -> None:
        """Activate the currently held item."""
        ctrl = self._ensure_connected()
        ctrl.use_item()

    async def attack(self, entity: Entity) -> None:
        """Attack an entity.

        Args:
            entity: The :class:`Entity` to attack.
        """
        ctrl = self._ensure_connected()
        js_entity = ctrl.get_entity_by_filter(
            entity.name, None, 32,
        )
        if js_entity is not None:
            ctrl.attack(js_entity)

    # -- Movement --

    async def goto(
        self, x: float, y: float, z: float, radius: float = 1.0
    ) -> None:
        """Move the bot to a position using A* pathfinding.

        Uses ``mineflayer-pathfinder`` for obstacle-aware navigation.
        Resolves when the bot arrives within *radius* of the target,
        or raises :class:`NavigationError` if no path is found.

        Args:
            x: Target X coordinate.
            y: Target Y coordinate.
            z: Target Z coordinate.
            radius: Acceptable distance from the target.

        Raises:
            NavigationError: If the pathfinder cannot reach the goal.
        """
        ctrl = self._ensure_connected()

        # Create futures for both possible outcomes
        reached_fut = self._relay.wait_for(GoalReachedEvent, timeout=300.0)
        failed_fut = self._relay.wait_for(GoalFailedEvent, timeout=300.0)

        ctrl.set_goal_near(x, y, z, radius)

        done, pending = await asyncio.wait(
            [asyncio.ensure_future(reached_fut), asyncio.ensure_future(failed_fut)],
            return_when=asyncio.FIRST_COMPLETED,
        )

        for task in pending:
            task.cancel()

        # Both futures may complete together (path_stop always fires after
        # goal_reached).  Prioritize success: if GoalReachedEvent is among
        # the results, treat navigation as successful.
        events = [task.result() for task in done]
        if any(isinstance(e, GoalReachedEvent) for e in events):
            return
        failed = next((e for e in events if isinstance(e, GoalFailedEvent)), None)
        if failed is not None:
            raise NavigationError(f"Navigation failed: {failed.reason}")

    async def look_at(self, x: float, y: float, z: float) -> None:
        """Rotate the bot to look at a position.

        Args:
            x: Target X coordinate.
            y: Target Y coordinate.
            z: Target Z coordinate.
        """
        ctrl = self._ensure_connected()
        ctrl.look_at(x, y, z)

    async def jump(self) -> None:
        """Make the bot jump once."""
        ctrl = self._ensure_connected()
        ctrl.set_control_state("jump", True)
        await asyncio.sleep(0.1)
        ctrl.set_control_state("jump", False)

    async def stop(self) -> None:
        """Stop all movement and cancel pathfinding."""
        ctrl = self._ensure_connected()
        ctrl.stop_pathfinder()
        ctrl.clear_control_states()

    # -- Sub-APIs --

    @property
    def observe(self) -> ObserveAPI:
        """Event subscription API."""
        return self._observe
