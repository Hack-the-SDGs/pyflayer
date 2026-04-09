"""Bot -- the public entry point for minethon."""

import asyncio

from minethon._bridge._events import (
    DigDoneEvent,
    EquipDoneEvent,
    LookAtDoneEvent,
    PlaceDoneEvent,
)
from minethon._bridge.event_relay import EventRelay
from minethon._bridge.js_bot import JSBotController
from minethon._bridge.marshalling import (
    js_block_to_block,
    js_entity_to_entity,
    js_item_to_item_stack,
)
from minethon._bridge.plugin_host import PluginHost
from minethon._bridge.runtime import BridgeRuntime
from minethon.api.navigation import NavigationAPI
from minethon.api.observe import ObserveAPI
from minethon.config import BotConfig
from minethon.models.block import Block
from minethon.models.entity import Entity, EntityKind
from minethon.models.errors import (
    BridgeError,
    InventoryError,
    NotSpawnedError,
    MinethonConnectionError,
    MinethonError,
)
from minethon.models.events import (
    EndEvent,
    SpawnEvent,
)
from minethon.models.experience import Experience
from minethon.models.game_state import GameState
from minethon.models.item import ItemStack
from minethon.models.player_info import PlayerInfo
from minethon.models.time_state import TimeState
from minethon.models.vec3 import Vec3
from minethon.raw import RawBotHandle


class Bot:
    """minethon entry point.

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
        username: str = "minethon",
        *,
        password: str | None = None,
        version: str | None = None,
        auth: str | None = None,
        auth_server: str | None = None,
        session_server: str | None = None,
        hide_errors: bool | None = None,
        log_errors: bool | None = None,
        disable_chat_signing: bool | None = None,
        check_timeout_interval: int | None = None,
        keep_alive: bool | None = None,
        respawn: bool | None = None,
        chat_length_limit: int | None = None,
        view_distance: str | None = None,
        default_chat_patterns: bool | None = None,
        physics_enabled: bool | None = None,
        brand: str | None = None,
        skip_validation: bool | None = None,
        profiles_folder: str | None = None,
        load_internal_plugins: bool | None = None,
        event_throttle_ms: dict[str, int] | None = None,
    ) -> None:
        self._config = BotConfig(
            host=host,
            port=port,
            username=username,
            password=password,
            version=version,
            auth=auth,
            auth_server=auth_server,
            session_server=session_server,
            hide_errors=hide_errors,
            log_errors=log_errors,
            disable_chat_signing=disable_chat_signing,
            check_timeout_interval=check_timeout_interval,
            keep_alive=keep_alive,
            respawn=respawn,
            chat_length_limit=chat_length_limit,
            view_distance=view_distance,
            default_chat_patterns=default_chat_patterns,
            physics_enabled=physics_enabled,
            brand=brand,
            skip_validation=skip_validation,
            profiles_folder=profiles_folder,
            load_internal_plugins=load_internal_plugins,
            **({"event_throttle_ms": event_throttle_ms} if event_throttle_ms is not None else {}),
        )
        self._relay = EventRelay(self._config.event_throttle_ms)
        self._observe = ObserveAPI(self._relay)
        self._runtime: BridgeRuntime | None = None
        self._controller: JSBotController | None = None
        self._connected = False
        self._spawned = False
        self._resolved_username: str | None = None
        self._plugin_host: PluginHost | None = None
        self._navigation: NavigationAPI | None = None
        self._on_end_handler: object | None = None
        # Serialize long-running operations that use global completion
        # events, preventing concurrent calls from stealing each other's
        # completion signal.
        self._dig_lock = asyncio.Lock()
        self._place_lock = asyncio.Lock()
        self._look_at_lock = asyncio.Lock()

    def _ensure_connected(self) -> JSBotController:
        """Return the controller or raise if not connected."""
        if self._controller is None or not self._connected:
            raise MinethonConnectionError("Bot is not connected.")
        return self._controller

    def _ensure_spawned(self) -> JSBotController:
        """Return the controller or raise if not spawned.

        Implies connected -- raises ``MinethonConnectionError`` first if
        not connected, then ``NotSpawnedError`` if not yet spawned.
        """
        ctrl = self._ensure_connected()
        if not self._spawned:
            raise NotSpawnedError(
                "Bot has not spawned yet. Call wait_until_spawned() first."
            )
        return ctrl

    # -- Lifecycle --

    async def connect(self) -> None:
        """Connect to the Minecraft server.

        Initializes the JSPyBridge runtime and calls
        ``mineflayer.createBot()``.
        """
        if self._connected:
            return

        # Clean up stale resources from a previous session (e.g. after a
        # remote EndEvent flipped _connected but left runtime alive).
        if self._runtime is not None or self._controller is not None:
            await self.disconnect()

        loop = asyncio.get_running_loop()
        self._relay.set_loop(loop)

        self._runtime = BridgeRuntime()
        self._runtime.start()

        self._controller = JSBotController(self._runtime, self._config)
        self._controller.create_bot()

        self._plugin_host = PluginHost(self._runtime, self._controller.js_bot)
        self._plugin_host.load_pathfinder()
        self._navigation = NavigationAPI(
            self._plugin_host, self._controller, self._relay
        )

        self._relay.register_js_events(
            self._controller.js_bot,
            self._runtime.js_module.On,
        )
        self._observe._bind_js(
            self._controller.js_bot,
            self._runtime.js_module.On,
        )

        # Register internal EndEvent handler *before* setting _connected,
        # so an immediate "end" event (e.g. connection refused) is caught.
        # Remove any previous handler to avoid accumulation on reconnect.
        if self._on_end_handler is not None:
            try:
                self._relay.remove_handler(EndEvent, self._on_end_handler)  # type: ignore[arg-type]
            except ValueError:
                pass  # Already removed by reset()

        async def _on_end(_event: EndEvent) -> None:
            self._connected = False
            self._spawned = False

        self._on_end_handler = _on_end
        self._relay.add_handler(EndEvent, _on_end)  # type: ignore[arg-type]
        self._connected = True

    async def disconnect(self) -> None:
        """Disconnect from the server and clean up resources.

        Safe to call even after a remote disconnect -- the runtime and
        controller are always cleaned up if they exist.
        """
        if self._on_end_handler is not None:
            try:
                self._relay.remove_handler(EndEvent, self._on_end_handler)  # type: ignore[arg-type]
            except ValueError:
                pass  # Handler already gone
            self._on_end_handler = None
        self._relay.reset()
        self._observe._reset_state()
        if self._controller is not None:
            if self._connected:
                self._controller.quit()
            self._controller = None
        self._navigation = None
        self._plugin_host = None
        if self._runtime is not None:
            self._runtime.shutdown()
            self._runtime = None
        self._connected = False
        self._spawned = False
        self._resolved_username = None

    async def wait_until_spawned(self, timeout: float = 30.0) -> None:
        """Block until the bot has spawned in the world."""
        if self._spawned:
            return
        await self._observe.wait_for(SpawnEvent, timeout=timeout)
        self._spawned = True
        if self._plugin_host is not None:
            self._plugin_host.setup_pathfinder_movements()

    # -- State properties --

    @property
    def is_connected(self) -> bool:
        """Whether the bot is currently connected."""
        return self._connected

    @property
    def is_alive(self) -> bool:
        """Whether the bot entity is alive.

        Reads the ``isAlive`` flag from mineflayer directly, which
        accounts for respawn transitions.
        """
        ctrl = self._ensure_spawned()
        return ctrl.get_is_alive_js()

    @property
    def position(self) -> Vec3:
        """Current bot position.

        Raises:
            NotSpawnedError: If ``wait_until_spawned()`` has not completed.
        """
        ctrl = self._ensure_spawned()
        data = ctrl.get_position()
        return Vec3(x=data["x"], y=data["y"], z=data["z"])

    @property
    def health(self) -> float:
        """Bot health (0-20).

        Raises:
            NotSpawnedError: If ``wait_until_spawned()`` has not completed.
        """
        ctrl = self._ensure_spawned()
        return ctrl.get_health()

    @property
    def food(self) -> float:
        """Bot food level (0-20).

        Raises:
            NotSpawnedError: If ``wait_until_spawned()`` has not completed.
        """
        ctrl = self._ensure_spawned()
        return ctrl.get_food()

    @property
    def username(self) -> str:
        """Bot username.

        After authentication the server may assign a different name
        (e.g. Microsoft auth).  This reads the live value from the JS
        bot on first access after connecting, then caches it.
        """
        if self._controller is not None and self._connected:
            if self._resolved_username is None:
                self._resolved_username = self._controller.get_username_js()
            return self._resolved_username
        return self._config.username

    @property
    def game_mode(self) -> str:
        """Current game mode (``"survival"``, ``"creative"``, etc.)."""
        ctrl = self._ensure_connected()
        return ctrl.get_game_mode()

    @property
    def players(self) -> dict[str, PlayerInfo]:
        """Online players as ``{username: PlayerInfo}``."""
        ctrl = self._ensure_connected()
        raw = ctrl.get_players_full()
        return {
            name: PlayerInfo(
                username=str(info["username"]),
                uuid=str(info["uuid"]),
                ping=int(info["ping"]),  # type: ignore[arg-type]
                game_mode=int(info["game_mode"]),  # type: ignore[arg-type]
                display_name=str(info["display_name"]) if info["display_name"] is not None else None,
            )
            for name, info in raw.items()
        }

    @property
    def food_saturation(self) -> float:
        """Bot food saturation level.

        Raises:
            NotSpawnedError: If ``wait_until_spawned()`` has not completed.
        """
        ctrl = self._ensure_spawned()
        return ctrl.get_food_saturation()

    @property
    def oxygen_level(self) -> int:
        """Bot oxygen (air supply) level (0-20).

        Defaults to 20 when no metadata has been received yet.

        Raises:
            NotSpawnedError: If ``wait_until_spawned()`` has not completed.
        """
        ctrl = self._ensure_spawned()
        return ctrl.get_oxygen_level()

    @property
    def experience(self) -> Experience:
        """Bot experience state snapshot.

        Raises:
            NotSpawnedError: If ``wait_until_spawned()`` has not completed.
        """
        ctrl = self._ensure_spawned()
        data = ctrl.get_experience()
        return Experience(
            level=int(data["level"]),  # type: ignore[arg-type]
            points=int(data["points"]),  # type: ignore[arg-type]
            progress=float(data["progress"]),  # type: ignore[arg-type]
        )

    @property
    def game(self) -> GameState:
        """Server game state snapshot."""
        ctrl = self._ensure_connected()
        data = ctrl.get_game_state()
        return GameState(
            game_mode=str(data["game_mode"]),
            dimension=str(data["dimension"]),
            difficulty=str(data["difficulty"]),
            hardcore=bool(data["hardcore"]),
            max_players=int(data["max_players"]),  # type: ignore[arg-type]
            server_brand=str(data["server_brand"]),
            min_y=int(data["min_y"]),  # type: ignore[arg-type]
            height=int(data["height"]),  # type: ignore[arg-type]
        )

    @property
    def difficulty(self) -> str:
        """Server difficulty (``"peaceful"``, ``"easy"``, ``"normal"``, ``"hard"``)."""
        return self.game.difficulty

    @property
    def is_raining(self) -> bool:
        """Whether it is currently raining."""
        ctrl = self._ensure_connected()
        return ctrl.get_is_raining()

    @property
    def thunder_state(self) -> float:
        """Thunder intensity level (0 means no thunder)."""
        ctrl = self._ensure_connected()
        return ctrl.get_thunder_state()

    @property
    def time(self) -> TimeState:
        """World time state snapshot."""
        ctrl = self._ensure_connected()
        data = ctrl.get_time()
        return TimeState(
            time_of_day=int(data["time_of_day"]),  # type: ignore[arg-type]
            day=int(data["day"]),  # type: ignore[arg-type]
            is_day=bool(data["is_day"]),
            moon_phase=int(data["moon_phase"]),  # type: ignore[arg-type]
            age=int(data["age"]),  # type: ignore[arg-type]
            do_daylight_cycle=bool(data["do_daylight_cycle"]),
        )

    @property
    def held_item(self) -> ItemStack | None:
        """Item currently held in the bot's main hand, or ``None``.

        Raises:
            NotSpawnedError: If ``wait_until_spawned()`` has not completed.
        """
        ctrl = self._ensure_spawned()
        js_item = ctrl.get_held_item()
        if js_item is None:
            return None
        return js_item_to_item_stack(js_item)

    @property
    def quick_bar_slot(self) -> int:
        """Currently selected quick bar slot (0-8).

        Raises:
            NotSpawnedError: If ``wait_until_spawned()`` has not completed.
        """
        ctrl = self._ensure_spawned()
        return ctrl.get_quick_bar_slot()

    @quick_bar_slot.setter
    def quick_bar_slot(self, slot: int) -> None:
        if not (0 <= slot <= 8):
            raise ValueError(f"quick_bar_slot must be 0-8, got {slot}")
        ctrl = self._ensure_spawned()
        ctrl.set_quick_bar_slot(slot)

    @property
    def spawn_point(self) -> Vec3:
        """Bot spawn point position.

        Raises:
            NotSpawnedError: If ``wait_until_spawned()`` has not completed.
            BridgeError: If the server has not yet sent a ``spawn_position``
                packet (``bot.spawnPoint`` is ``null``).
        """
        ctrl = self._ensure_spawned()
        data = ctrl.get_spawn_point()
        return Vec3(x=data["x"], y=data["y"], z=data["z"])

    @property
    def is_sleeping(self) -> bool:
        """Whether the bot is currently sleeping in a bed."""
        ctrl = self._ensure_connected()
        return ctrl.get_is_sleeping()

    @property
    def target_dig_block(self) -> Block | None:
        """Block currently being dug, or ``None``."""
        ctrl = self._ensure_connected()
        js_block = ctrl.get_target_dig_block()
        if js_block is None:
            return None
        return js_block_to_block(js_block)

    @property
    def entity(self) -> Entity:
        """The bot's own entity snapshot.

        Raises:
            NotSpawnedError: If ``wait_until_spawned()`` has not completed.
        """
        ctrl = self._ensure_spawned()
        return js_entity_to_entity(ctrl.get_bot_entity())

    @property
    def entities(self) -> dict[int, Entity]:
        """All currently tracked entities as ``{entity_id: Entity}``.

        Note:
            This creates a snapshot of every tracked entity. For
            frequent access consider caching or using
            :meth:`find_entity` instead.

            ``Entity.metadata`` is always ``None`` in this snapshot
            for performance reasons.  Use :meth:`find_entity` if you
            need metadata for a specific entity.

        Raises:
            NotSpawnedError: If ``wait_until_spawned()`` has not completed.
        """
        ctrl = self._ensure_spawned()
        result: dict[int, Entity] = {}
        for raw in ctrl.get_entities_snapshot():
            pos = raw["position"]  # type: ignore[assignment]
            position = Vec3(float(pos["x"]), float(pos["y"]), float(pos["z"]))  # type: ignore[index]
            velocity: Vec3 | None = None
            vel = raw.get("velocity")
            if vel is not None:
                velocity = Vec3(float(vel["x"]), float(vel["y"]), float(vel["z"]))  # type: ignore[index]
            etype = raw.get("type")
            kind_map = {"player": EntityKind.PLAYER, "mob": EntityKind.MOB,
                        "animal": EntityKind.ANIMAL, "hostile": EntityKind.HOSTILE,
                        "projectile": EntityKind.PROJECTILE, "object": EntityKind.OBJECT}
            kind = kind_map.get(str(etype), EntityKind.OTHER) if etype else EntityKind.OTHER
            name = raw.get("username") or raw.get("name")
            health_val = raw.get("health")
            eid = int(raw["id"])  # type: ignore[arg-type]
            result[eid] = Entity(
                id=eid,
                name=str(name) if name is not None else None,
                kind=kind,
                position=position,
                velocity=velocity,
                health=float(health_val) if health_val is not None else None,
            )
        return result

    @property
    def version(self) -> str:
        """Minecraft version string (e.g. ``"1.20.4"``)."""
        ctrl = self._ensure_connected()
        return ctrl.get_version()

    @property
    def physics_enabled(self) -> bool:
        """Whether the physics simulation is active."""
        ctrl = self._ensure_connected()
        return ctrl.get_physics_enabled()

    @physics_enabled.setter
    def physics_enabled(self, value: bool) -> None:
        ctrl = self._ensure_connected()
        ctrl.set_physics_enabled(value)

    @property
    def firework_rocket_duration(self) -> int:
        """Remaining firework rocket boost ticks (0 if not boosting)."""
        ctrl = self._ensure_connected()
        return ctrl.get_firework_rocket_duration()

    @property
    def tablist(self) -> tuple[str, str]:
        """Tab list ``(header, footer)`` as plain strings."""
        ctrl = self._ensure_connected()
        data = ctrl.get_tablist()
        return (data["header"], data["footer"])

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
        js_entity = ctrl.get_entity_by_filter(name, kind, max_distance)
        if js_entity is None:
            return None
        return js_entity_to_entity(js_entity)

    # -- Actions (non-blocking, event-driven) --

    async def dig(self, block: Block) -> None:
        """Dig (break) a block.

        Args:
            block: The :class:`Block` to dig. Use :meth:`find_block` or
                :meth:`block_at` to obtain one.

        Raises:
            MinethonError: If the block is no longer present.
            BridgeError: If the JS dig operation fails or times out.
        """
        async with self._dig_lock:
            ctrl = self._ensure_connected()
            js_block = ctrl.block_at(
                int(block.position.x),
                int(block.position.y),
                int(block.position.z),
            )
            if js_block is None:
                raise MinethonError(
                    f"Block at {block.position} is no longer available "
                    "(chunk unloaded or block changed)"
                )
            ctrl.start_dig(js_block)
            try:
                event = await self._relay.wait_for(DigDoneEvent, timeout=60.0)
            except asyncio.TimeoutError as exc:
                raise BridgeError("dig timed out") from exc
            if event.error is not None:
                raise BridgeError(f"dig failed: {event.error}")

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
            InventoryError: If *item_name* is not found in inventory
                or equip times out.
            BridgeError: If the JS place operation fails or times out.
        """
        async with self._place_lock:
            ctrl = self._ensure_connected()
            if item_name is not None:
                if not ctrl.start_equip(item_name):
                    raise InventoryError(
                        f"Item '{item_name}' not found in inventory"
                    )
                try:
                    equip_event = await self._relay.wait_for(
                        EquipDoneEvent, timeout=10.0
                    )
                except asyncio.TimeoutError as exc:
                    raise InventoryError("equip timed out") from exc
                if equip_event.error is not None:
                    raise InventoryError(f"equip failed: {equip_event.error}")

            js_block = ctrl.block_at(
                int(reference_block.position.x),
                int(reference_block.position.y),
                int(reference_block.position.z),
            )
            if js_block is None:
                raise MinethonError(
                    f"Block at {reference_block.position} is no longer available "
                    "(chunk unloaded or block changed)"
                )
            ctrl.start_place(js_block, face.x, face.y, face.z)
            try:
                event = await self._relay.wait_for(PlaceDoneEvent, timeout=30.0)
            except asyncio.TimeoutError as exc:
                raise BridgeError("place timed out") from exc
            if event.error is not None:
                raise BridgeError(f"place failed: {event.error}")

    async def use_item(self) -> None:
        """Activate the currently held item."""
        ctrl = self._ensure_connected()
        ctrl.use_item()

    async def attack(self, entity: Entity) -> None:
        """Attack an entity.

        Args:
            entity: The :class:`Entity` to attack. Looked up by
                numeric entity ID for precision.
        """
        ctrl = self._ensure_connected()
        js_entity = ctrl.get_entity_by_id(entity.id)
        if js_entity is not None:
            ctrl.attack(js_entity)

    # -- Movement --

    async def goto(
        self, x: float, y: float, z: float, radius: float = 1.0
    ) -> None:
        """Move the bot to a position using A* pathfinding.

        Convenience wrapper for ``bot.navigation.goto()``.
        Uses ``mineflayer-pathfinder`` for obstacle-aware navigation.

        Args:
            x: Target X coordinate.
            y: Target Y coordinate.
            z: Target Z coordinate.
            radius: Acceptable distance from the target.

        Raises:
            NotSpawnedError: If ``wait_until_spawned()`` has not completed.
            NavigationError: If the pathfinder cannot reach the goal.
            BridgeError: If a low-level bridge or pathfinding operation fails.
        """
        self._ensure_spawned()
        await self.navigation.goto(x, y, z, radius=radius)

    async def look_at(self, x: float, y: float, z: float) -> None:
        """Rotate the bot to look at a position.

        Args:
            x: Target X coordinate.
            y: Target Y coordinate.
            z: Target Z coordinate.

        Raises:
            BridgeError: If the look operation fails or times out.
        """
        async with self._look_at_lock:
            ctrl = self._ensure_connected()
            ctrl.start_look_at(x, y, z)
            try:
                event = await self._relay.wait_for(LookAtDoneEvent, timeout=10.0)
            except asyncio.TimeoutError as exc:
                raise BridgeError("look_at timed out") from exc
            if event.error is not None:
                raise BridgeError(f"look_at failed: {event.error}")

    async def jump(self) -> None:
        """Make the bot jump once."""
        ctrl = self._ensure_connected()
        ctrl.set_control_state("jump", True)
        await asyncio.sleep(0.1)
        ctrl.set_control_state("jump", False)

    async def stop(self) -> None:
        """Stop all movement and cancel pathfinding."""
        ctrl = self._ensure_connected()
        await self.navigation.stop()
        ctrl.clear_control_states()

    # -- Sub-APIs --

    @property
    def navigation(self) -> NavigationAPI:
        """Path-planning and movement control API."""
        if self._navigation is None:
            raise MinethonConnectionError("Bot is not connected.")
        return self._navigation

    @property
    def observe(self) -> ObserveAPI:
        """Event subscription API."""
        return self._observe

    @property
    def raw(self) -> RawBotHandle:
        """Raw access to the underlying mineflayer JS bot.

        Warning:
            This is an escape hatch for advanced use cases. The returned
            handle exposes the raw JSPyBridge proxy with **no** type
            safety or API stability guarantees. Refer to the mineflayer
            JS docs for usage.
        """
        ctrl = self._ensure_connected()
        return RawBotHandle(ctrl.js_bot)

    @property
    def plugins(self) -> PluginHost:
        """Plugin management API.

        Includes ``raw_plugin(name)`` for loading arbitrary JS plugins.
        """
        if self._plugin_host is None:
            raise MinethonConnectionError("Bot is not connected.")
        return self._plugin_host
