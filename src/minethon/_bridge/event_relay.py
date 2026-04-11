"""Bridge JS EventEmitter callbacks into asyncio dispatch."""

import asyncio
import logging
import time
from collections import defaultdict
from typing import TYPE_CHECKING, Any

from minethon._bridge._events import (
    ActivateBlockDoneEvent,
    ActivateEntityAtDoneEvent,
    ActivateEntityDoneEvent,
    ArmorEquipDoneEvent,
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
    PanoramaDoneEvent,
    PictureDoneEvent,
    PlaceDoneEvent,
    PlaceEntityDoneEvent,
    PutAwayDoneEvent,
    SimplyShotDoneEvent,
    SleepDoneEvent,
    TabCompleteDoneEvent,
    ToolEquipDoneEvent,
    TossDoneEvent,
    TossStackDoneEvent,
    TradeDoneEvent,
    TransferDoneEvent,
    UnequipDoneEvent,
    ViewerStartDoneEvent,
    WaitForTicksDoneEvent,
    WakeDoneEvent,
    WebInvStartDoneEvent,
    WebInvStopDoneEvent,
    WriteBookDoneEvent,
)
from minethon._bridge.marshalling import js_entity_to_entity, js_item_to_item_stack
from minethon.models.events import (
    ActionBarEvent,
    AutoShotStoppedEvent,
    BlockBreakProgressEndEvent,
    BlockBreakProgressObservedEvent,
    # Block events
    BlockPlacedEvent,
    BlockUpdateEvent,
    # Boss bar
    BossBarCreatedEvent,
    BossBarDeletedEvent,
    BossBarUpdatedEvent,
    # Health & State
    BreathEvent,
    # Lifecycle
    ChatEvent,
    # World events
    ChestLidMoveEvent,
    ChunkColumnLoadEvent,
    ChunkColumnUnloadEvent,
    DeathEvent,
    DiggingAbortedEvent,
    DiggingCompletedEvent,
    # Movement
    DismountEvent,
    EndEvent,
    # Entity events
    EntityAttachEvent,
    EntityAttributesEvent,
    EntityCriticalEffectEvent,
    EntityCrouchEvent,
    EntityDeadEvent,
    EntityDetachEvent,
    EntityEatEvent,
    EntityEatingGrassEvent,
    EntityEffectEndEvent,
    EntityEffectEvent,
    EntityElytraFlewEvent,
    EntityEquipEvent,
    EntityGoneEvent,
    EntityHandSwapEvent,
    EntityHurtEvent,
    EntityMagicCriticalEffectEvent,
    EntityMovedEvent,
    EntityShakingOffWaterEvent,
    EntitySleepEvent,
    EntitySpawnEvent,
    EntitySwingArmEvent,
    EntityTamedEvent,
    EntityTamingEvent,
    EntityUncrouchEvent,
    EntityUpdateEvent,
    EntityWakeEvent,
    ErrorEvent,
    ExperienceEvent,
    ForcedMoveEvent,
    GameEvent,
    GoalFailedEvent,
    GoalReachedEvent,
    # Sound
    HardcodedSoundEffectHeardEvent,
    HealthChangedEvent,
    HeldItemChangedEvent,
    ItemDropEvent,
    KickedEvent,
    LoginEvent,
    MessageEvent,
    MessageStrEvent,
    MountEvent,
    MoveEvent,
    NoteHeardEvent,
    # Physics & Particles
    ParticleEvent,
    PhysicsTickEvent,
    PistonMoveEvent,
    PlayerCollectEvent,
    # Player events
    PlayerJoinedEvent,
    PlayerLeftEvent,
    PlayerUpdatedEvent,
    # Weather & Time
    RainEvent,
    # Resource pack
    ResourcePackEvent,
    RespawnEvent,
    # Scoreboard
    ScoreboardCreatedEvent,
    ScoreboardDeletedEvent,
    ScoreboardPositionEvent,
    ScoreboardTitleChangedEvent,
    ScoreRemovedEvent,
    ScoreUpdatedEvent,
    SleepEvent,
    SoundEffectHeardEvent,
    SpawnEvent,
    SpawnResetEvent,
    # Team
    TeamCreatedEvent,
    TeamMemberAddedEvent,
    TeamMemberRemovedEvent,
    TeamRemovedEvent,
    TeamUpdatedEvent,
    TimeEvent,
    # Title
    TitleClearEvent,
    TitleEvent,
    TitleTimesEvent,
    UsedFireworkEvent,
    WakeEvent,
    WeatherUpdateEvent,
    WhisperEvent,
    # Window
    WindowCloseEvent,
    WindowOpenEvent,
)
from minethon.models.vec3 import Vec3

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine

_log = logging.getLogger(__name__)

_HIGH_FREQ_EVENTS: frozenset[str] = frozenset(
    {
        "physicsTick",
        "entityMoved",
        "entityUpdate",
        "move",
    }
)
_SLOW_HANDLER_THRESHOLD: float = 0.5  # 500ms

# Static events always bound by register_js_events().
_STATIC_BRIDGED_EVENTS: frozenset[str] = frozenset(
    {
        # Lifecycle
        "spawn",
        "login",
        "respawn",
        "game",
        "spawnReset",
        "error",
        # Chat / message
        "chat",
        "whisper",
        "actionBar",
        "message",
        "messagestr",
        # Title
        "title",
        "title_times",
        "title_clear",
        # Health & state
        "health",
        "breath",
        "experience",
        "death",
        "kicked",
        "end",
        "sleep",
        "wake",
        "heldItemChanged",
        # Movement
        "forcedMove",
        "mount",
        "dismount",
        # Navigation
        "goal_reached",
        "path_update",
        "path_stop",
        # Entity events
        "entitySwingArm",
        "entityHurt",
        "entityDead",
        "entityTaming",
        "entityTamed",
        "entityShakingOffWater",
        "entityEatingGrass",
        "entityHandSwap",
        "entityWake",
        "entityEat",
        "entityCriticalEffect",
        "entityMagicCriticalEffect",
        "entityCrouch",
        "entityUncrouch",
        "entityEquip",
        "entitySleep",
        "entitySpawn",
        "entityElytraFlew",
        "entityGone",
        "entityAttach",
        "entityDetach",
        "entityAttributes",
        "entityEffect",
        "entityEffectEnd",
        "itemDrop",
        "playerCollect",
        # Player events
        "playerJoined",
        "playerUpdated",
        "playerLeft",
        # Block events
        "blockUpdate",
        "blockPlaced",
        "chunkColumnLoad",
        "chunkColumnUnload",
        # Digging
        "diggingCompleted",
        "diggingAborted",
        "blockBreakProgressObserved",
        "blockBreakProgressEnd",
        # Sound
        "soundEffectHeard",
        "hardcodedSoundEffectHeard",
        "noteHeard",
        # Weather & time
        "rain",
        "weatherUpdate",
        "time",
        # World events
        "pistonMove",
        "chestLidMove",
        "usedFirework",
        # Window
        "windowOpen",
        "windowClose",
        # Resource pack
        "resourcePack",
        # Scoreboard
        "scoreboardCreated",
        "scoreboardDeleted",
        "scoreboardTitleChanged",
        "scoreUpdated",
        "scoreRemoved",
        "scoreboardPosition",
        # Team
        "teamCreated",
        "teamRemoved",
        "teamUpdated",
        "teamMemberAdded",
        "teamMemberRemoved",
        # Boss bar
        "bossBarCreated",
        "bossBarDeleted",
        "bossBarUpdated",
        # Physics & particles
        "particle",
        # Internal done events
        "_minethon:digDone",
        "_minethon:placeDone",
        "_minethon:equipDone",
        "_minethon:lookAtDone",
        "_minethon:lookDone",
        "_minethon:sleepDone",
        "_minethon:wakeDone",
        "_minethon:unequipDone",
        "_minethon:tossStackDone",
        "_minethon:tossDone",
        "_minethon:consumeDone",
        "_minethon:fishDone",
        "_minethon:elytraFlyDone",
        "_minethon:craftDone",
        "_minethon:activateBlockDone",
        "_minethon:activateEntityDone",
        "_minethon:activateEntityAtDone",
        "_minethon:openContainerDone",
        "_minethon:openFurnaceDone",
        "_minethon:openEnchantmentTableDone",
        "_minethon:openAnvilDone",
        "_minethon:openVillagerDone",
        "_minethon:tradeDone",
        "_minethon:tabCompleteDone",
        "_minethon:writeBookDone",
        "_minethon:chunksLoadedDone",
        "_minethon:waitForTicksDone",
        "_minethon:clickWindowDone",
        "_minethon:transferDone",
        "_minethon:moveSlotItemDone",
        "_minethon:putAwayDone",
        "_minethon:creativeFlyToDone",
        "_minethon:creativeSetSlotDone",
        "_minethon:creativeClearSlotDone",
        "_minethon:creativeClearInventoryDone",
        "_minethon:placeEntityDone",
        "_minethon:armorEquipDone",
        "_minethon:toolEquipDone",
        # Panorama
        "_minethon:panoramaDone",
        "_minethon:pictureDone",
        # HawkEye
        "_minethon:simplyShotDone",
        "auto_shot_stopped",
        # Viewer service
        "_minethon:viewerStartDone",
        # Web inventory service
        "_minethon:webInvStartDone",
        "_minethon:webInvStopDone",
    }
)


class EventRelay:
    """Receives JS events on the JSPyBridge callback thread and
    dispatches them to asyncio handlers via ``call_soon_threadsafe``.
    """

    def __init__(self, event_throttle_ms: dict[str, int] | None = None) -> None:
        self._loop: asyncio.AbstractEventLoop | None = None
        self._handlers: dict[type, list[Callable[..., Coroutine[Any, Any, None]]]] = (
            defaultdict(list)
        )
        self._waiters: dict[type, list[asyncio.Future[Any]]] = defaultdict(list)
        # Raw event handlers keyed by JS event name
        self._raw_handlers: dict[
            str, list[Callable[..., Coroutine[Any, Any, None]]]
        ] = defaultdict(list)
        # Strong refs to prevent GC (JSPyBridge uses WeakValueDictionary)
        self._js_handler_refs: list[Any] = []
        # Per-event throttle: event_name -> interval in seconds
        throttle_cfg = (
            event_throttle_ms
            if event_throttle_ms is not None
            else {"move": 50, "entityMoved": 50, "entityUpdate": 50, "physicsTick": 50}
        )
        self._throttle_intervals: dict[str, float] = {
            name: ms / 1000.0 for name, ms in throttle_cfg.items()
        }
        self._throttle_last_post: dict[str, float] = {}
        # Events actually registered by register_js_events(); used by
        # bind_raw_js_event() to avoid duplicate JS listeners.
        self._registered_events: set[str] = set(_STATIC_BRIDGED_EVENTS)
        # Suppress GoalFailedEvent from path_stop after a successful goal_reached
        self._goal_just_reached: bool = False

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Bind to the running asyncio event loop."""
        self._loop = loop

    def reset(self) -> None:
        """Clean up JS handler references, pending waiters, and loop binding.

        Call on disconnect so that a subsequent ``connect()`` starts
        with a clean slate.  Clearing ``_loop`` ensures that
        ``wait_for()`` raises ``RuntimeError`` (surfaced as
        ``MinethonConnectionError`` by ``ObserveAPI``) when the bot
        is not connected, rather than silently timing out.
        """
        self._js_handler_refs.clear()
        # Cancel all pending waiters
        for waiter_list in self._waiters.values():
            for fut in waiter_list:
                if not fut.done():
                    fut.cancel()
        self._waiters.clear()
        self._throttle_last_post.clear()
        self._goal_just_reached = False
        self._loop = None

    def register_js_events(self, js_bot: Any, on_fn: Any) -> None:  # noqa: C901, PLR0915
        """Register ``@On`` handlers for core mineflayer events.

        Args:
            js_bot: The JS bot proxy from JSBotController.
            on_fn: The ``On`` decorator from JSPyBridge.
        """

        def _stringify_message(value: Any) -> str:
            to_string = getattr(value, "toString", None)
            if callable(to_string):
                return str(to_string())
            return str(value)

        def _vec3_from_js(value: Any) -> Vec3:
            return Vec3(float(value.x), float(value.y), float(value.z))

        def _post_entity_event(
            event_type: type,
            *args: Any,
            include_entity: bool = False,
        ) -> None:
            normalized = self._normalize_js_args(js_bot, args)
            entity = normalized[0] if normalized else None
            if entity is None:
                return
            try:
                payload: dict[str, Any] = {"entity_id": int(entity.id)}
                if include_entity:
                    payload["entity"] = js_entity_to_entity(entity)
                self._post(event_type, event_type(**payload))
            except Exception:
                _log.debug(
                    "Failed to snapshot %s from JS entity payload",
                    event_type.__name__,
                    exc_info=True,
                )

        def _post_player_event(event_type: type, *args: Any) -> None:
            # Ref: mineflayer/docs/api.md — player object has
            # username, uuid, displayName, gamemode, ping, entity.
            normalized = self._normalize_js_args(js_bot, args)
            player = normalized[0] if normalized else None
            if player is None:
                return
            try:
                username = str(player.username)
                if event_type is PlayerLeftEvent:
                    self._post(event_type, PlayerLeftEvent(username=username))
                else:
                    uuid_val = str(player.uuid) if getattr(player, "uuid", None) else ""
                    ping_val = (
                        int(player.ping)
                        if getattr(player, "ping", None) is not None
                        else 0
                    )
                    gm_val = (
                        int(player.gamemode)
                        if getattr(player, "gamemode", None) is not None
                        else 0
                    )
                    dn = getattr(player, "displayName", None)
                    dn_val = str(dn.toString()) if dn is not None else None
                    self._post(
                        event_type,
                        event_type(
                            username=username,
                            uuid=uuid_val,
                            ping=ping_val,
                            game_mode=gm_val,
                            display_name=dn_val,
                        ),
                    )
            except Exception:
                _log.debug(
                    "Failed to snapshot %s from JS player payload",
                    event_type.__name__,
                    exc_info=True,
                )

        def _name_from_proxy(value: Any) -> str:
            return str(value.name) if hasattr(value, "name") else str(value)

        def _post_named_event(event_type: type, field_name: str, *args: Any) -> None:
            normalized = self._normalize_js_args(js_bot, args)
            value = normalized[0] if normalized else None
            if value is None:
                return
            try:
                self._post(
                    event_type,
                    event_type(**{field_name: _name_from_proxy(value)}),
                )
            except Exception:
                _log.debug(
                    "Failed to snapshot %s from JS named payload",
                    event_type.__name__,
                    exc_info=True,
                )

        # ================================================================
        # Lifecycle
        # ================================================================

        @on_fn(js_bot, "spawn")
        def _on_spawn(*_args: Any) -> None:
            self._post(SpawnEvent, SpawnEvent())

        @on_fn(js_bot, "login")
        def _on_login(*_args: Any) -> None:
            self._post(LoginEvent, LoginEvent())

        @on_fn(js_bot, "respawn")
        def _on_respawn(*_args: Any) -> None:
            self._post(RespawnEvent, RespawnEvent())

        @on_fn(js_bot, "game")
        def _on_game(*_args: Any) -> None:
            # Ref: mineflayer/lib/plugins/game.js — bot.game is already
            # updated when this event fires.
            def builder(*_unused: Any) -> GameEvent:
                g = js_bot.game
                return GameEvent(
                    game_mode=str(getattr(g, "gameMode", "unknown") or "unknown"),
                    dimension=str(getattr(g, "dimension", "unknown") or "unknown"),
                    difficulty=str(getattr(g, "difficulty", "unknown") or "unknown"),
                    hardcore=bool(getattr(g, "hardcore", False)),
                    max_players=int(getattr(g, "maxPlayers", 0) or 0),
                    server_brand=str(getattr(g, "serverBrand", "") or ""),
                    min_y=int(getattr(g, "minY", 0) or 0),
                    height=int(getattr(g, "height", 256) or 256),
                )

            self._post_built(js_bot, GameEvent, builder, *_args)

        @on_fn(js_bot, "spawnReset")
        def _on_spawn_reset(*_args: Any) -> None:
            self._post(SpawnResetEvent, SpawnResetEvent())

        @on_fn(js_bot, "error")
        def _on_error(*args: Any) -> None:
            def builder(err: Any | None = None) -> ErrorEvent:
                return ErrorEvent(message=str(err) if err is not None else "unknown")

            self._post_built(js_bot, ErrorEvent, builder, *args)

        @on_fn(js_bot, "death")
        def _on_death(*_args: Any) -> None:
            self._post(DeathEvent, DeathEvent(reason=None))

        @on_fn(js_bot, "kicked")
        def _on_kicked(*args: Any) -> None:
            def builder(
                reason: Any | None = None, logged_in: Any = False
            ) -> KickedEvent:
                return KickedEvent(
                    reason=str(reason) if reason is not None else "unknown",
                    logged_in=bool(logged_in),
                )

            self._post_built(js_bot, KickedEvent, builder, *args)

        @on_fn(js_bot, "end")
        def _on_end(*args: Any) -> None:
            def builder(reason: Any | None = None) -> EndEvent:
                return EndEvent(reason=str(reason) if reason is not None else "unknown")

            self._post_built(js_bot, EndEvent, builder, *args)

        # ================================================================
        # Chat & Messages
        # ================================================================

        @on_fn(js_bot, "chat")
        def _on_chat(*args: Any) -> None:
            def builder(username: Any, message: Any, *_extra: Any) -> ChatEvent:
                return ChatEvent(
                    sender=str(username),
                    message=str(message),
                    timestamp=time.time(),
                )

            self._post_built(js_bot, ChatEvent, builder, *args)

        @on_fn(js_bot, "whisper")
        def _on_whisper(*args: Any) -> None:
            def builder(username: Any, message: Any, *_extra: Any) -> WhisperEvent:
                return WhisperEvent(
                    sender=str(username),
                    message=str(message),
                    timestamp=time.time(),
                )

            self._post_built(js_bot, WhisperEvent, builder, *args)

        @on_fn(js_bot, "actionBar")
        def _on_action_bar(*args: Any) -> None:
            def builder(json_msg: Any, verified: Any | None = None) -> ActionBarEvent:
                return ActionBarEvent(
                    message=_stringify_message(json_msg),
                    verified=None if verified is None else bool(verified),
                )

            self._post_built(js_bot, ActionBarEvent, builder, *args)

        @on_fn(js_bot, "message")
        def _on_message(*args: Any) -> None:
            def builder(
                json_msg: Any,
                position: Any = "chat",
                sender: Any | None = None,
                verified: Any | None = None,
            ) -> MessageEvent:
                return MessageEvent(
                    message=_stringify_message(json_msg),
                    position=str(position),
                    sender=str(sender) if sender is not None else None,
                    verified=None if verified is None else bool(verified),
                )

            self._post_built(js_bot, MessageEvent, builder, *args)

        @on_fn(js_bot, "messagestr")
        def _on_messagestr(*args: Any) -> None:
            def builder(
                message: Any,
                position: Any = "chat",
                _json_msg: Any | None = None,
                sender: Any | None = None,
                verified: Any | None = None,
            ) -> MessageStrEvent:
                return MessageStrEvent(
                    message=str(message),
                    position=str(position),
                    sender=str(sender) if sender is not None else None,
                    verified=None if verified is None else bool(verified),
                )

            self._post_built(js_bot, MessageStrEvent, builder, *args)

        # ================================================================
        # Title
        # ================================================================

        @on_fn(js_bot, "title")
        def _on_title(*args: Any) -> None:
            def builder(text: Any, title_type: Any = "title") -> TitleEvent:
                return TitleEvent(text=_stringify_message(text), type=str(title_type))

            self._post_built(js_bot, TitleEvent, builder, *args)

        @on_fn(js_bot, "title_times")
        def _on_title_times(*args: Any) -> None:
            def builder(fade_in: Any, stay: Any, fade_out: Any) -> TitleTimesEvent:
                return TitleTimesEvent(
                    fade_in=int(fade_in),
                    stay=int(stay),
                    fade_out=int(fade_out),
                )

            self._post_built(js_bot, TitleTimesEvent, builder, *args)

        @on_fn(js_bot, "title_clear")
        def _on_title_clear(*_args: Any) -> None:
            self._post(TitleClearEvent, TitleClearEvent())

        # ================================================================
        # Health & State
        # ================================================================

        @on_fn(js_bot, "health")
        def _on_health(*_args: Any) -> None:
            def builder(*_unused: Any) -> HealthChangedEvent:
                return HealthChangedEvent(
                    health=float(js_bot.health),
                    food=float(js_bot.food),
                    saturation=float(js_bot.foodSaturation),
                )

            self._post_built(js_bot, HealthChangedEvent, builder, *_args)

        @on_fn(js_bot, "breath")
        def _on_breath(*_args: Any) -> None:
            def builder(*_unused: Any) -> BreathEvent:
                return BreathEvent(oxygen_level=int(js_bot.oxygenLevel))

            self._post_built(js_bot, BreathEvent, builder, *_args)

        @on_fn(js_bot, "experience")
        def _on_experience(*_args: Any) -> None:
            def builder(*_unused: Any) -> ExperienceEvent:
                exp = js_bot.experience
                return ExperienceEvent(
                    level=int(exp.level),
                    points=int(exp.points),
                    progress=float(exp.progress),
                )

            self._post_built(js_bot, ExperienceEvent, builder, *_args)

        @on_fn(js_bot, "sleep")
        def _on_sleep(*_args: Any) -> None:
            self._post(SleepEvent, SleepEvent())

        @on_fn(js_bot, "wake")
        def _on_wake(*_args: Any) -> None:
            self._post(WakeEvent, WakeEvent())

        @on_fn(js_bot, "heldItemChanged")
        def _on_held_item_changed(*args: Any) -> None:
            normalized = self._normalize_js_args(js_bot, args)
            held_item = normalized[0] if normalized else None
            try:
                item = None if held_item is None else js_item_to_item_stack(held_item)
                # Read quickBarSlot here on the JS callback thread so the
                # asyncio handler doesn't need a bridge call.
                # Ref: mineflayer/lib/plugins/inventory.js:43 — bot.quickBarSlot
                slot = (
                    int(js_bot.quickBarSlot) if js_bot.quickBarSlot is not None else 0
                )
                self._post(
                    HeldItemChangedEvent,
                    HeldItemChangedEvent(item=item, quick_bar_slot=slot),
                )
            except Exception:
                _log.debug(
                    "Failed to snapshot HeldItemChangedEvent from JS payload",
                    exc_info=True,
                )

        # ================================================================
        # Movement
        # ================================================================

        @on_fn(js_bot, "forcedMove")
        def _on_forced_move(*_args: Any) -> None:
            self._post(ForcedMoveEvent, ForcedMoveEvent())

        @on_fn(js_bot, "mount")
        def _on_mount(*_args: Any) -> None:
            self._post(MountEvent, MountEvent())

        @on_fn(js_bot, "dismount")
        def _on_dismount(*args: Any) -> None:
            def builder(vehicle: Any | None = None) -> DismountEvent:
                vehicle_id = int(vehicle.id) if vehicle is not None else -1
                return DismountEvent(vehicle_id=vehicle_id)

            self._post_built(js_bot, DismountEvent, builder, *args)

        # ================================================================
        # Navigation
        # ================================================================

        @on_fn(js_bot, "goal_reached")
        def _on_goal_reached(*_args: Any) -> None:
            self._goal_just_reached = True

            def builder(*_unused: Any) -> GoalReachedEvent:
                return GoalReachedEvent(position=_vec3_from_js(js_bot.entity.position))

            self._post_built(js_bot, GoalReachedEvent, builder, *_args)

        @on_fn(js_bot, "path_update")
        def _on_path_update(*args: Any) -> None:
            def builder(result: Any) -> GoalFailedEvent | None:
                status = getattr(result, "status", None)
                if status is not None and str(status) == "noPath":
                    return GoalFailedEvent(reason="noPath")
                return None

            self._post_built(js_bot, GoalFailedEvent, builder, *args)

        @on_fn(js_bot, "path_stop")
        def _on_path_stop(*_args: Any) -> None:
            if not self._goal_just_reached:
                self._post(
                    GoalFailedEvent,
                    GoalFailedEvent(reason="stopped"),
                )
            self._goal_just_reached = False

        # ================================================================
        # Entity events (extract entity_id from JS entity proxy)
        # ================================================================

        @on_fn(js_bot, "entitySwingArm")
        def _on_entity_swing_arm(*args: Any) -> None:
            _post_entity_event(EntitySwingArmEvent, *args)

        @on_fn(js_bot, "entityHurt")
        def _on_entity_hurt(*args: Any) -> None:
            _post_entity_event(EntityHurtEvent, *args)

        @on_fn(js_bot, "entityDead")
        def _on_entity_dead(*args: Any) -> None:
            _post_entity_event(EntityDeadEvent, *args)

        @on_fn(js_bot, "entityTaming")
        def _on_entity_taming(*args: Any) -> None:
            _post_entity_event(EntityTamingEvent, *args)

        @on_fn(js_bot, "entityTamed")
        def _on_entity_tamed(*args: Any) -> None:
            _post_entity_event(EntityTamedEvent, *args)

        @on_fn(js_bot, "entityShakingOffWater")
        def _on_entity_shaking_off_water(*args: Any) -> None:
            _post_entity_event(EntityShakingOffWaterEvent, *args)

        @on_fn(js_bot, "entityEatingGrass")
        def _on_entity_eating_grass(*args: Any) -> None:
            _post_entity_event(EntityEatingGrassEvent, *args)

        @on_fn(js_bot, "entityHandSwap")
        def _on_entity_hand_swap(*args: Any) -> None:
            _post_entity_event(EntityHandSwapEvent, *args)

        @on_fn(js_bot, "entityWake")
        def _on_entity_wake(*args: Any) -> None:
            _post_entity_event(EntityWakeEvent, *args)

        @on_fn(js_bot, "entityEat")
        def _on_entity_eat(*args: Any) -> None:
            _post_entity_event(EntityEatEvent, *args)

        @on_fn(js_bot, "entityCriticalEffect")
        def _on_entity_critical_effect(*args: Any) -> None:
            _post_entity_event(EntityCriticalEffectEvent, *args)

        @on_fn(js_bot, "entityMagicCriticalEffect")
        def _on_entity_magic_critical_effect(*args: Any) -> None:
            _post_entity_event(EntityMagicCriticalEffectEvent, *args)

        @on_fn(js_bot, "entityCrouch")
        def _on_entity_crouch(*args: Any) -> None:
            _post_entity_event(EntityCrouchEvent, *args)

        @on_fn(js_bot, "entityUncrouch")
        def _on_entity_uncrouch(*args: Any) -> None:
            _post_entity_event(EntityUncrouchEvent, *args)

        @on_fn(js_bot, "entityEquip")
        def _on_entity_equip(*args: Any) -> None:
            _post_entity_event(EntityEquipEvent, *args)

        @on_fn(js_bot, "entitySleep")
        def _on_entity_sleep(*args: Any) -> None:
            _post_entity_event(EntitySleepEvent, *args)

        @on_fn(js_bot, "entitySpawn")
        def _on_entity_spawn(*args: Any) -> None:
            _post_entity_event(EntitySpawnEvent, *args, include_entity=True)

        @on_fn(js_bot, "entityElytraFlew")
        def _on_entity_elytra_flew(*args: Any) -> None:
            _post_entity_event(EntityElytraFlewEvent, *args)

        @on_fn(js_bot, "entityGone")
        def _on_entity_gone(*args: Any) -> None:
            _post_entity_event(EntityGoneEvent, *args)

        @on_fn(js_bot, "entityAttach")
        def _on_entity_attach(*args: Any) -> None:
            def builder(entity: Any, vehicle: Any) -> EntityAttachEvent:
                return EntityAttachEvent(
                    entity_id=int(entity.id),
                    vehicle_id=int(vehicle.id),
                )

            self._post_built(js_bot, EntityAttachEvent, builder, *args)

        @on_fn(js_bot, "entityDetach")
        def _on_entity_detach(*args: Any) -> None:
            def builder(entity: Any, vehicle: Any) -> EntityDetachEvent:
                return EntityDetachEvent(
                    entity_id=int(entity.id),
                    vehicle_id=int(vehicle.id),
                )

            self._post_built(js_bot, EntityDetachEvent, builder, *args)

        @on_fn(js_bot, "entityAttributes")
        def _on_entity_attributes(*args: Any) -> None:
            _post_entity_event(EntityAttributesEvent, *args)

        @on_fn(js_bot, "entityEffect")
        def _on_entity_effect(*args: Any) -> None:
            def builder(entity: Any, effect: Any | None = None) -> EntityEffectEvent:
                return EntityEffectEvent(
                    entity_id=int(entity.id),
                    effect_id=int(effect.id) if effect is not None else -1,
                    amplifier=int(effect.amplifier) if effect is not None else 0,
                    duration=int(effect.duration) if effect is not None else 0,
                )

            self._post_built(js_bot, EntityEffectEvent, builder, *args)

        @on_fn(js_bot, "entityEffectEnd")
        def _on_entity_effect_end(*args: Any) -> None:
            def builder(entity: Any, effect: Any | None = None) -> EntityEffectEndEvent:
                return EntityEffectEndEvent(
                    entity_id=int(entity.id),
                    effect_id=int(effect.id) if effect is not None else -1,
                )

            self._post_built(js_bot, EntityEffectEndEvent, builder, *args)

        @on_fn(js_bot, "itemDrop")
        def _on_item_drop(*args: Any) -> None:
            _post_entity_event(ItemDropEvent, *args)

        @on_fn(js_bot, "playerCollect")
        def _on_player_collect(*args: Any) -> None:
            def builder(collector: Any, collected: Any) -> PlayerCollectEvent:
                return PlayerCollectEvent(
                    collector_id=int(collector.id),
                    collected_id=int(collected.id),
                )

            self._post_built(js_bot, PlayerCollectEvent, builder, *args)

        # ================================================================
        # Player events
        # ================================================================

        @on_fn(js_bot, "playerJoined")
        def _on_player_joined(*args: Any) -> None:
            _post_player_event(PlayerJoinedEvent, *args)

        @on_fn(js_bot, "playerUpdated")
        def _on_player_updated(*args: Any) -> None:
            _post_player_event(PlayerUpdatedEvent, *args)

        @on_fn(js_bot, "playerLeft")
        def _on_player_left(*args: Any) -> None:
            _post_player_event(PlayerLeftEvent, *args)

        # ================================================================
        # Block events
        # ================================================================

        @on_fn(js_bot, "blockUpdate")
        def _on_block_update(*args: Any) -> None:
            def builder(
                old_b: Any | None, new_b: Any | None
            ) -> BlockUpdateEvent | None:
                pos = (
                    new_b.position
                    if new_b is not None
                    else (old_b.position if old_b is not None else None)
                )
                if pos is None:
                    return None
                return BlockUpdateEvent(
                    position=_vec3_from_js(pos),
                    old_block_name=str(old_b.name) if old_b is not None else None,
                    new_block_name=str(new_b.name) if new_b is not None else None,
                )

            self._post_built(js_bot, BlockUpdateEvent, builder, *args)

        @on_fn(js_bot, "blockPlaced")
        def _on_block_placed(*args: Any) -> None:
            def builder(
                old_b: Any | None, new_b: Any | None
            ) -> BlockPlacedEvent | None:
                pos = (
                    new_b.position
                    if new_b is not None
                    else (old_b.position if old_b is not None else None)
                )
                if pos is None:
                    return None
                return BlockPlacedEvent(
                    position=_vec3_from_js(pos),
                    old_block_name=str(old_b.name) if old_b is not None else None,
                    new_block_name=str(new_b.name) if new_b is not None else None,
                )

            self._post_built(js_bot, BlockPlacedEvent, builder, *args)

        @on_fn(js_bot, "chunkColumnLoad")
        def _on_chunk_column_load(*args: Any) -> None:
            def builder(point: Any) -> ChunkColumnLoadEvent:
                return ChunkColumnLoadEvent(
                    position=Vec3(float(point.x), 0.0, float(point.z)),
                )

            self._post_built(js_bot, ChunkColumnLoadEvent, builder, *args)

        @on_fn(js_bot, "chunkColumnUnload")
        def _on_chunk_column_unload(*args: Any) -> None:
            def builder(point: Any) -> ChunkColumnUnloadEvent:
                return ChunkColumnUnloadEvent(
                    position=Vec3(float(point.x), 0.0, float(point.z)),
                )

            self._post_built(js_bot, ChunkColumnUnloadEvent, builder, *args)

        # ================================================================
        # Digging
        # ================================================================

        @on_fn(js_bot, "diggingCompleted")
        def _on_digging_completed(*args: Any) -> None:
            def builder(block: Any) -> DiggingCompletedEvent:
                return DiggingCompletedEvent(
                    position=_vec3_from_js(block.position),
                    block_name=str(block.name),
                )

            self._post_built(js_bot, DiggingCompletedEvent, builder, *args)

        @on_fn(js_bot, "diggingAborted")
        def _on_digging_aborted(*args: Any) -> None:
            def builder(block: Any) -> DiggingAbortedEvent:
                return DiggingAbortedEvent(
                    position=_vec3_from_js(block.position),
                    block_name=str(block.name),
                )

            self._post_built(js_bot, DiggingAbortedEvent, builder, *args)

        @on_fn(js_bot, "blockBreakProgressObserved")
        def _on_block_break_progress_observed(*args: Any) -> None:
            def builder(
                block: Any,
                destroy_stage: Any,
                entity: Any | None = None,
            ) -> BlockBreakProgressObservedEvent:
                return BlockBreakProgressObservedEvent(
                    position=_vec3_from_js(block.position),
                    destroy_stage=int(destroy_stage),
                    entity_id=int(entity.id) if entity is not None else -1,
                )

            self._post_built(js_bot, BlockBreakProgressObservedEvent, builder, *args)

        @on_fn(js_bot, "blockBreakProgressEnd")
        def _on_block_break_progress_end(*args: Any) -> None:
            def builder(
                block: Any, entity: Any | None = None
            ) -> BlockBreakProgressEndEvent:
                return BlockBreakProgressEndEvent(
                    position=_vec3_from_js(block.position),
                    entity_id=int(entity.id) if entity is not None else -1,
                )

            self._post_built(js_bot, BlockBreakProgressEndEvent, builder, *args)

        # ================================================================
        # Sound
        # ================================================================

        @on_fn(js_bot, "soundEffectHeard")
        def _on_sound_effect_heard(*args: Any) -> None:
            def builder(
                sound_name: Any,
                position: Any,
                volume: Any,
                pitch: Any,
            ) -> SoundEffectHeardEvent:
                return SoundEffectHeardEvent(
                    sound_name=str(sound_name),
                    position=_vec3_from_js(position),
                    volume=float(volume),
                    pitch=float(pitch),
                )

            self._post_built(js_bot, SoundEffectHeardEvent, builder, *args)

        @on_fn(js_bot, "hardcodedSoundEffectHeard")
        def _on_hardcoded_sound_effect_heard(*args: Any) -> None:
            def builder(
                sound_id: Any,
                sound_category: Any,
                position: Any,
                volume: Any,
                pitch: Any,
            ) -> HardcodedSoundEffectHeardEvent:
                return HardcodedSoundEffectHeardEvent(
                    sound_id=int(sound_id),
                    sound_category=int(sound_category),
                    position=_vec3_from_js(position),
                    volume=float(volume),
                    pitch=float(pitch),
                )

            self._post_built(js_bot, HardcodedSoundEffectHeardEvent, builder, *args)

        @on_fn(js_bot, "noteHeard")
        def _on_note_heard(*args: Any) -> None:
            def builder(block: Any, instrument: Any, pitch: Any = 0) -> NoteHeardEvent:
                instrument_id = (
                    int(instrument.id) if hasattr(instrument, "id") else int(instrument)
                )
                return NoteHeardEvent(
                    position=_vec3_from_js(block.position),
                    instrument_id=instrument_id,
                    pitch=int(pitch),
                )

            self._post_built(js_bot, NoteHeardEvent, builder, *args)

        # ================================================================
        # Weather & Time
        # ================================================================

        @on_fn(js_bot, "rain")
        def _on_rain(*_args: Any) -> None:
            # Ref: mineflayer/lib/plugins/rain.js — bot.rainState is
            # already updated when this event fires.
            def builder(*_unused: Any) -> RainEvent:
                return RainEvent(rain_state=float(js_bot.rainState))

            self._post_built(js_bot, RainEvent, builder, *_args)

        @on_fn(js_bot, "weatherUpdate")
        def _on_weather_update(*_args: Any) -> None:
            def builder(*_unused: Any) -> WeatherUpdateEvent:
                return WeatherUpdateEvent(
                    rain_state=float(js_bot.rainState),
                    thunder_state=float(js_bot.thunderState),
                )

            self._post_built(js_bot, WeatherUpdateEvent, builder, *_args)

        @on_fn(js_bot, "time")
        def _on_time(*_args: Any) -> None:
            # Ref: mineflayer/lib/plugins/time.js — all bot.time fields
            # are updated before emit('time').
            def builder(*_unused: Any) -> TimeEvent:
                t = js_bot.time
                return TimeEvent(
                    time_of_day=int(t.timeOfDay),
                    day=int(t.day),
                    is_day=bool(t.isDay),
                    moon_phase=int(t.moonPhase),
                    age=int(t.age),
                    do_daylight_cycle=bool(t.doDaylightCycle),
                )

            self._post_built(js_bot, TimeEvent, builder, *_args)

        # ================================================================
        # World events
        # ================================================================

        @on_fn(js_bot, "pistonMove")
        def _on_piston_move(*args: Any) -> None:
            def builder(block: Any, is_pulling: Any, direction: Any) -> PistonMoveEvent:
                return PistonMoveEvent(
                    position=_vec3_from_js(block.position),
                    is_pulling=bool(is_pulling),
                    direction=int(direction),
                )

            self._post_built(js_bot, PistonMoveEvent, builder, *args)

        @on_fn(js_bot, "chestLidMove")
        def _on_chest_lid_move(*args: Any) -> None:
            def builder(block: Any, is_open: Any, *_extra: Any) -> ChestLidMoveEvent:
                return ChestLidMoveEvent(
                    position=_vec3_from_js(block.position),
                    is_open=int(is_open),
                )

            self._post_built(js_bot, ChestLidMoveEvent, builder, *args)

        @on_fn(js_bot, "usedFirework")
        def _on_used_firework(*args: Any) -> None:
            def builder(firework: Any) -> UsedFireworkEvent:
                firework_id = (
                    int(firework.id) if hasattr(firework, "id") else int(firework)
                )
                return UsedFireworkEvent(firework_entity_id=firework_id)

            self._post_built(js_bot, UsedFireworkEvent, builder, *args)

        # ================================================================
        # Window
        # ================================================================

        @on_fn(js_bot, "windowOpen")
        def _on_window_open(*args: Any) -> None:
            def builder(window: Any) -> WindowOpenEvent:
                return WindowOpenEvent(
                    window_id=int(window.id) if hasattr(window, "id") else 0,
                )

            self._post_built(js_bot, WindowOpenEvent, builder, *args)

        @on_fn(js_bot, "windowClose")
        def _on_window_close(*args: Any) -> None:
            def builder(window: Any) -> WindowCloseEvent:
                return WindowCloseEvent(
                    window_id=int(window.id) if hasattr(window, "id") else 0,
                )

            self._post_built(js_bot, WindowCloseEvent, builder, *args)

        # ================================================================
        # Resource pack
        # ================================================================

        @on_fn(js_bot, "resourcePack")
        def _on_resource_pack(*args: Any) -> None:
            def builder(url: Any, hash_value: Any = "") -> ResourcePackEvent:
                return ResourcePackEvent(url=str(url), hash=str(hash_value))

            self._post_built(js_bot, ResourcePackEvent, builder, *args)

        # ================================================================
        # Scoreboard
        # ================================================================

        @on_fn(js_bot, "scoreboardCreated")
        def _on_scoreboard_created(*args: Any) -> None:
            _post_named_event(ScoreboardCreatedEvent, "name", *args)

        @on_fn(js_bot, "scoreboardDeleted")
        def _on_scoreboard_deleted(*args: Any) -> None:
            _post_named_event(ScoreboardDeletedEvent, "name", *args)

        @on_fn(js_bot, "scoreboardTitleChanged")
        def _on_scoreboard_title_changed(*args: Any) -> None:
            _post_named_event(ScoreboardTitleChangedEvent, "name", *args)

        @on_fn(js_bot, "scoreUpdated")
        def _on_score_updated(*args: Any) -> None:
            def builder(scoreboard: Any, item: Any) -> ScoreUpdatedEvent:
                return ScoreUpdatedEvent(
                    scoreboard_name=_name_from_proxy(scoreboard),
                    item_name=_name_from_proxy(item),
                    value=int(item.value) if hasattr(item, "value") else 0,
                )

            self._post_built(js_bot, ScoreUpdatedEvent, builder, *args)

        @on_fn(js_bot, "scoreRemoved")
        def _on_score_removed(*args: Any) -> None:
            def builder(scoreboard: Any, item: Any) -> ScoreRemovedEvent:
                return ScoreRemovedEvent(
                    scoreboard_name=_name_from_proxy(scoreboard),
                    item_name=_name_from_proxy(item),
                )

            self._post_built(js_bot, ScoreRemovedEvent, builder, *args)

        @on_fn(js_bot, "scoreboardPosition")
        def _on_scoreboard_position(*args: Any) -> None:
            def builder(position: Any, scoreboard: Any) -> ScoreboardPositionEvent:
                return ScoreboardPositionEvent(
                    position=int(position),
                    scoreboard_name=_name_from_proxy(scoreboard),
                )

            self._post_built(js_bot, ScoreboardPositionEvent, builder, *args)

        # ================================================================
        # Team
        # ================================================================

        @on_fn(js_bot, "teamCreated")
        def _on_team_created(*args: Any) -> None:
            _post_named_event(TeamCreatedEvent, "name", *args)

        @on_fn(js_bot, "teamRemoved")
        def _on_team_removed(*args: Any) -> None:
            _post_named_event(TeamRemovedEvent, "name", *args)

        @on_fn(js_bot, "teamUpdated")
        def _on_team_updated(*args: Any) -> None:
            _post_named_event(TeamUpdatedEvent, "name", *args)

        @on_fn(js_bot, "teamMemberAdded")
        def _on_team_member_added(*args: Any) -> None:
            _post_named_event(TeamMemberAddedEvent, "team_name", *args)

        @on_fn(js_bot, "teamMemberRemoved")
        def _on_team_member_removed(*args: Any) -> None:
            _post_named_event(TeamMemberRemovedEvent, "team_name", *args)

        # ================================================================
        # Boss bar
        # ================================================================

        @on_fn(js_bot, "bossBarCreated")
        def _on_boss_bar_created(*args: Any) -> None:
            def builder(bar: Any) -> BossBarCreatedEvent:
                return BossBarCreatedEvent(
                    entity_uuid=str(bar.entityUUID)
                    if hasattr(bar, "entityUUID")
                    else str(bar),
                    title=_stringify_message(bar.title)
                    if hasattr(bar, "title")
                    else "",
                    health=float(bar.health) if hasattr(bar, "health") else 0.0,
                )

            self._post_built(js_bot, BossBarCreatedEvent, builder, *args)

        @on_fn(js_bot, "bossBarDeleted")
        def _on_boss_bar_deleted(*args: Any) -> None:
            def builder(bar: Any) -> BossBarDeletedEvent:
                return BossBarDeletedEvent(
                    entity_uuid=str(bar.entityUUID)
                    if hasattr(bar, "entityUUID")
                    else str(bar),
                )

            self._post_built(js_bot, BossBarDeletedEvent, builder, *args)

        @on_fn(js_bot, "bossBarUpdated")
        def _on_boss_bar_updated(*args: Any) -> None:
            def builder(bar: Any) -> BossBarUpdatedEvent:
                return BossBarUpdatedEvent(
                    entity_uuid=str(bar.entityUUID)
                    if hasattr(bar, "entityUUID")
                    else str(bar),
                    title=_stringify_message(bar.title)
                    if hasattr(bar, "title")
                    else "",
                    health=float(bar.health) if hasattr(bar, "health") else 0.0,
                )

            self._post_built(js_bot, BossBarUpdatedEvent, builder, *args)

        # ================================================================
        # Physics & Particles
        # ================================================================

        @on_fn(js_bot, "particle")
        def _on_particle(*args: Any) -> None:
            def builder(particle: Any) -> ParticleEvent:
                position = (
                    particle.position if hasattr(particle, "position") else particle
                )
                return ParticleEvent(
                    particle_id=int(particle.id) if hasattr(particle, "id") else 0,
                    particle_name=str(particle.name)
                    if hasattr(particle, "name")
                    else "",
                    position=_vec3_from_js(position),
                    count=int(particle.count) if hasattr(particle, "count") else 1,
                )

            self._post_built(js_bot, ParticleEvent, builder, *args)

        # ================================================================
        # Internal async-operation completion events (void pattern)
        # ================================================================

        @on_fn(js_bot, "_minethon:digDone")
        def _on_dig_done(*args: Any) -> None:
            def builder(error: Any | None = None) -> DigDoneEvent:
                return DigDoneEvent(error=str(error) if error is not None else None)

            self._post_built(js_bot, DigDoneEvent, builder, *args)

        @on_fn(js_bot, "_minethon:placeDone")
        def _on_place_done(*args: Any) -> None:
            def builder(error: Any | None = None) -> PlaceDoneEvent:
                return PlaceDoneEvent(error=str(error) if error is not None else None)

            self._post_built(js_bot, PlaceDoneEvent, builder, *args)

        @on_fn(js_bot, "_minethon:equipDone")
        def _on_equip_done(*args: Any) -> None:
            def builder(error: Any | None = None) -> EquipDoneEvent:
                return EquipDoneEvent(error=str(error) if error is not None else None)

            self._post_built(js_bot, EquipDoneEvent, builder, *args)

        @on_fn(js_bot, "_minethon:lookAtDone")
        def _on_look_at_done(*args: Any) -> None:
            def builder(error: Any | None = None) -> LookAtDoneEvent:
                return LookAtDoneEvent(error=str(error) if error is not None else None)

            self._post_built(js_bot, LookAtDoneEvent, builder, *args)

        @on_fn(js_bot, "_minethon:lookDone")
        def _on_look_done(*args: Any) -> None:
            def builder(error: Any | None = None) -> LookDoneEvent:
                return LookDoneEvent(error=str(error) if error is not None else None)

            self._post_built(js_bot, LookDoneEvent, builder, *args)

        @on_fn(js_bot, "_minethon:sleepDone")
        def _on_sleep_done(*args: Any) -> None:
            def builder(error: Any | None = None) -> SleepDoneEvent:
                return SleepDoneEvent(error=str(error) if error is not None else None)

            self._post_built(js_bot, SleepDoneEvent, builder, *args)

        @on_fn(js_bot, "_minethon:wakeDone")
        def _on_wake_done(*args: Any) -> None:
            def builder(error: Any | None = None) -> WakeDoneEvent:
                return WakeDoneEvent(error=str(error) if error is not None else None)

            self._post_built(js_bot, WakeDoneEvent, builder, *args)

        @on_fn(js_bot, "_minethon:unequipDone")
        def _on_unequip_done(*args: Any) -> None:
            def builder(error: Any | None = None) -> UnequipDoneEvent:
                return UnequipDoneEvent(error=str(error) if error is not None else None)

            self._post_built(js_bot, UnequipDoneEvent, builder, *args)

        @on_fn(js_bot, "_minethon:tossStackDone")
        def _on_toss_stack_done(*args: Any) -> None:
            def builder(error: Any | None = None) -> TossStackDoneEvent:
                return TossStackDoneEvent(
                    error=str(error) if error is not None else None
                )

            self._post_built(js_bot, TossStackDoneEvent, builder, *args)

        @on_fn(js_bot, "_minethon:tossDone")
        def _on_toss_done(*args: Any) -> None:
            def builder(error: Any | None = None) -> TossDoneEvent:
                return TossDoneEvent(error=str(error) if error is not None else None)

            self._post_built(js_bot, TossDoneEvent, builder, *args)

        @on_fn(js_bot, "_minethon:consumeDone")
        def _on_consume_done(*args: Any) -> None:
            def builder(error: Any | None = None) -> ConsumeDoneEvent:
                return ConsumeDoneEvent(error=str(error) if error is not None else None)

            self._post_built(js_bot, ConsumeDoneEvent, builder, *args)

        @on_fn(js_bot, "_minethon:fishDone")
        def _on_fish_done(*args: Any) -> None:
            def builder(error: Any | None = None) -> FishDoneEvent:
                return FishDoneEvent(error=str(error) if error is not None else None)

            self._post_built(js_bot, FishDoneEvent, builder, *args)

        @on_fn(js_bot, "_minethon:elytraFlyDone")
        def _on_elytra_fly_done(*args: Any) -> None:
            def builder(error: Any | None = None) -> ElytraFlyDoneEvent:
                return ElytraFlyDoneEvent(
                    error=str(error) if error is not None else None
                )

            self._post_built(js_bot, ElytraFlyDoneEvent, builder, *args)

        @on_fn(js_bot, "_minethon:craftDone")
        def _on_craft_done(*args: Any) -> None:
            def builder(error: Any | None = None) -> CraftDoneEvent:
                return CraftDoneEvent(error=str(error) if error is not None else None)

            self._post_built(js_bot, CraftDoneEvent, builder, *args)

        @on_fn(js_bot, "_minethon:activateBlockDone")
        def _on_activate_block_done(*args: Any) -> None:
            def builder(error: Any | None = None) -> ActivateBlockDoneEvent:
                return ActivateBlockDoneEvent(
                    error=str(error) if error is not None else None
                )

            self._post_built(js_bot, ActivateBlockDoneEvent, builder, *args)

        @on_fn(js_bot, "_minethon:activateEntityDone")
        def _on_activate_entity_done(*args: Any) -> None:
            def builder(error: Any | None = None) -> ActivateEntityDoneEvent:
                return ActivateEntityDoneEvent(
                    error=str(error) if error is not None else None
                )

            self._post_built(js_bot, ActivateEntityDoneEvent, builder, *args)

        @on_fn(js_bot, "_minethon:activateEntityAtDone")
        def _on_activate_entity_at_done(*args: Any) -> None:
            def builder(error: Any | None = None) -> ActivateEntityAtDoneEvent:
                return ActivateEntityAtDoneEvent(
                    error=str(error) if error is not None else None
                )

            self._post_built(js_bot, ActivateEntityAtDoneEvent, builder, *args)

        @on_fn(js_bot, "_minethon:tradeDone")
        def _on_trade_done(*args: Any) -> None:
            def builder(error: Any | None = None) -> TradeDoneEvent:
                return TradeDoneEvent(error=str(error) if error is not None else None)

            self._post_built(js_bot, TradeDoneEvent, builder, *args)

        @on_fn(js_bot, "_minethon:writeBookDone")
        def _on_write_book_done(*args: Any) -> None:
            def builder(error: Any | None = None) -> WriteBookDoneEvent:
                return WriteBookDoneEvent(
                    error=str(error) if error is not None else None
                )

            self._post_built(js_bot, WriteBookDoneEvent, builder, *args)

        @on_fn(js_bot, "_minethon:chunksLoadedDone")
        def _on_chunks_loaded_done(*args: Any) -> None:
            def builder(error: Any | None = None) -> ChunksLoadedDoneEvent:
                return ChunksLoadedDoneEvent(
                    error=str(error) if error is not None else None
                )

            self._post_built(js_bot, ChunksLoadedDoneEvent, builder, *args)

        @on_fn(js_bot, "_minethon:waitForTicksDone")
        def _on_wait_for_ticks_done(*args: Any) -> None:
            def builder(error: Any | None = None) -> WaitForTicksDoneEvent:
                return WaitForTicksDoneEvent(
                    error=str(error) if error is not None else None
                )

            self._post_built(js_bot, WaitForTicksDoneEvent, builder, *args)

        @on_fn(js_bot, "_minethon:clickWindowDone")
        def _on_click_window_done(*args: Any) -> None:
            def builder(error: Any | None = None) -> ClickWindowDoneEvent:
                return ClickWindowDoneEvent(
                    error=str(error) if error is not None else None
                )

            self._post_built(js_bot, ClickWindowDoneEvent, builder, *args)

        @on_fn(js_bot, "_minethon:transferDone")
        def _on_transfer_done(*args: Any) -> None:
            def builder(error: Any | None = None) -> TransferDoneEvent:
                return TransferDoneEvent(
                    error=str(error) if error is not None else None
                )

            self._post_built(js_bot, TransferDoneEvent, builder, *args)

        @on_fn(js_bot, "_minethon:moveSlotItemDone")
        def _on_move_slot_item_done(*args: Any) -> None:
            def builder(error: Any | None = None) -> MoveSlotItemDoneEvent:
                return MoveSlotItemDoneEvent(
                    error=str(error) if error is not None else None
                )

            self._post_built(js_bot, MoveSlotItemDoneEvent, builder, *args)

        @on_fn(js_bot, "_minethon:putAwayDone")
        def _on_put_away_done(*args: Any) -> None:
            def builder(error: Any | None = None) -> PutAwayDoneEvent:
                return PutAwayDoneEvent(error=str(error) if error is not None else None)

            self._post_built(js_bot, PutAwayDoneEvent, builder, *args)

        @on_fn(js_bot, "_minethon:creativeFlyToDone")
        def _on_creative_fly_to_done(*args: Any) -> None:
            def builder(error: Any | None = None) -> CreativeFlyToDoneEvent:
                return CreativeFlyToDoneEvent(
                    error=str(error) if error is not None else None
                )

            self._post_built(js_bot, CreativeFlyToDoneEvent, builder, *args)

        @on_fn(js_bot, "_minethon:creativeSetSlotDone")
        def _on_creative_set_slot_done(*args: Any) -> None:
            def builder(error: Any | None = None) -> CreativeSetSlotDoneEvent:
                return CreativeSetSlotDoneEvent(
                    error=str(error) if error is not None else None
                )

            self._post_built(js_bot, CreativeSetSlotDoneEvent, builder, *args)

        @on_fn(js_bot, "_minethon:creativeClearSlotDone")
        def _on_creative_clear_slot_done(*args: Any) -> None:
            def builder(error: Any | None = None) -> CreativeClearSlotDoneEvent:
                return CreativeClearSlotDoneEvent(
                    error=str(error) if error is not None else None
                )

            self._post_built(js_bot, CreativeClearSlotDoneEvent, builder, *args)

        @on_fn(js_bot, "_minethon:creativeClearInventoryDone")
        def _on_creative_clear_inventory_done(*args: Any) -> None:
            def builder(error: Any | None = None) -> CreativeClearInventoryDoneEvent:
                return CreativeClearInventoryDoneEvent(
                    error=str(error) if error is not None else None
                )

            self._post_built(js_bot, CreativeClearInventoryDoneEvent, builder, *args)

        # -- Internal done events with return value --

        @on_fn(js_bot, "_minethon:openContainerDone")
        def _on_open_container_done(*args: Any) -> None:
            def builder(
                error: Any | None = None, result: Any | None = None
            ) -> OpenContainerDoneEvent:
                return OpenContainerDoneEvent(
                    error=str(error) if error is not None else None,
                    result=result,
                )

            self._post_built(js_bot, OpenContainerDoneEvent, builder, *args)

        @on_fn(js_bot, "_minethon:openFurnaceDone")
        def _on_open_furnace_done(*args: Any) -> None:
            def builder(
                error: Any | None = None, result: Any | None = None
            ) -> OpenFurnaceDoneEvent:
                return OpenFurnaceDoneEvent(
                    error=str(error) if error is not None else None,
                    result=result,
                )

            self._post_built(js_bot, OpenFurnaceDoneEvent, builder, *args)

        @on_fn(js_bot, "_minethon:openEnchantmentTableDone")
        def _on_open_enchantment_table_done(*args: Any) -> None:
            def builder(
                error: Any | None = None,
                result: Any | None = None,
            ) -> OpenEnchantmentTableDoneEvent:
                return OpenEnchantmentTableDoneEvent(
                    error=str(error) if error is not None else None,
                    result=result,
                )

            self._post_built(js_bot, OpenEnchantmentTableDoneEvent, builder, *args)

        @on_fn(js_bot, "_minethon:openAnvilDone")
        def _on_open_anvil_done(*args: Any) -> None:
            def builder(
                error: Any | None = None, result: Any | None = None
            ) -> OpenAnvilDoneEvent:
                return OpenAnvilDoneEvent(
                    error=str(error) if error is not None else None,
                    result=result,
                )

            self._post_built(js_bot, OpenAnvilDoneEvent, builder, *args)

        @on_fn(js_bot, "_minethon:openVillagerDone")
        def _on_open_villager_done(*args: Any) -> None:
            def builder(
                error: Any | None = None, result: Any | None = None
            ) -> OpenVillagerDoneEvent:
                return OpenVillagerDoneEvent(
                    error=str(error) if error is not None else None,
                    result=result,
                )

            self._post_built(js_bot, OpenVillagerDoneEvent, builder, *args)

        @on_fn(js_bot, "_minethon:tabCompleteDone")
        def _on_tab_complete_done(*args: Any) -> None:
            def builder(
                error: Any | None = None, result: Any | None = None
            ) -> TabCompleteDoneEvent:
                return TabCompleteDoneEvent(
                    error=str(error) if error is not None else None,
                    result=result,
                )

            self._post_built(js_bot, TabCompleteDoneEvent, builder, *args)

        @on_fn(js_bot, "_minethon:placeEntityDone")
        def _on_place_entity_done(*args: Any) -> None:
            def builder(
                error: Any | None = None, result: Any | None = None
            ) -> PlaceEntityDoneEvent:
                return PlaceEntityDoneEvent(
                    error=str(error) if error is not None else None,
                    result=result,
                )

            self._post_built(js_bot, PlaceEntityDoneEvent, builder, *args)

        # -- Armor Manager done event --

        @on_fn(js_bot, "_minethon:armorEquipDone")
        def _on_armor_equip_done(*args: Any) -> None:
            def builder(error: Any | None = None) -> ArmorEquipDoneEvent:
                return ArmorEquipDoneEvent(
                    error=str(error) if error is not None else None
                )

            self._post_built(js_bot, ArmorEquipDoneEvent, builder, *args)

        # -- Plugin: mineflayer-tool --

        @on_fn(js_bot, "_minethon:toolEquipDone")
        def _on_tool_equip_done(*args: Any) -> None:
            def builder(error: Any | None = None) -> ToolEquipDoneEvent:
                return ToolEquipDoneEvent(
                    error=str(error) if error is not None else None
                )

            self._post_built(js_bot, ToolEquipDoneEvent, builder, *args)

        # -- Viewer service done event --

        @on_fn(js_bot, "_minethon:viewerStartDone")
        def _on_viewer_start_done(*args: Any) -> None:
            def builder(error: Any | None = None) -> ViewerStartDoneEvent:
                return ViewerStartDoneEvent(
                    error=str(error) if error is not None else None
                )

            self._post_built(js_bot, ViewerStartDoneEvent, builder, *args)

        # -- Web inventory service done events --

        @on_fn(js_bot, "_minethon:webInvStartDone")
        def _on_web_inv_start_done(*args: Any) -> None:
            def builder(error: Any | None = None) -> WebInvStartDoneEvent:
                return WebInvStartDoneEvent(
                    error=str(error) if error is not None else None
                )

            self._post_built(js_bot, WebInvStartDoneEvent, builder, *args)

        @on_fn(js_bot, "_minethon:webInvStopDone")
        def _on_web_inv_stop_done(*args: Any) -> None:
            def builder(error: Any | None = None) -> WebInvStopDoneEvent:
                return WebInvStopDoneEvent(
                    error=str(error) if error is not None else None
                )

            self._post_built(js_bot, WebInvStopDoneEvent, builder, *args)

        # -- Panorama (mineflayer-panorama) --

        @on_fn(js_bot, "_minethon:panoramaDone")
        def _on_panorama_done(*args: Any) -> None:
            def builder(
                error: Any | None = None, result: Any | None = None
            ) -> PanoramaDoneEvent:
                return PanoramaDoneEvent(
                    error=str(error) if error is not None else None,
                    result=result,
                )

            self._post_built(js_bot, PanoramaDoneEvent, builder, *args)

        @on_fn(js_bot, "_minethon:pictureDone")
        def _on_picture_done(*args: Any) -> None:
            def builder(
                error: Any | None = None, result: Any | None = None
            ) -> PictureDoneEvent:
                return PictureDoneEvent(
                    error=str(error) if error is not None else None,
                    result=result,
                )

            self._post_built(js_bot, PictureDoneEvent, builder, *args)

        # -- HawkEye --

        @on_fn(js_bot, "_minethon:simplyShotDone")
        def _on_simply_shot_done(*args: Any) -> None:
            def builder(error: Any | None = None) -> SimplyShotDoneEvent:
                return SimplyShotDoneEvent(
                    error=str(error) if error is not None else None
                )

            self._post_built(js_bot, SimplyShotDoneEvent, builder, *args)

        @on_fn(js_bot, "auto_shot_stopped")
        def _on_auto_shot_stopped(*args: Any) -> None:
            normalized = self._normalize_js_args(js_bot, args)
            target_js = normalized[0] if normalized else None
            try:
                target = (
                    js_entity_to_entity(target_js)
                    if target_js is not None
                    else None
                )
            except Exception:
                target = None
            self._post(
                AutoShotStoppedEvent, AutoShotStoppedEvent(target=target)
            )

        # ================================================================
        # Throttled high-frequency events (raw dispatch only)
        # ================================================================

        throttled_handlers: list[object] = []
        for event_name in self._throttle_intervals:
            interval = self._throttle_intervals[event_name]

            # Capture event_name and interval per-iteration
            def _make_throttled(evt: str, intv: float) -> Callable[..., None]:
                def _handler(*_args: Any) -> None:
                    now = time.monotonic()
                    last = self._throttle_last_post.get(evt, 0.0)
                    if now - last < intv:
                        return
                    self._throttle_last_post[evt] = now
                    if evt == "move":
                        normalized = self._normalize_js_args(js_bot, _args)
                        position = (
                            normalized[0] if normalized else js_bot.entity.position
                        )
                        try:
                            self._post(
                                MoveEvent,
                                MoveEvent(position=_vec3_from_js(position)),
                            )
                        except Exception:
                            _log.debug("Failed to snapshot move payload", exc_info=True)
                    elif evt == "entityMoved":
                        normalized = self._normalize_js_args(js_bot, _args)
                        entity = normalized[0] if normalized else None
                        if entity is not None:
                            try:
                                self._post(
                                    EntityMovedEvent,
                                    EntityMovedEvent(
                                        entity_id=int(entity.id),
                                        position=_vec3_from_js(entity.position),
                                    ),
                                )
                            except Exception:
                                _log.debug(
                                    "Failed to snapshot entityMoved payload",
                                    exc_info=True,
                                )
                        self._post_raw(evt, {"args": list(normalized)})
                    elif evt == "entityUpdate":
                        _post_entity_event(
                            EntityUpdateEvent, *_args, include_entity=True
                        )
                        self._post_raw(
                            evt,
                            {"args": list(self._normalize_js_args(js_bot, _args))},
                        )
                    elif evt == "physicsTick":

                        def build_physics_tick(*_unused: Any) -> PhysicsTickEvent:
                            return PhysicsTickEvent()

                        self._post_built(
                            js_bot, PhysicsTickEvent, build_physics_tick, *_args
                        )
                        self._post_raw(
                            evt, {"args": list(self._normalize_js_args(js_bot, _args))}
                        )
                    else:
                        self._post_raw(
                            evt, {"args": list(self._normalize_js_args(js_bot, _args))}
                        )

                return _handler

            handler = _make_throttled(event_name, interval)
            on_fn(js_bot, event_name)(handler)
            throttled_handlers.append(handler)
            self._registered_events.add(event_name)

        # ================================================================
        # Keep strong refs to ALL handlers to prevent GC
        # ================================================================

        self._js_handler_refs.extend(
            [
                # Lifecycle
                _on_spawn,
                _on_login,
                _on_respawn,
                _on_game,
                _on_spawn_reset,
                _on_error,
                _on_death,
                _on_kicked,
                _on_end,
                # Chat / message
                _on_chat,
                _on_whisper,
                _on_action_bar,
                _on_message,
                _on_messagestr,
                # Title
                _on_title,
                _on_title_times,
                _on_title_clear,
                # Health & state
                _on_health,
                _on_breath,
                _on_experience,
                _on_sleep,
                _on_wake,
                _on_held_item_changed,
                # Movement
                _on_forced_move,
                _on_mount,
                _on_dismount,
                # Navigation
                _on_goal_reached,
                _on_path_update,
                _on_path_stop,
                # Entity events
                _on_entity_swing_arm,
                _on_entity_hurt,
                _on_entity_dead,
                _on_entity_taming,
                _on_entity_tamed,
                _on_entity_shaking_off_water,
                _on_entity_eating_grass,
                _on_entity_hand_swap,
                _on_entity_wake,
                _on_entity_eat,
                _on_entity_critical_effect,
                _on_entity_magic_critical_effect,
                _on_entity_crouch,
                _on_entity_uncrouch,
                _on_entity_equip,
                _on_entity_sleep,
                _on_entity_spawn,
                _on_entity_elytra_flew,
                _on_entity_gone,
                _on_entity_attach,
                _on_entity_detach,
                _on_entity_attributes,
                _on_entity_effect,
                _on_entity_effect_end,
                _on_item_drop,
                _on_player_collect,
                # Player events
                _on_player_joined,
                _on_player_updated,
                _on_player_left,
                # Block events
                _on_block_update,
                _on_block_placed,
                _on_chunk_column_load,
                _on_chunk_column_unload,
                # Digging
                _on_digging_completed,
                _on_digging_aborted,
                _on_block_break_progress_observed,
                _on_block_break_progress_end,
                # Sound
                _on_sound_effect_heard,
                _on_hardcoded_sound_effect_heard,
                _on_note_heard,
                # Weather & time
                _on_rain,
                _on_weather_update,
                _on_time,
                # World events
                _on_piston_move,
                _on_chest_lid_move,
                _on_used_firework,
                # Window
                _on_window_open,
                _on_window_close,
                # Resource pack
                _on_resource_pack,
                # Scoreboard
                _on_scoreboard_created,
                _on_scoreboard_deleted,
                _on_scoreboard_title_changed,
                _on_score_updated,
                _on_score_removed,
                _on_scoreboard_position,
                # Team
                _on_team_created,
                _on_team_removed,
                _on_team_updated,
                _on_team_member_added,
                _on_team_member_removed,
                # Boss bar
                _on_boss_bar_created,
                _on_boss_bar_deleted,
                _on_boss_bar_updated,
                # Physics & particles
                _on_particle,
                # Internal done events (void)
                _on_dig_done,
                _on_place_done,
                _on_equip_done,
                _on_look_at_done,
                _on_look_done,
                _on_sleep_done,
                _on_wake_done,
                _on_unequip_done,
                _on_toss_stack_done,
                _on_toss_done,
                _on_consume_done,
                _on_fish_done,
                _on_elytra_fly_done,
                _on_craft_done,
                _on_activate_block_done,
                _on_activate_entity_done,
                _on_activate_entity_at_done,
                _on_trade_done,
                _on_write_book_done,
                _on_chunks_loaded_done,
                _on_wait_for_ticks_done,
                _on_click_window_done,
                _on_transfer_done,
                _on_move_slot_item_done,
                _on_put_away_done,
                _on_creative_fly_to_done,
                _on_creative_set_slot_done,
                _on_creative_clear_slot_done,
                _on_creative_clear_inventory_done,
                # Internal done events (with result)
                _on_open_container_done,
                _on_open_furnace_done,
                _on_open_enchantment_table_done,
                _on_open_anvil_done,
                _on_open_villager_done,
                _on_tab_complete_done,
                _on_place_entity_done,
                # HawkEye
                _on_simply_shot_done,
                _on_auto_shot_stopped,
                # Plugin done events (Phase 1a)
                _on_armor_equip_done,
                _on_tool_equip_done,
                _on_viewer_start_done,
                _on_web_inv_start_done,
                _on_web_inv_stop_done,
                # Throttled
                *throttled_handlers,
            ]
        )

    # -- Handler management (called from ObserveAPI) --

    def add_handler(
        self, event_type: type, handler: Callable[..., Coroutine[Any, Any, None]]
    ) -> None:
        """Register an async handler for an event type."""
        self._handlers[event_type].append(handler)

    def remove_handler(
        self, event_type: type, handler: Callable[..., Coroutine[Any, Any, None]]
    ) -> None:
        """Unregister an async handler."""
        self._handlers[event_type].remove(handler)

    def add_raw_handler(
        self, event_name: str, handler: Callable[..., Coroutine[Any, Any, None]]
    ) -> None:
        """Register an async handler for a raw JS event name."""
        self._raw_handlers[event_name].append(handler)

    def remove_raw_handler(
        self, event_name: str, handler: Callable[..., Coroutine[Any, Any, None]]
    ) -> None:
        """Unregister a raw event handler."""
        self._raw_handlers[event_name].remove(handler)

    def bind_raw_js_event(self, js_bot: Any, on_fn: Any, event_name: str) -> None:
        """Dynamically bind a raw JS event for ``on_raw()`` subscribers.

        Events already handled by :meth:`register_js_events` are
        skipped to avoid attaching a duplicate (unthrottled) listener.

        Args:
            js_bot: The JS bot proxy.
            on_fn: The ``On`` decorator from JSPyBridge.
            event_name: The JS event name to listen for.
        """
        if event_name in self._registered_events:
            return

        if event_name in _HIGH_FREQ_EVENTS:
            _log.warning(
                "Subscribing to high-frequency event '%s'. "
                "This may impact performance. Consider throttling "
                "in your handler.",
                event_name,
            )

        @on_fn(js_bot, event_name)
        def _on_raw(*args: Any) -> None:
            data: dict[str, Any] = {
                "args": list(self._normalize_js_args(js_bot, args)),
            }
            self._post_raw(event_name, data)

        self._js_handler_refs.append(_on_raw)

    async def wait_for(self, event_type: type, *, timeout: float = 30.0) -> Any:
        """Wait for a single event of the given type."""
        if self._loop is None:
            raise RuntimeError(
                "EventRelay has no bound event loop. "
                "Call Bot.connect() before waiting for events."
            )
        fut: asyncio.Future[Any] = self._loop.create_future()
        self._waiters[event_type].append(fut)
        try:
            return await asyncio.wait_for(fut, timeout=timeout)
        finally:
            waiters = self._waiters.get(event_type, [])
            if fut in waiters:
                waiters.remove(fut)

    # -- Internal dispatch --

    def _post(self, event_type: type, event: object) -> None:
        """Thread-safe post from JSPyBridge callback thread."""
        if self._loop is not None and self._loop.is_running():
            try:
                self._loop.call_soon_threadsafe(self._dispatch, event_type, event)
            except RuntimeError:
                pass  # Event loop closed during shutdown

    @staticmethod
    def _normalize_js_args(js_bot: Any, args: tuple[Any, ...]) -> tuple[Any, ...]:
        """Drop the synthetic emitter arg inserted by legacy JSPyBridge patches."""
        if args and args[0] is js_bot:
            return args[1:]
        return args

    def _post_built(
        self,
        js_bot: Any,
        event_type: type,
        builder: Callable[..., object | None],
        *args: Any,
    ) -> None:
        """Defer JS payload parsing to the asyncio loop thread."""
        normalized = self._normalize_js_args(js_bot, args)
        if self._loop is not None and self._loop.is_running():
            try:
                self._loop.call_soon_threadsafe(
                    self._dispatch_built, event_type, builder, normalized
                )
            except RuntimeError:
                pass

    def _dispatch_built(
        self,
        event_type: type,
        builder: Callable[..., object | None],
        args: tuple[Any, ...],
    ) -> None:
        """Build and dispatch an event on the asyncio loop thread."""
        try:
            event = builder(*args)
        except Exception:
            _log.debug(
                "Failed to build %s from JS callback payload",
                event_type.__name__,
                exc_info=True,
            )
            return
        if event is not None:
            self._dispatch(event_type, event)

    def _post_raw(self, event_name: str, data: dict[str, Any]) -> None:
        """Thread-safe post for raw events."""
        if self._loop is not None and self._loop.is_running():
            try:
                self._loop.call_soon_threadsafe(self._dispatch_raw, event_name, data)
            except RuntimeError:
                pass

    @staticmethod
    async def _timed(coro: Coroutine[Any, Any, None], name: str) -> None:
        """Run a handler coroutine with execution-time monitoring."""
        t0 = time.monotonic()
        try:
            await coro
        except Exception as exc:
            _log.exception(
                "Unhandled exception in event handler %s",
                name,
                exc_info=exc,
            )
        finally:
            elapsed = time.monotonic() - t0
            if elapsed > _SLOW_HANDLER_THRESHOLD:
                _log.warning(
                    "Event handler '%s' took %.1fms (threshold: %.0fms)",
                    name,
                    elapsed * 1000,
                    _SLOW_HANDLER_THRESHOLD * 1000,
                )

    def _dispatch(self, event_type: type, event: object) -> None:
        """Runs on the asyncio event loop thread."""
        for fut in self._waiters.pop(event_type, []):
            if not fut.done():
                fut.set_result(event)
        if self._loop is not None:
            for handler in self._handlers.get(event_type, []):
                self._loop.create_task(
                    self._timed(
                        handler(event),
                        getattr(handler, "__qualname__", repr(handler)),
                    )
                )

    def _dispatch_raw(self, event_name: str, data: dict[str, Any]) -> None:
        """Dispatch raw events on the asyncio event loop thread."""
        if self._loop is not None:
            for handler in self._raw_handlers.get(event_name, []):
                self._loop.create_task(
                    self._timed(
                        handler(data),
                        getattr(handler, "__qualname__", repr(handler)),
                    )
                )
