"""Bot -- the public entry point for minethon."""

import asyncio
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from minethon._bridge._events import (
    ActivateBlockDoneEvent,
    ActivateEntityAtDoneEvent,
    ActivateEntityDoneEvent,
    ChunksLoadedDoneEvent,
    ClickWindowDoneEvent,
    ConsumeDoneEvent,
    CraftDoneEvent,
    CreativeClearInventoryDoneEvent,
    CreativeClearSlotDoneEvent,
    CreativeFlyToDoneEvent,
    CreativeSetSlotDoneEvent,
    DigDoneEvent,
    ElytraFlyDoneEvent,
    EquipDoneEvent,
    FishDoneEvent,
    LookAtDoneEvent,
    LookDoneEvent,
    MoveSlotItemDoneEvent,
    OpenAnvilDoneEvent,
    OpenContainerDoneEvent,
    OpenEnchantmentTableDoneEvent,
    OpenFurnaceDoneEvent,
    OpenVillagerDoneEvent,
    PlaceDoneEvent,
    PlaceEntityDoneEvent,
    PutAwayDoneEvent,
    SleepDoneEvent,
    TabCompleteDoneEvent,
    TossDoneEvent,
    TossStackDoneEvent,
    TradeDoneEvent,
    TransferDoneEvent,
    UnequipDoneEvent,
    WaitForTicksDoneEvent,
    WakeDoneEvent,
    WriteBookDoneEvent,
)
from minethon._bridge.event_relay import EventRelay
from minethon._bridge.js_bot import JSBotController
from minethon._bridge.marshalling import (
    js_block_to_block,
    js_entity_to_entity,
    js_item_to_item_stack,
    js_window_to_window_handle,
    villager_snapshot_to_session,
)
from minethon._bridge.plugin_host import PluginHost
from minethon._bridge.runtime import BridgeRuntime
from minethon.api.navigation import NavigationAPI
from minethon.api.observe import ObserveAPI
from minethon.api.plugins import PluginAPI
from minethon.config import BotConfig
from minethon.models import Recipe, VillagerSession, WindowHandle
from minethon.models.block import Block
from minethon.models.entity import Entity, EntityKind
from minethon.models.errors import (
    BridgeError,
    InventoryError,
    MinethonConnectionError,
    MinethonError,
    NotSpawnedError,
)
from minethon.models.events import (
    BreathEvent,
    EndEvent,
    ExperienceEvent,
    GameEvent,
    GoalReachedEvent,
    HealthChangedEvent,
    HeldItemChangedEvent,
    MessageStrEvent,
    MoveEvent,
    PlayerJoinedEvent,
    PlayerLeftEvent,
    PlayerUpdatedEvent,
    RainEvent,
    RespawnEvent,
    SleepEvent,
    SpawnEvent,
    TimeEvent,
    WakeEvent,
    WeatherUpdateEvent,
)
from minethon.models.experience import Experience
from minethon.models.game_state import GameState
from minethon.models.item import ItemStack
from minethon.models.player_info import PlayerInfo
from minethon.models.time_state import TimeState
from minethon.models.vec3 import Vec3
from minethon.raw import RawBotHandle

if TYPE_CHECKING:
    import re


@dataclass(slots=True)
class _BotStateCache:
    """Mutable snapshot store for sync Bot properties."""

    position: Vec3 | None = None
    health: float | None = None
    food: float | None = None
    food_saturation: float | None = None
    oxygen_level: int | None = None
    experience: Experience | None = None
    game: GameState | None = None
    time: TimeState | None = None
    held_item: ItemStack | None = None
    held_item_known: bool = False
    rain_state: float | None = None
    thunder_state: float | None = None
    is_sleeping: bool = False
    is_sleeping_known: bool = False
    version: str | None = None
    physics_enabled: bool | None = None
    quick_bar_slot: int | None = None
    players: dict[str, PlayerInfo] = field(default_factory=dict)


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
            **(
                {"event_throttle_ms": event_throttle_ms}
                if event_throttle_ms is not None
                else {}
            ),
        )
        self._relay = EventRelay(self._config.event_throttle_ms)
        self._observe = ObserveAPI(self._relay)
        self._runtime: BridgeRuntime | None = None
        self._controller: JSBotController | None = None
        self._connected = False
        self._spawned = False
        self._state = _BotStateCache()
        self._window_registry: dict[int, Any] = {}
        self._recipe_registry: dict[int, Any] = {}
        self._recipe_counter: int = 0
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
        self._look_lock = asyncio.Lock()
        self._sleep_lock = asyncio.Lock()
        self._consume_lock = asyncio.Lock()
        self._fish_lock = asyncio.Lock()
        self._equip_lock = asyncio.Lock()
        self._unequip_lock = asyncio.Lock()
        self._toss_lock = asyncio.Lock()
        self._activate_block_lock = asyncio.Lock()
        self._activate_entity_lock = asyncio.Lock()
        self._craft_lock = asyncio.Lock()
        self._tab_complete_lock = asyncio.Lock()
        self._wait_chunks_lock = asyncio.Lock()
        self._wait_ticks_lock = asyncio.Lock()
        self._window_lock = asyncio.Lock()
        self._trade_lock = asyncio.Lock()
        self._elytra_fly_lock = asyncio.Lock()
        self._activate_entity_at_lock = asyncio.Lock()
        self._write_book_lock = asyncio.Lock()
        self._place_entity_lock = asyncio.Lock()
        self._move_slot_item_lock = asyncio.Lock()
        self._put_away_lock = asyncio.Lock()
        self._click_window_lock = asyncio.Lock()
        self._transfer_lock = asyncio.Lock()
        self._creative_lock = asyncio.Lock()
        self._register_internal_state_handlers()

    def _reset_state_cache(self) -> None:
        """Discard all cached snapshot values."""
        self._state = _BotStateCache()
        self._window_registry.clear()
        self._recipe_registry.clear()
        self._recipe_counter = 0

    @staticmethod
    def _vec3_from_raw(data: dict[str, float]) -> Vec3:
        return Vec3(x=float(data["x"]), y=float(data["y"]), z=float(data["z"]))

    @staticmethod
    def _experience_from_raw(data: dict[str, object]) -> Experience:
        return Experience(
            level=int(data["level"]),  # type: ignore[arg-type]
            points=int(data["points"]),  # type: ignore[arg-type]
            progress=float(data["progress"]),  # type: ignore[arg-type]
        )

    @staticmethod
    def _game_state_from_raw(data: dict[str, object]) -> GameState:
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

    @staticmethod
    def _time_state_from_raw(data: dict[str, object]) -> TimeState:
        return TimeState(
            time_of_day=int(data["time_of_day"]),  # type: ignore[arg-type]
            day=int(data["day"]),  # type: ignore[arg-type]
            is_day=bool(data["is_day"]),
            moon_phase=int(data["moon_phase"]),  # type: ignore[arg-type]
            age=int(data["age"]),  # type: ignore[arg-type]
            do_daylight_cycle=bool(data["do_daylight_cycle"]),
        )

    def _refresh_connected_state_cache(self) -> None:
        """Refresh connected-state snapshots on the event-loop thread."""
        ctrl = self._controller
        if ctrl is None:
            return
        try:
            self._state.game = self._game_state_from_raw(ctrl.get_game_state())
        except BridgeError:
            pass
        try:
            self._state.time = self._time_state_from_raw(ctrl.get_time())
        except BridgeError:
            pass
        try:
            self._state.rain_state = ctrl.get_rain_state()
        except BridgeError:
            pass
        try:
            self._state.thunder_state = ctrl.get_thunder_state()
        except BridgeError:
            pass
        try:
            self._state.is_sleeping = ctrl.get_is_sleeping()
            self._state.is_sleeping_known = True
        except BridgeError:
            pass
        # Ref: mineflayer/lib/plugins/inventory.js — bot.version (set once at login)
        if self._state.version is None:
            try:
                self._state.version = ctrl.get_version()
            except BridgeError:
                pass
        # Ref: mineflayer/lib/plugins/physics.js — bot.physicsEnabled
        if self._state.physics_enabled is None:
            try:
                self._state.physics_enabled = ctrl.get_physics_enabled()
            except BridgeError:
                pass
        # Ref: mineflayer/docs/api.md — bot.players
        if not self._state.players:
            try:
                raw = ctrl.get_players_full()
                self._state.players = {
                    name: PlayerInfo(
                        username=str(info["username"]),
                        uuid=str(info["uuid"]),
                        ping=int(info["ping"]),  # type: ignore[arg-type]
                        game_mode=int(info["game_mode"]),  # type: ignore[arg-type]
                        display_name=(
                            str(info["display_name"])
                            if info["display_name"] is not None
                            else None
                        ),
                    )
                    for name, info in raw.items()
                }
            except BridgeError:
                pass

    def _refresh_spawn_state_cache(self) -> None:
        """Refresh spawned-state snapshots on the event-loop thread."""
        ctrl = self._controller
        if ctrl is None or not self._spawned:
            return
        self._refresh_connected_state_cache()
        try:
            self._state.position = self._vec3_from_raw(ctrl.get_position())
        except BridgeError:
            pass
        try:
            self._state.health = ctrl.get_health()
            self._state.food = ctrl.get_food()
            self._state.food_saturation = ctrl.get_food_saturation()
        except BridgeError:
            pass
        try:
            self._state.oxygen_level = ctrl.get_oxygen_level()
        except BridgeError:
            pass
        try:
            self._state.experience = self._experience_from_raw(ctrl.get_experience())
        except BridgeError:
            pass
        try:
            js_item = ctrl.get_held_item()
            self._state.held_item = (
                js_item_to_item_stack(js_item) if js_item is not None else None
            )
            self._state.held_item_known = True
        except BridgeError:
            pass
        # Ref: mineflayer/lib/plugins/inventory.js:43 — bot.quickBarSlot
        try:
            self._state.quick_bar_slot = ctrl.get_quick_bar_slot()
        except BridgeError:
            pass

    @staticmethod
    def _require_snapshot(value: Any, name: str) -> Any:
        if value is None:
            raise BridgeError(f"{name} snapshot is not available yet")
        return value

    def _resolve_js_block(self, block: Block) -> Any | None:
        ctrl = self._ensure_connected()
        return ctrl.block_at(
            int(block.position.x),
            int(block.position.y),
            int(block.position.z),
        )

    def _resolve_js_entity(self, entity: Entity) -> Any | None:
        ctrl = self._ensure_connected()
        return ctrl.get_entity_by_id(entity.id)

    def _resolve_item_type(self, item_name: str) -> int:
        ctrl = self._ensure_connected()
        item_type = ctrl.get_item_type(item_name)
        if item_type is None:
            raise ValueError(f"Unknown item name '{item_name}'")
        return item_type

    def _register_internal_state_handlers(self) -> None:
        """Keep sync properties backed by Python-side snapshots."""

        async def _on_spawn(_event: SpawnEvent) -> None:
            self._spawned = True
            if self._controller is not None and self._connected:
                self._refresh_spawn_state_cache()

        async def _on_respawn(_event: RespawnEvent) -> None:
            self._spawned = False

        async def _on_move(event: MoveEvent) -> None:
            self._state.position = event.position

        async def _on_goal_reached(event: GoalReachedEvent) -> None:
            self._state.position = event.position

        async def _on_health(event: HealthChangedEvent) -> None:
            self._state.health = event.health
            self._state.food = event.food
            self._state.food_saturation = event.saturation

        async def _on_breath(event: BreathEvent) -> None:
            self._state.oxygen_level = event.oxygen_level

        async def _on_experience(event: ExperienceEvent) -> None:
            self._state.experience = Experience(
                level=event.level,
                points=event.points,
                progress=event.progress,
            )

        async def _on_held_item(event: HeldItemChangedEvent) -> None:
            self._state.held_item = event.item
            self._state.held_item_known = True
            # quick_bar_slot is read on the JS callback thread and
            # included in the event — no bridge call needed here.
            self._state.quick_bar_slot = event.quick_bar_slot

        async def _on_weather(event: WeatherUpdateEvent) -> None:
            self._state.rain_state = event.rain_state
            self._state.thunder_state = event.thunder_state

        async def _on_rain(event: RainEvent) -> None:
            self._state.rain_state = event.rain_state

        async def _on_time(event: TimeEvent) -> None:
            self._state.time = TimeState(
                time_of_day=event.time_of_day,
                day=event.day,
                is_day=event.is_day,
                moon_phase=event.moon_phase,
                age=event.age,
                do_daylight_cycle=event.do_daylight_cycle,
            )

        async def _on_game(event: GameEvent) -> None:
            self._state.game = GameState(
                game_mode=event.game_mode,
                dimension=event.dimension,
                difficulty=event.difficulty,
                hardcore=event.hardcore,
                max_players=event.max_players,
                server_brand=event.server_brand,
                min_y=event.min_y,
                height=event.height,
            )

        async def _on_sleep(_event: SleepEvent) -> None:
            self._state.is_sleeping = True
            self._state.is_sleeping_known = True

        async def _on_wake(_event: WakeEvent) -> None:
            self._state.is_sleeping = False
            self._state.is_sleeping_known = True

        async def _on_player_joined(event: PlayerJoinedEvent) -> None:
            self._state.players[event.username] = PlayerInfo(
                username=event.username,
                uuid=event.uuid,
                ping=event.ping,
                game_mode=event.game_mode,
                display_name=event.display_name,
            )

        async def _on_player_updated(event: PlayerUpdatedEvent) -> None:
            self._state.players[event.username] = PlayerInfo(
                username=event.username,
                uuid=event.uuid,
                ping=event.ping,
                game_mode=event.game_mode,
                display_name=event.display_name,
            )

        async def _on_player_left(event: PlayerLeftEvent) -> None:
            self._state.players.pop(event.username, None)

        self._relay.add_handler(SpawnEvent, _on_spawn)  # type: ignore[arg-type]
        self._relay.add_handler(RespawnEvent, _on_respawn)  # type: ignore[arg-type]
        self._relay.add_handler(MoveEvent, _on_move)  # type: ignore[arg-type]
        self._relay.add_handler(GoalReachedEvent, _on_goal_reached)  # type: ignore[arg-type]
        self._relay.add_handler(HealthChangedEvent, _on_health)  # type: ignore[arg-type]
        self._relay.add_handler(BreathEvent, _on_breath)  # type: ignore[arg-type]
        self._relay.add_handler(ExperienceEvent, _on_experience)  # type: ignore[arg-type]
        self._relay.add_handler(HeldItemChangedEvent, _on_held_item)  # type: ignore[arg-type]
        self._relay.add_handler(WeatherUpdateEvent, _on_weather)  # type: ignore[arg-type]
        self._relay.add_handler(RainEvent, _on_rain)  # type: ignore[arg-type]
        self._relay.add_handler(TimeEvent, _on_time)  # type: ignore[arg-type]
        self._relay.add_handler(GameEvent, _on_game)  # type: ignore[arg-type]
        self._relay.add_handler(SleepEvent, _on_sleep)  # type: ignore[arg-type]
        self._relay.add_handler(WakeEvent, _on_wake)  # type: ignore[arg-type]
        self._relay.add_handler(PlayerJoinedEvent, _on_player_joined)  # type: ignore[arg-type]
        self._relay.add_handler(PlayerUpdatedEvent, _on_player_updated)  # type: ignore[arg-type]
        self._relay.add_handler(PlayerLeftEvent, _on_player_left)  # type: ignore[arg-type]

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
            self._reset_state_cache()

        self._on_end_handler = _on_end
        self._relay.add_handler(EndEvent, _on_end)  # type: ignore[arg-type]
        self._connected = True
        self._refresh_connected_state_cache()

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
        self._reset_state_cache()

    async def wait_until_spawned(self, timeout: float = 30.0) -> None:
        """Block until the bot has spawned in the world."""
        if self._spawned:
            return
        await self._observe.wait_for(SpawnEvent, timeout=timeout)
        self._spawned = True
        self._refresh_spawn_state_cache()
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
        self._ensure_spawned()
        return self._require_snapshot(self._state.position, "position")

    @property
    def health(self) -> float:
        """Bot health (0-20).

        Raises:
            NotSpawnedError: If ``wait_until_spawned()`` has not completed.
        """
        self._ensure_spawned()
        return self._require_snapshot(self._state.health, "health")

    @property
    def food(self) -> float:
        """Bot food level (0-20).

        Raises:
            NotSpawnedError: If ``wait_until_spawned()`` has not completed.
        """
        self._ensure_spawned()
        return self._require_snapshot(self._state.food, "food")

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
        return self.game.game_mode

    @property
    def players(self) -> dict[str, PlayerInfo]:
        """Online players as ``{username: PlayerInfo}``.

        Backed by event-driven snapshot updated via ``playerJoined``,
        ``playerUpdated``, and ``playerLeft`` events.  Seeded from
        ``bot.players`` at connect time.

        Ref: mineflayer/docs/api.md — bot.players
        """
        self._ensure_connected()
        return dict(self._state.players)

    @property
    def food_saturation(self) -> float:
        """Bot food saturation level.

        Raises:
            NotSpawnedError: If ``wait_until_spawned()`` has not completed.
        """
        self._ensure_spawned()
        return self._require_snapshot(
            self._state.food_saturation,
            "food_saturation",
        )

    @property
    def oxygen_level(self) -> int:
        """Bot oxygen (air supply) level (0-20).

        Defaults to 20 when no metadata has been received yet.

        Raises:
            NotSpawnedError: If ``wait_until_spawned()`` has not completed.
        """
        self._ensure_spawned()
        return self._require_snapshot(self._state.oxygen_level, "oxygen_level")

    @property
    def experience(self) -> Experience:
        """Bot experience state snapshot.

        Raises:
            NotSpawnedError: If ``wait_until_spawned()`` has not completed.
        """
        self._ensure_spawned()
        return self._require_snapshot(self._state.experience, "experience")

    @property
    def game(self) -> GameState:
        """Server game state snapshot."""
        self._ensure_connected()
        return self._require_snapshot(self._state.game, "game")

    @property
    def difficulty(self) -> str:
        """Server difficulty (``"peaceful"``, ``"easy"``, ``"normal"``, ``"hard"``)."""
        return self.game.difficulty

    @property
    def is_raining(self) -> bool:
        """Whether it is currently raining."""
        return self.rain_state > 0.0

    @property
    def thunder_state(self) -> float:
        """Thunder intensity level (0 means no thunder)."""
        self._ensure_connected()
        return self._require_snapshot(self._state.thunder_state, "thunder_state")

    @property
    def time(self) -> TimeState:
        """World time state snapshot."""
        self._ensure_connected()
        return self._require_snapshot(self._state.time, "time")

    @property
    def held_item(self) -> ItemStack | None:
        """Item currently held in the bot's main hand, or ``None``.

        Raises:
            NotSpawnedError: If ``wait_until_spawned()`` has not completed.
        """
        self._ensure_spawned()
        if not self._state.held_item_known:
            raise BridgeError("held_item snapshot is not available yet")
        return self._state.held_item

    @property
    def quick_bar_slot(self) -> int:
        """Currently selected quick bar slot (0-8).

        Backed by snapshot, updated via ``heldItemChanged`` event and setter.

        Ref: mineflayer/lib/plugins/inventory.js:43 — bot.quickBarSlot

        Raises:
            NotSpawnedError: If ``wait_until_spawned()`` has not completed.
        """
        self._ensure_spawned()
        return self._require_snapshot(self._state.quick_bar_slot, "quick_bar_slot")

    @quick_bar_slot.setter
    def quick_bar_slot(self, slot: int) -> None:
        if not (0 <= slot <= 8):
            raise ValueError(f"quick_bar_slot must be 0-8, got {slot}")
        ctrl = self._ensure_spawned()
        ctrl.set_quick_bar_slot(slot)
        self._state.quick_bar_slot = slot

    async def get_spawn_point(self) -> Vec3:
        """Bot spawn point position.

        Ref: mineflayer/lib/plugins/spawn_point.js — bot.spawnPoint

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
        self._ensure_connected()
        if not self._state.is_sleeping_known:
            raise BridgeError("is_sleeping snapshot is not available yet")
        return self._state.is_sleeping

    async def get_target_dig_block(self) -> Block | None:
        """Block currently being dug, or ``None``.

        Ref: mineflayer/lib/plugins/digging.js — bot.targetDigBlock
        """
        ctrl = self._ensure_connected()
        js_block = ctrl.get_target_dig_block()
        if js_block is None:
            return None
        return js_block_to_block(js_block)

    async def get_entity(self) -> Entity:
        """The bot's own entity snapshot.

        Ref: mineflayer/lib/plugins/entities.js — bot.entity

        Raises:
            NotSpawnedError: If ``wait_until_spawned()`` has not completed.
        """
        ctrl = self._ensure_spawned()
        return js_entity_to_entity(ctrl.get_bot_entity())

    async def get_entities(self) -> dict[int, Entity]:
        """All currently tracked entities as ``{entity_id: Entity}``.

        Ref: mineflayer/lib/plugins/entities.js — bot.entities

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
            kind_map = {
                "player": EntityKind.PLAYER,
                "mob": EntityKind.MOB,
                "animal": EntityKind.ANIMAL,
                "hostile": EntityKind.HOSTILE,
                "projectile": EntityKind.PROJECTILE,
                "object": EntityKind.OBJECT,
            }
            kind = (
                kind_map.get(str(etype), EntityKind.OTHER)
                if etype
                else EntityKind.OTHER
            )
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
        """Minecraft version string (e.g. ``"1.20.4"``).

        Backed by one-time snapshot taken at connect (immutable after login).

        Ref: mineflayer/lib/version.js — bot.version
        """
        self._ensure_connected()
        return self._require_snapshot(self._state.version, "version")

    @property
    def physics_enabled(self) -> bool:
        """Whether the physics simulation is active.

        Backed by snapshot, updated via setter.

        Ref: mineflayer/lib/plugins/physics.js — bot.physicsEnabled
        """
        self._ensure_connected()
        return self._require_snapshot(self._state.physics_enabled, "physics_enabled")

    @physics_enabled.setter
    def physics_enabled(self, value: bool) -> None:
        ctrl = self._ensure_connected()
        ctrl.set_physics_enabled(value)
        self._state.physics_enabled = value

    async def get_firework_rocket_duration(self) -> int:
        """Remaining firework rocket boost ticks (0 if not boosting).

        Ref: mineflayer/lib/plugins/physics.js — bot.fireworkRocketDuration
        """
        ctrl = self._ensure_connected()
        return ctrl.get_firework_rocket_duration()

    async def get_tablist(self) -> tuple[str, str]:
        """Tab list ``(header, footer)`` as plain strings.

        Ref: mineflayer/lib/plugins/tablist.js — bot.tablist
        """
        ctrl = self._ensure_connected()
        data = ctrl.get_tablist()
        return (data["header"], data["footer"])

    async def get_using_held_item(self) -> bool:
        """Whether the bot is currently using its held item (e.g. eating).

        Ref: mineflayer/lib/plugins/inventory.js:46 — bot.usingHeldItem
        """
        ctrl = self._ensure_connected()
        return ctrl.get_using_held_item()

    @property
    def rain_state(self) -> float:
        """Rain intensity (0.0 = clear, 1.0 = full rain)."""
        self._ensure_connected()
        return self._require_snapshot(self._state.rain_state, "rain_state")

    async def get_inventory_items(self) -> list[ItemStack]:
        """All items currently in the bot inventory.

        Uses a batch JS helper to avoid per-item bridge round-trips.

        Ref: mineflayer/lib/plugins/inventory.js — bot.inventory.items()
        """
        ctrl = self._ensure_connected()
        result: list[ItemStack] = []
        for raw in ctrl.get_inventory_snapshot():
            enchants = raw.get("enchants")
            nbt = raw.get("nbt")
            result.append(
                ItemStack(
                    name=str(raw["name"]),
                    display_name=str(raw["displayName"])
                    if raw.get("displayName")
                    else str(raw["name"]),
                    count=int(raw["count"]),  # type: ignore[arg-type]
                    slot=int(raw["slot"]),  # type: ignore[arg-type]
                    max_stack_size=int(raw["stackSize"]),  # type: ignore[arg-type]
                    enchantments=list(enchants) if enchants else None,  # type: ignore[arg-type]
                    nbt=dict(nbt) if nbt else None,  # type: ignore[arg-type]
                )
            )
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
            except TimeoutError as exc:
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
                async with self._equip_lock:
                    if not ctrl.start_equip(item_name):
                        raise InventoryError(
                            f"Item '{item_name}' not found in inventory"
                        )
                    try:
                        equip_event = await self._relay.wait_for(
                            EquipDoneEvent, timeout=10.0
                        )
                    except TimeoutError as exc:
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
            except TimeoutError as exc:
                raise BridgeError("place timed out") from exc
            if event.error is not None:
                raise BridgeError(f"place failed: {event.error}")

    async def place_entity(self, reference_block: Block, face: Vec3) -> None:
        """Place an entity (e.g. a boat or minecart) against a block face.

        Args:
            reference_block: The block to place against.
            face: Direction vector for the face (e.g. ``Vec3(0, 1, 0)``).

        Raises:
            MinethonError: If the block is not found.
            BridgeError: If the place operation fails or times out.
        """
        async with self._place_entity_lock:
            ctrl = self._ensure_connected()
            js_block = self._resolve_js_block(reference_block)
            if js_block is None:
                raise MinethonError(f"Block at {reference_block.position} not found")
            ctrl.start_place_entity(js_block, face.x, face.y, face.z)
            try:
                event = await self._relay.wait_for(PlaceEntityDoneEvent, timeout=10.0)
            except TimeoutError as exc:
                raise BridgeError("place_entity timed out") from exc
            if event.error is not None:
                raise BridgeError(f"place_entity failed: {event.error}")

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

    async def goto(self, x: float, y: float, z: float, radius: float = 1.0) -> None:
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
            except TimeoutError as exc:
                raise BridgeError("look_at timed out") from exc
            if event.error is not None:
                raise BridgeError(f"look_at failed: {event.error}")

    async def look(self, yaw: float, pitch: float, *, force: bool = False) -> None:
        """Set head direction by yaw and pitch.

        Args:
            yaw: Horizontal rotation in radians.
            pitch: Vertical rotation in radians.
            force: If ``True``, snap instantly instead of smoothly rotating.

        Raises:
            BridgeError: If the look operation fails or times out.
        """
        async with self._look_lock:
            ctrl = self._ensure_connected()
            ctrl.start_look(yaw, pitch, force)
            try:
                event = await self._relay.wait_for(LookDoneEvent, timeout=10.0)
            except TimeoutError as exc:
                raise BridgeError("look timed out") from exc
            if event.error is not None:
                raise BridgeError(f"look failed: {event.error}")

    async def jump(self) -> None:
        """Make the bot jump once."""
        ctrl = self._ensure_connected()
        ctrl.set_control_state("jump", True)
        try:
            await asyncio.sleep(0.05)  # ~1 game tick (50 ms)
        finally:
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
        plugin_loader = (
            self._plugin_host.raw_plugin if self._plugin_host is not None else None
        )
        return RawBotHandle(
            ctrl.js_bot,
            raw_subscribe=self._observe._on_raw,
            raw_unsubscribe=self._observe._off_raw,
            plugin_loader=plugin_loader,
        )

    @property
    def plugins(self) -> PluginAPI:
        """Plugin management API.

        Exposes only typed, supported plugin operations.
        """
        if self._plugin_host is None:
            raise MinethonConnectionError("Bot is not connected.")
        return PluginAPI(self._plugin_host)

    # -- Sleep / Wake --

    async def sleep(self, bed_block: Block) -> None:
        """Sleep in a bed.

        Args:
            bed_block: The :class:`Block` representing the bed.

        Raises:
            MinethonError: If the bed block is not found at the position.
            BridgeError: If the sleep operation fails or times out.
        """
        async with self._sleep_lock:
            ctrl = self._ensure_spawned()
            js_block = ctrl.block_at(
                int(bed_block.position.x),
                int(bed_block.position.y),
                int(bed_block.position.z),
            )
            if js_block is None:
                raise MinethonError("Bed block not found")
            ctrl.start_sleep(js_block)
            try:
                event = await self._relay.wait_for(SleepDoneEvent, timeout=10.0)
            except TimeoutError as exc:
                raise BridgeError("sleep timed out") from exc
            if event.error is not None:
                raise BridgeError(f"sleep failed: {event.error}")

    async def wake(self) -> None:
        """Wake up from sleeping.

        Raises:
            BridgeError: If the wake operation fails or times out.
        """
        async with self._sleep_lock:
            ctrl = self._ensure_spawned()
            ctrl.start_wake()
            try:
                event = await self._relay.wait_for(WakeDoneEvent, timeout=10.0)
            except TimeoutError as exc:
                raise BridgeError("wake timed out") from exc
            if event.error is not None:
                raise BridgeError(f"wake failed: {event.error}")

    # -- Inventory operations --

    async def equip(self, item_name: str, destination: str = "hand") -> None:
        """Equip an item by name.

        Args:
            item_name: Name of the item to equip (e.g. ``"diamond_sword"``).
            destination: Where to equip (``"hand"``, ``"off-hand"``,
                ``"head"``, ``"torso"``, ``"legs"``, ``"feet"``).

        Raises:
            InventoryError: If the item is not found or equip fails.
        """
        async with self._equip_lock:
            ctrl = self._ensure_connected()
            if not ctrl.start_equip(item_name, destination):
                raise InventoryError(f"Item '{item_name}' not found in inventory")
            try:
                event = await self._relay.wait_for(EquipDoneEvent, timeout=10.0)
            except TimeoutError as exc:
                raise InventoryError("equip timed out") from exc
            if event.error is not None:
                raise InventoryError(f"equip failed: {event.error}")

    async def unequip(self, destination: str) -> None:
        """Unequip an item from a slot.

        Args:
            destination: Slot to unequip (``"hand"``, ``"off-hand"``,
                ``"head"``, ``"torso"``, ``"legs"``, ``"feet"``).

        Raises:
            InventoryError: If the unequip operation fails.
        """
        async with self._unequip_lock:
            ctrl = self._ensure_connected()
            ctrl.start_unequip(destination)
            try:
                event = await self._relay.wait_for(UnequipDoneEvent, timeout=10.0)
            except TimeoutError as exc:
                raise InventoryError("unequip timed out") from exc
            if event.error is not None:
                raise InventoryError(f"unequip failed: {event.error}")

    async def toss(self, item_name: str, count: int | None = None) -> None:
        """Toss items by name.

        Args:
            item_name: Name of the item to toss.
            count: Number of items to toss. ``None`` tosses the whole stack.

        Raises:
            InventoryError: If the item is not found or toss fails.
        """
        async with self._toss_lock:
            ctrl = self._ensure_connected()
            item_type, js_item = ctrl.find_inventory_item_by_name(item_name)
            if js_item is None:
                raise InventoryError(f"Item '{item_name}' not found")
            if count is None:
                ctrl.start_toss_stack(js_item)
                try:
                    event = await self._relay.wait_for(TossStackDoneEvent, timeout=10.0)
                except TimeoutError as exc:
                    raise InventoryError("toss timed out") from exc
                if event.error is not None:
                    raise InventoryError(f"toss failed: {event.error}")
            else:
                ctrl.start_toss(item_type, None, count)
                try:
                    event = await self._relay.wait_for(TossDoneEvent, timeout=10.0)
                except TimeoutError as exc:
                    raise InventoryError("toss timed out") from exc
                if event.error is not None:
                    raise InventoryError(f"toss failed: {event.error}")

    async def set_quick_bar_slot(self, slot: int) -> None:
        """Select a quick bar slot.

        Args:
            slot: Slot index (0-8).
        """
        ctrl = self._ensure_connected()
        ctrl.set_quick_bar_slot(slot)
        self._state.quick_bar_slot = slot

    # -- Actions (extended) --

    async def consume(self) -> None:
        """Eat or drink the currently held item.

        Raises:
            BridgeError: If the consume operation fails or times out.
        """
        async with self._consume_lock:
            ctrl = self._ensure_connected()
            ctrl.start_consume()
            try:
                event = await self._relay.wait_for(ConsumeDoneEvent, timeout=30.0)
            except TimeoutError as exc:
                raise BridgeError("consume timed out") from exc
            if event.error is not None:
                raise BridgeError(f"consume failed: {event.error}")

    async def fish(self) -> None:
        """Cast a fishing rod and wait for a catch.

        Raises:
            BridgeError: If the fish operation fails or times out.
        """
        async with self._fish_lock:
            ctrl = self._ensure_connected()
            ctrl.start_fish()
            try:
                event = await self._relay.wait_for(FishDoneEvent, timeout=120.0)
            except TimeoutError as exc:
                raise BridgeError("fish timed out") from exc
            if event.error is not None:
                raise BridgeError(f"fish failed: {event.error}")

    async def activate_block(self, block: Block) -> None:
        """Activate a block (open door, punch note block, etc.).

        Args:
            block: The :class:`Block` to activate.

        Raises:
            MinethonError: If the block is not found at the position.
            BridgeError: If the activation fails or times out.
        """
        async with self._activate_block_lock:
            ctrl = self._ensure_connected()
            js_block = ctrl.block_at(
                int(block.position.x),
                int(block.position.y),
                int(block.position.z),
            )
            if js_block is None:
                raise MinethonError(f"Block at {block.position} not found")
            ctrl.start_activate_block(js_block)
            try:
                event = await self._relay.wait_for(ActivateBlockDoneEvent, timeout=10.0)
            except TimeoutError as exc:
                raise BridgeError("activate_block timed out") from exc
            if event.error is not None:
                raise BridgeError(f"activate_block failed: {event.error}")

    async def activate_entity(self, entity: Entity) -> None:
        """Activate (right-click) an entity.

        Args:
            entity: The :class:`Entity` to activate.

        Raises:
            BridgeError: If the activation fails or times out.
        """
        async with self._activate_entity_lock:
            ctrl = self._ensure_connected()
            js_entity = ctrl.get_entity_by_id(entity.id)
            if js_entity is None:
                return
            ctrl.start_activate_entity(js_entity)
            try:
                event = await self._relay.wait_for(
                    ActivateEntityDoneEvent, timeout=10.0
                )
            except TimeoutError as exc:
                raise BridgeError("activate_entity timed out") from exc
            if event.error is not None:
                raise BridgeError(f"activate_entity failed: {event.error}")

    async def activate_entity_at(self, entity: Entity, position: Vec3) -> None:
        """Activate an entity at a specific position (e.g. armor stand).

        Args:
            entity: The :class:`Entity` to activate.
            position: World position to click at.

        Raises:
            BridgeError: If the activation fails or times out.
        """
        async with self._activate_entity_at_lock:
            ctrl = self._ensure_connected()
            js_entity = ctrl.get_entity_by_id(entity.id)
            if js_entity is None:
                return
            ctrl.start_activate_entity_at(js_entity, position.x, position.y, position.z)
            try:
                event = await self._relay.wait_for(
                    ActivateEntityAtDoneEvent, timeout=10.0
                )
            except TimeoutError as exc:
                raise BridgeError("activate_entity_at timed out") from exc
            if event.error is not None:
                raise BridgeError(f"activate_entity_at failed: {event.error}")

    async def elytra_fly(self) -> None:
        """Activate elytra flight.

        Raises:
            BridgeError: If the elytra fly activation fails or times out.
        """
        async with self._elytra_fly_lock:
            ctrl = self._ensure_connected()
            ctrl.start_elytra_fly()
            try:
                event = await self._relay.wait_for(ElytraFlyDoneEvent, timeout=10.0)
            except TimeoutError as exc:
                raise BridgeError("elytra_fly timed out") from exc
            if event.error is not None:
                raise BridgeError(f"elytra_fly failed: {event.error}")

    async def swing_arm(self, hand: str = "right") -> None:
        """Swing the bot arm.

        Args:
            hand: ``"right"`` or ``"left"``.
        """
        ctrl = self._ensure_connected()
        ctrl.swing_arm(hand)

    async def deactivate_item(self) -> None:
        """Stop using the currently held item (e.g. stop eating/blocking)."""
        ctrl = self._ensure_connected()
        ctrl.deactivate_item()

    async def use_on(self, entity: Entity) -> None:
        """Use the currently held item on an entity.

        Args:
            entity: The :class:`Entity` to interact with.
        """
        ctrl = self._ensure_connected()
        js_entity = ctrl.get_entity_by_id(entity.id)
        if js_entity is not None:
            ctrl.use_on(js_entity)

    async def mount(self, entity: Entity) -> None:
        """Mount an entity (horse, boat, minecart, etc.).

        Args:
            entity: The :class:`Entity` to mount.
        """
        ctrl = self._ensure_connected()
        js_entity = ctrl.get_entity_by_id(entity.id)
        if js_entity is not None:
            ctrl.mount(js_entity)

    async def dismount(self) -> None:
        """Dismount the currently mounted entity."""
        ctrl = self._ensure_connected()
        ctrl.dismount()

    async def move_vehicle(self, left: float, forward: float) -> None:
        """Move the currently mounted vehicle.

        Args:
            left: Leftward movement (-1.0 to 1.0).
            forward: Forward movement (-1.0 to 1.0).
        """
        ctrl = self._ensure_connected()
        ctrl.move_vehicle(left, forward)

    # -- Crafting --

    async def recipes_for(
        self,
        item_name: str,
        *,
        metadata: int | None = None,
        min_result_count: int | None = None,
        crafting_table: Block | None = None,
    ) -> list[Recipe]:
        """Return craftable recipes for an item name."""
        ctrl = self._ensure_connected()
        item_type = self._resolve_item_type(item_name)
        js_table = self._resolve_js_block(crafting_table) if crafting_table else None
        js_recipes = ctrl.recipes_for(item_type, metadata, min_result_count, js_table)
        return self._register_recipes(js_recipes)

    async def recipes_all(
        self,
        item_name: str,
        *,
        metadata: int | None = None,
        crafting_table: Block | None = None,
    ) -> list[Recipe]:
        """Return all known recipes for an item name regardless of inventory."""
        ctrl = self._ensure_connected()
        item_type = self._resolve_item_type(item_name)
        js_table = self._resolve_js_block(crafting_table) if crafting_table else None
        js_recipes = ctrl.recipes_all(item_type, metadata, js_table)
        return self._register_recipes(js_recipes)

    def _register_recipes(self, js_recipes: list[Any]) -> list[Recipe]:
        """Register JS recipe proxies and return typed handles."""
        result: list[Recipe] = []
        for js_recipe in js_recipes:
            self._recipe_counter += 1
            rid = self._recipe_counter
            self._recipe_registry[rid] = js_recipe
            result.append(Recipe(id=rid))
        return result

    async def open_container(self, target: Block | Entity) -> WindowHandle:
        """Open a generic container and return a typed session handle."""
        async with self._window_lock:
            ctrl = self._ensure_connected()
            js_target = (
                self._resolve_js_block(target)
                if isinstance(target, Block)
                else self._resolve_js_entity(target)
            )
            if js_target is None:
                raise MinethonError("Container target is no longer available")
            ctrl.start_open_container(js_target)
            try:
                event = await self._relay.wait_for(OpenContainerDoneEvent, timeout=10.0)
            except TimeoutError as exc:
                raise BridgeError("open_container timed out") from exc
            if event.error is not None:
                raise BridgeError(f"open_container failed: {event.error}")
            if event.result is None:
                raise BridgeError("open_container returned no window")
            handle = js_window_to_window_handle(event.result)
            self._window_registry[handle.id] = event.result
            return handle

    async def open_furnace(self, block: Block) -> WindowHandle:
        """Open a furnace-like block and return a typed session handle."""
        async with self._window_lock:
            ctrl = self._ensure_connected()
            js_block = self._resolve_js_block(block)
            if js_block is None:
                raise MinethonError(f"Block at {block.position} not found")
            ctrl.start_open_furnace(js_block)
            try:
                event = await self._relay.wait_for(OpenFurnaceDoneEvent, timeout=10.0)
            except TimeoutError as exc:
                raise BridgeError("open_furnace timed out") from exc
            if event.error is not None:
                raise BridgeError(f"open_furnace failed: {event.error}")
            if event.result is None:
                raise BridgeError("open_furnace returned no window")
            handle = js_window_to_window_handle(event.result)
            self._window_registry[handle.id] = event.result
            return handle

    async def open_enchantment_table(self, block: Block) -> WindowHandle:
        """Open an enchantment table and return a typed session handle."""
        async with self._window_lock:
            ctrl = self._ensure_connected()
            js_block = self._resolve_js_block(block)
            if js_block is None:
                raise MinethonError(f"Block at {block.position} not found")
            ctrl.start_open_enchantment_table(js_block)
            try:
                event = await self._relay.wait_for(
                    OpenEnchantmentTableDoneEvent,
                    timeout=10.0,
                )
            except TimeoutError as exc:
                raise BridgeError("open_enchantment_table timed out") from exc
            if event.error is not None:
                raise BridgeError(f"open_enchantment_table failed: {event.error}")
            if event.result is None:
                raise BridgeError("open_enchantment_table returned no window")
            handle = js_window_to_window_handle(event.result)
            self._window_registry[handle.id] = event.result
            return handle

    async def open_anvil(self, block: Block) -> WindowHandle:
        """Open an anvil and return a typed session handle."""
        async with self._window_lock:
            ctrl = self._ensure_connected()
            js_block = self._resolve_js_block(block)
            if js_block is None:
                raise MinethonError(f"Block at {block.position} not found")
            ctrl.start_open_anvil(js_block)
            try:
                event = await self._relay.wait_for(OpenAnvilDoneEvent, timeout=10.0)
            except TimeoutError as exc:
                raise BridgeError("open_anvil timed out") from exc
            if event.error is not None:
                raise BridgeError(f"open_anvil failed: {event.error}")
            if event.result is None:
                raise BridgeError("open_anvil returned no window")
            handle = js_window_to_window_handle(event.result)
            self._window_registry[handle.id] = event.result
            return handle

    async def open_villager(self, villager: Entity) -> VillagerSession:
        """Open a villager trading window and return a typed session."""
        async with self._window_lock:
            ctrl = self._ensure_connected()
            js_villager = self._resolve_js_entity(villager)
            if js_villager is None:
                raise MinethonError(f"Entity {villager.id} not found")
            ctrl.start_open_villager(js_villager)
            try:
                event = await self._relay.wait_for(OpenVillagerDoneEvent, timeout=10.0)
            except TimeoutError as exc:
                raise BridgeError("open_villager timed out") from exc
            if event.error is not None:
                raise BridgeError(f"open_villager failed: {event.error}")
            if event.result is None:
                raise BridgeError("open_villager returned no session")
            ctrl = self._ensure_connected()
            snapshot = ctrl.get_villager_session_snapshot(event.result)
            session = villager_snapshot_to_session(snapshot)
            self._window_registry[session.id] = event.result
            return session

    async def close_window(self, window: WindowHandle | VillagerSession) -> None:
        """Close an open window or villager session."""
        ctrl = self._ensure_connected()
        js_proxy = self._window_registry.pop(window.id, None)
        if js_proxy is None:
            raise BridgeError(
                f"No JS proxy found for window id={window.id} (already closed?)"
            )
        ctrl.close_window(js_proxy)

    async def trade(
        self,
        villager: VillagerSession,
        trade_index: int,
        *,
        times: int = 1,
    ) -> VillagerSession:
        """Execute a villager trade and return the updated session snapshot."""
        async with self._trade_lock:
            ctrl = self._ensure_connected()
            js_proxy = self._window_registry.get(villager.id)
            if js_proxy is None:
                raise BridgeError(
                    f"No JS proxy found for villager session id={villager.id}"
                )
            ctrl.start_trade(js_proxy, trade_index, times)
            try:
                event = await self._relay.wait_for(TradeDoneEvent, timeout=30.0)
            except TimeoutError as exc:
                raise BridgeError("trade timed out") from exc
            if event.error is not None:
                raise BridgeError(f"trade failed: {event.error}")
            snapshot = ctrl.get_villager_session_snapshot(js_proxy)
            session = villager_snapshot_to_session(snapshot)
            self._window_registry[session.id] = js_proxy
            return session

    async def craft(
        self,
        recipe: Recipe,
        count: int = 1,
        crafting_table: Block | None = None,
    ) -> None:
        """Craft items using a recipe.

        Args:
            recipe: A typed recipe handle from :meth:`recipes_for` or
                :meth:`recipes_all`.
            count: Number of times to craft.
            crafting_table: Optional crafting table :class:`Block` for
                3x3 recipes.

        Raises:
            BridgeError: If the craft operation fails or times out.
        """
        async with self._craft_lock:
            ctrl = self._ensure_connected()
            js_table = None
            if crafting_table is not None:
                js_table = self._resolve_js_block(crafting_table)
            js_recipe = self._recipe_registry.get(recipe.id)
            if js_recipe is None:
                raise BridgeError(
                    f"Recipe handle id={recipe.id} is no longer valid "
                    "(stale from a previous session?)"
                )
            ctrl.start_craft(js_recipe, count, js_table)
            try:
                event = await self._relay.wait_for(CraftDoneEvent, timeout=30.0)
            except TimeoutError as exc:
                raise BridgeError("craft timed out") from exc
            if event.error is not None:
                raise BridgeError(f"craft failed: {event.error}")

    async def write_book(self, slot: int, pages: list[str]) -> None:
        """Write text to a book and quill.

        Args:
            slot: Inventory window slot containing the book
                (36 = first quickbar slot).
            pages: List of strings, one per page.

        Raises:
            BridgeError: If the write operation fails or times out.
        """
        async with self._write_book_lock:
            ctrl = self._ensure_connected()
            ctrl.start_write_book(slot, pages)
            try:
                event = await self._relay.wait_for(WriteBookDoneEvent, timeout=30.0)
            except TimeoutError as exc:
                raise BridgeError("write_book timed out") from exc
            if event.error is not None:
                raise BridgeError(f"write_book failed: {event.error}")

    # -- Lower-level inventory --

    async def click_window(self, slot: int, mouse_button: int, mode: int) -> None:
        """Perform a raw window click.

        Args:
            slot: The slot index to click.
            mouse_button: Mouse button (0 = left, 1 = right).
            mode: Click mode (0 = normal click, 1 = shift-click, etc.).

        Raises:
            BridgeError: If the click operation fails or times out.
        """
        async with self._click_window_lock:
            ctrl = self._ensure_connected()
            ctrl.start_click_window(slot, mouse_button, mode)
            try:
                event = await self._relay.wait_for(ClickWindowDoneEvent, timeout=10.0)
            except TimeoutError as exc:
                raise BridgeError("click_window timed out") from exc
            if event.error is not None:
                raise BridgeError(f"click_window failed: {event.error}")

    async def put_away(self, slot: int) -> None:
        """Put the item at the given slot back into the inventory.

        Args:
            slot: The slot index to put away.

        Raises:
            BridgeError: If the operation fails or times out.
        """
        async with self._put_away_lock:
            ctrl = self._ensure_connected()
            ctrl.start_put_away(slot)
            try:
                event = await self._relay.wait_for(PutAwayDoneEvent, timeout=10.0)
            except TimeoutError as exc:
                raise BridgeError("put_away timed out") from exc
            if event.error is not None:
                raise BridgeError(f"put_away failed: {event.error}")

    async def transfer(
        self,
        item_type: int,
        *,
        source_start: int,
        source_end: int,
        dest_start: int,
        dest_end: int | None = None,
        count: int = 1,
    ) -> None:
        """Transfer items between slot ranges in the current window.

        Args:
            item_type: Numeric item type ID.
            source_start: Start of the source slot range.
            source_end: End of the source slot range.
            dest_start: Start of the destination slot range.
            dest_end: End of the destination range (defaults to
                ``dest_start + 1``).
            count: Number of items to transfer.

        Raises:
            BridgeError: If the transfer fails or times out.
        """
        async with self._transfer_lock:
            ctrl = self._ensure_connected()
            options: dict[str, Any] = {
                "itemType": item_type,
                "sourceStart": source_start,
                "sourceEnd": source_end,
                "destStart": dest_start,
                "count": count,
            }
            if dest_end is not None:
                options["destEnd"] = dest_end
            ctrl.start_transfer(options)
            try:
                event = await self._relay.wait_for(TransferDoneEvent, timeout=30.0)
            except TimeoutError as exc:
                raise BridgeError("transfer timed out") from exc
            if event.error is not None:
                raise BridgeError(f"transfer failed: {event.error}")

    async def move_slot_item(self, source_slot: int, dest_slot: int) -> None:
        """Move an item from one slot to another in the current window.

        Args:
            source_slot: Source slot index.
            dest_slot: Destination slot index.

        Raises:
            BridgeError: If the move fails or times out.
        """
        async with self._move_slot_item_lock:
            ctrl = self._ensure_connected()
            ctrl.start_move_slot_item(source_slot, dest_slot)
            try:
                event = await self._relay.wait_for(MoveSlotItemDoneEvent, timeout=10.0)
            except TimeoutError as exc:
                raise BridgeError("move_slot_item timed out") from exc
            if event.error is not None:
                raise BridgeError(f"move_slot_item failed: {event.error}")

    # -- Creative mode --

    async def creative_fly_to(self, destination: Vec3) -> None:
        """Fly to a destination in creative mode.

        Calls ``startFlying()`` internally and moves in a straight line.
        Will not avoid obstacles.

        Args:
            destination: Target position (tip: use ``.5`` for x/z).

        Raises:
            BridgeError: If the fly operation fails or times out.
        """
        async with self._creative_lock:
            ctrl = self._ensure_connected()
            ctrl.start_creative_fly_to(destination.x, destination.y, destination.z)
            try:
                event = await self._relay.wait_for(CreativeFlyToDoneEvent, timeout=30.0)
            except TimeoutError as exc:
                raise BridgeError("creative_fly_to timed out") from exc
            if event.error is not None:
                raise BridgeError(f"creative_fly_to failed: {event.error}")

    async def creative_set_inventory_slot_raw(self, slot: int, item: Any) -> None:
        """**Raw escape hatch.** Set an inventory slot in creative mode.

        This method accepts a raw JS ``prismarine-item`` proxy because
        there is no lossless way to reconstruct one from a Python
        :class:`ItemStack`.  Callers must obtain the item via
        :attr:`Bot.raw` or similar bridge-level access.

        Ref: mineflayer/lib/plugins/creative.js — bot.creative.setInventorySlot()

        Args:
            slot: Inventory window slot (36 = first quickbar slot).
            item: A raw JS ``prismarine-item`` instance, or ``None``
                to clear the slot.

        Raises:
            BridgeError: If the operation fails or times out.
        """
        async with self._creative_lock:
            ctrl = self._ensure_connected()
            ctrl.start_creative_set_inventory_slot(slot, item)
            try:
                event = await self._relay.wait_for(
                    CreativeSetSlotDoneEvent, timeout=10.0
                )
            except TimeoutError as exc:
                raise BridgeError("creative_set_inventory_slot timed out") from exc
            if event.error is not None:
                raise BridgeError(f"creative_set_inventory_slot failed: {event.error}")

    async def creative_clear_slot(self, slot: int) -> None:
        """Clear an inventory slot in creative mode.

        Args:
            slot: Inventory window slot to clear.

        Raises:
            BridgeError: If the operation fails or times out.
        """
        async with self._creative_lock:
            ctrl = self._ensure_connected()
            ctrl.start_creative_clear_slot(slot)
            try:
                event = await self._relay.wait_for(
                    CreativeClearSlotDoneEvent, timeout=10.0
                )
            except TimeoutError as exc:
                raise BridgeError("creative_clear_slot timed out") from exc
            if event.error is not None:
                raise BridgeError(f"creative_clear_slot failed: {event.error}")

    async def creative_clear_inventory(self) -> None:
        """Clear the entire inventory in creative mode.

        Raises:
            BridgeError: If the operation fails or times out.
        """
        async with self._creative_lock:
            ctrl = self._ensure_connected()
            ctrl.start_creative_clear_inventory()
            try:
                event = await self._relay.wait_for(
                    CreativeClearInventoryDoneEvent, timeout=30.0
                )
            except TimeoutError as exc:
                raise BridgeError("creative_clear_inventory timed out") from exc
            if event.error is not None:
                raise BridgeError(f"creative_clear_inventory failed: {event.error}")

    # -- World queries (extended) --

    async def block_at_cursor(self, max_distance: float = 256) -> Block | None:
        """Get the block the bot is currently looking at.

        Args:
            max_distance: Maximum raycast distance.

        Returns:
            A :class:`Block` snapshot, or ``None`` if nothing is in range.
        """
        ctrl = self._ensure_connected()
        js_block = ctrl.block_at_cursor(max_distance)
        return js_block_to_block(js_block) if js_block is not None else None

    async def entity_at_cursor(self, max_distance: float = 3.5) -> Entity | None:
        """Get the entity the bot is currently looking at.

        Args:
            max_distance: Maximum raycast distance.

        Returns:
            An :class:`Entity` snapshot, or ``None``.
        """
        ctrl = self._ensure_connected()
        js_entity = ctrl.entity_at_cursor(max_distance)
        return js_entity_to_entity(js_entity) if js_entity is not None else None

    async def can_dig_block(self, block: Block) -> bool:
        """Check whether the bot can dig the given block.

        Args:
            block: The :class:`Block` to check.

        Returns:
            ``True`` if the block is diggable.
        """
        ctrl = self._ensure_connected()
        js_block = ctrl.block_at(
            int(block.position.x),
            int(block.position.y),
            int(block.position.z),
        )
        return ctrl.can_dig_block(js_block) if js_block is not None else False

    async def can_see_block(self, block: Block) -> bool:
        """Check whether the bot has line-of-sight to the block.

        Args:
            block: The :class:`Block` to check.

        Returns:
            ``True`` if the block is visible.
        """
        ctrl = self._ensure_connected()
        js_block = ctrl.block_at(
            int(block.position.x),
            int(block.position.y),
            int(block.position.z),
        )
        return ctrl.can_see_block(js_block) if js_block is not None else False

    async def dig_time(self, block: Block) -> int:
        """Return the estimated dig time in milliseconds.

        Args:
            block: The :class:`Block` to query.

        Returns:
            Dig time in milliseconds.

        Raises:
            MinethonError: If the block is not found.
        """
        ctrl = self._ensure_connected()
        js_block = ctrl.block_at(
            int(block.position.x),
            int(block.position.y),
            int(block.position.z),
        )
        if js_block is None:
            raise MinethonError(f"Block at {block.position} not found")
        return ctrl.dig_time(js_block)

    async def stop_digging(self) -> None:
        """Cancel the current dig operation."""
        ctrl = self._ensure_connected()
        ctrl.stop_digging()

    async def wait_for_chunks_to_load(self) -> None:
        """Wait until all nearby chunks have been loaded.

        Raises:
            BridgeError: If the operation fails or times out.
        """
        async with self._wait_chunks_lock:
            ctrl = self._ensure_connected()
            ctrl.start_wait_for_chunks_to_load()
            try:
                event = await self._relay.wait_for(ChunksLoadedDoneEvent, timeout=30.0)
            except TimeoutError as exc:
                raise BridgeError("wait_for_chunks timed out") from exc
            if event.error is not None:
                raise BridgeError(f"wait_for_chunks failed: {event.error}")

    async def wait_for_ticks(self, ticks: int) -> None:
        """Wait for a specific number of game ticks.

        Args:
            ticks: Number of ticks to wait (1 tick ~ 50ms).

        Raises:
            BridgeError: If the operation fails or times out.
        """
        async with self._wait_ticks_lock:
            ctrl = self._ensure_connected()
            ctrl.start_wait_for_ticks(ticks)
            try:
                event = await self._relay.wait_for(
                    WaitForTicksDoneEvent,
                    timeout=max(30.0, ticks * 0.05 + 5.0),
                )
            except TimeoutError as exc:
                raise BridgeError("wait_for_ticks timed out") from exc
            if event.error is not None:
                raise BridgeError(f"wait_for_ticks failed: {event.error}")

    # -- Misc --

    async def accept_resource_pack(self) -> None:
        """Accept the server resource pack."""
        ctrl = self._ensure_connected()
        ctrl.accept_resource_pack()

    async def deny_resource_pack(self) -> None:
        """Deny the server resource pack."""
        ctrl = self._ensure_connected()
        ctrl.deny_resource_pack()

    async def set_settings(self, **options: Any) -> None:
        """Update client settings (view distance, skin parts, etc.).

        Args:
            **options: Key-value pairs of settings to update.
        """
        ctrl = self._ensure_connected()
        ctrl.set_settings(options)

    def support_feature(self, name: str) -> bool:
        """Check whether the server supports a protocol feature.

        Args:
            name: Feature name string.

        Returns:
            ``True`` if the feature is supported.
        """
        ctrl = self._ensure_connected()
        return ctrl.support_feature(name)

    async def respawn(self) -> None:
        """Respawn after death."""
        ctrl = self._ensure_connected()
        ctrl.do_respawn()

    async def tab_complete(
        self, text: str, *, assume_command: bool = False
    ) -> list[str]:
        """Request tab-completion suggestions from the server.

        Args:
            text: The partial text to complete.
            assume_command: If ``True``, treat the text as a command
                even without a leading ``/``.

        Returns:
            List of completion suggestions.

        Raises:
            BridgeError: If the tab-complete operation fails.
        """
        async with self._tab_complete_lock:
            ctrl = self._ensure_connected()
            ctrl.start_tab_complete(text, assume_command)
            try:
                event = await self._relay.wait_for(TabCompleteDoneEvent, timeout=10.0)
            except TimeoutError as exc:
                raise BridgeError("tab_complete timed out") from exc
            if event.error is not None:
                raise BridgeError(f"tab_complete failed: {event.error}")
            try:
                if event.result is not None:
                    return [str(item) for item in event.result]
                return []
            except TypeError, ValueError:
                return []

    async def await_message(
        self,
        *patterns: str | re.Pattern[str] | list[str | re.Pattern[str]],
        timeout: float = 30.0,
    ) -> str:
        """Wait for the next chat message matching any exact string or regex."""
        flat_patterns: list[str | re.Pattern[str]] = []
        for pattern in patterns:
            if isinstance(pattern, list):
                flat_patterns.extend(pattern)
            else:
                flat_patterns.append(pattern)
        if not flat_patterns:
            raise ValueError("await_message requires at least one pattern")

        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout
        while True:
            remaining = deadline - loop.time()
            if remaining <= 0:
                raise TimeoutError
            event = await self._observe.wait_for(MessageStrEvent, timeout=remaining)
            for pattern in flat_patterns:
                if isinstance(pattern, str):
                    if event.message == pattern:
                        return event.message
                elif pattern.search(event.message):
                    return event.message
