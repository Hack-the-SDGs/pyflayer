"""Bridge JS EventEmitter callbacks into asyncio dispatch."""

import asyncio
import logging
import time
from collections import defaultdict
from collections.abc import Coroutine
from typing import Any, Callable

from minethon._bridge._events import (
    ActivateBlockDoneEvent,
    ActivateEntityAtDoneEvent,
    ActivateEntityDoneEvent,
    ClickWindowDoneEvent,
    ConsumeDoneEvent,
    CraftDoneEvent,
    CreativeClearInventoryDoneEvent,
    CreativeClearSlotDoneEvent,
    CreativeFlyToDoneEvent,
    CreativeSetSlotDoneEvent,
    ChunksLoadedDoneEvent,
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
from minethon.models.events import (
    # Lifecycle
    ChatEvent,
    DeathEvent,
    EndEvent,
    ErrorEvent,
    GameEvent,
    GoalFailedEvent,
    GoalReachedEvent,
    HealthChangedEvent,
    KickedEvent,
    LoginEvent,
    RespawnEvent,
    SpawnEvent,
    SpawnResetEvent,
    WhisperEvent,
    # Chat/Message
    ActionBarEvent,
    MessageEvent,
    MessageStrEvent,
    # Title
    TitleClearEvent,
    TitleEvent,
    TitleTimesEvent,
    # Health & State
    BreathEvent,
    ExperienceEvent,
    HeldItemChangedEvent,
    SleepEvent,
    WakeEvent,
    # Movement
    DismountEvent,
    ForcedMoveEvent,
    MountEvent,
    MoveEvent,
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
    EntityShakingOffWaterEvent,
    EntitySleepEvent,
    EntitySpawnEvent,
    EntitySwingArmEvent,
    EntityTamedEvent,
    EntityTamingEvent,
    EntityUncrouchEvent,
    EntityUpdateEvent,
    EntityWakeEvent,
    ItemDropEvent,
    PlayerCollectEvent,
    # Player events
    PlayerJoinedEvent,
    PlayerLeftEvent,
    PlayerUpdatedEvent,
    # Block events
    BlockPlacedEvent,
    BlockUpdateEvent,
    ChunkColumnLoadEvent,
    ChunkColumnUnloadEvent,
    # Digging
    BlockBreakProgressEndEvent,
    BlockBreakProgressObservedEvent,
    DiggingAbortedEvent,
    DiggingCompletedEvent,
    # Sound
    HardcodedSoundEffectHeardEvent,
    NoteHeardEvent,
    SoundEffectHeardEvent,
    # Weather & Time
    RainEvent,
    TimeEvent,
    WeatherUpdateEvent,
    # World events
    ChestLidMoveEvent,
    PistonMoveEvent,
    UsedFireworkEvent,
    # Window
    WindowCloseEvent,
    WindowOpenEvent,
    # Resource pack
    ResourcePackEvent,
    # Scoreboard
    ScoreboardCreatedEvent,
    ScoreboardDeletedEvent,
    ScoreboardPositionEvent,
    ScoreboardTitleChangedEvent,
    ScoreRemovedEvent,
    ScoreUpdatedEvent,
    # Team
    TeamCreatedEvent,
    TeamMemberAddedEvent,
    TeamMemberRemovedEvent,
    TeamRemovedEvent,
    TeamUpdatedEvent,
    # Boss bar
    BossBarCreatedEvent,
    BossBarDeletedEvent,
    BossBarUpdatedEvent,
    # Physics & Particles
    ParticleEvent,
)
from minethon.models.vec3 import Vec3

_log = logging.getLogger(__name__)

_HIGH_FREQ_EVENTS: frozenset[str] = frozenset({
    "physicsTick", "entityMoved", "move",
})
_SLOW_HANDLER_THRESHOLD: float = 0.5  # 500ms

# Static events always bound by register_js_events().
_STATIC_BRIDGED_EVENTS: frozenset[str] = frozenset({
    # Lifecycle
    "spawn", "login", "respawn", "game", "spawnReset", "error",
    # Chat / message
    "chat", "whisper", "actionBar", "message", "messagestr",
    # Title
    "title", "title_times", "title_clear",
    # Health & state
    "health", "breath", "experience",
    "death", "kicked", "end",
    "sleep", "wake", "heldItemChanged",
    # Movement
    "forcedMove", "mount", "dismount",
    # Navigation
    "goal_reached", "path_update", "path_stop",
    # Entity events
    "entitySwingArm", "entityHurt", "entityDead",
    "entityTaming", "entityTamed",
    "entityShakingOffWater", "entityEatingGrass",
    "entityHandSwap", "entityWake", "entityEat",
    "entityCriticalEffect", "entityMagicCriticalEffect",
    "entityCrouch", "entityUncrouch",
    "entityEquip", "entitySleep",
    "entitySpawn", "entityElytraFlew",
    "entityGone", "entityUpdate",
    "entityAttach", "entityDetach",
    "entityAttributes",
    "entityEffect", "entityEffectEnd",
    "itemDrop", "playerCollect",
    # Player events
    "playerJoined", "playerUpdated", "playerLeft",
    # Block events
    "blockUpdate", "blockPlaced",
    "chunkColumnLoad", "chunkColumnUnload",
    # Digging
    "diggingCompleted", "diggingAborted",
    "blockBreakProgressObserved", "blockBreakProgressEnd",
    # Sound
    "soundEffectHeard", "hardcodedSoundEffectHeard", "noteHeard",
    # Weather & time
    "rain", "weatherUpdate", "time",
    # World events
    "pistonMove", "chestLidMove", "usedFirework",
    # Window
    "windowOpen", "windowClose",
    # Resource pack
    "resourcePack",
    # Scoreboard
    "scoreboardCreated", "scoreboardDeleted",
    "scoreboardTitleChanged", "scoreUpdated", "scoreRemoved",
    "scoreboardPosition",
    # Team
    "teamCreated", "teamRemoved", "teamUpdated",
    "teamMemberAdded", "teamMemberRemoved",
    # Boss bar
    "bossBarCreated", "bossBarDeleted", "bossBarUpdated",
    # Physics & particles
    "particle",
    # Internal done events
    "_minethon:digDone", "_minethon:placeDone",
    "_minethon:equipDone", "_minethon:lookAtDone",
    "_minethon:lookDone", "_minethon:sleepDone", "_minethon:wakeDone",
    "_minethon:unequipDone", "_minethon:tossStackDone", "_minethon:tossDone",
    "_minethon:consumeDone", "_minethon:fishDone", "_minethon:elytraFlyDone",
    "_minethon:craftDone",
    "_minethon:activateBlockDone", "_minethon:activateEntityDone",
    "_minethon:activateEntityAtDone",
    "_minethon:openContainerDone", "_minethon:openFurnaceDone",
    "_minethon:openEnchantmentTableDone", "_minethon:openAnvilDone",
    "_minethon:openVillagerDone",
    "_minethon:tradeDone", "_minethon:tabCompleteDone",
    "_minethon:writeBookDone",
    "_minethon:chunksLoadedDone", "_minethon:waitForTicksDone",
    "_minethon:clickWindowDone", "_minethon:transferDone",
    "_minethon:moveSlotItemDone", "_minethon:putAwayDone",
    "_minethon:creativeFlyToDone", "_minethon:creativeSetSlotDone",
    "_minethon:creativeClearSlotDone", "_minethon:creativeClearInventoryDone",
    "_minethon:placeEntityDone",
})


class EventRelay:
    """Receives JS events on the JSPyBridge callback thread and
    dispatches them to asyncio handlers via ``call_soon_threadsafe``.
    """

    def __init__(
        self, event_throttle_ms: dict[str, int] | None = None
    ) -> None:
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
        throttle_cfg = event_throttle_ms if event_throttle_ms is not None else {"move": 50}
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
            self._post(GameEvent, GameEvent())

        @on_fn(js_bot, "spawnReset")
        def _on_spawn_reset(*_args: Any) -> None:
            self._post(SpawnResetEvent, SpawnResetEvent())

        @on_fn(js_bot, "error")
        def _on_error(*args: Any) -> None:
            message = str(args[0]) if args else "unknown"
            self._post(ErrorEvent, ErrorEvent(message=message))

        @on_fn(js_bot, "death")
        def _on_death(*_args: Any) -> None:
            self._post(DeathEvent, DeathEvent(reason=None))

        @on_fn(js_bot, "kicked")
        def _on_kicked(*args: Any) -> None:
            reason = str(args[0]) if len(args) > 0 else "unknown"
            logged_in = bool(args[1]) if len(args) > 1 else False
            self._post(KickedEvent, KickedEvent(reason=reason, logged_in=logged_in))

        @on_fn(js_bot, "end")
        def _on_end(*args: Any) -> None:
            reason = str(args[0]) if len(args) > 0 else "unknown"
            self._post(EndEvent, EndEvent(reason=reason))

        # ================================================================
        # Chat & Messages
        # ================================================================

        @on_fn(js_bot, "chat")
        def _on_chat(*args: Any) -> None:
            if len(args) < 2:
                return
            username = str(args[0])
            message = str(args[1])
            event = ChatEvent(
                sender=username,
                message=message,
                timestamp=time.time(),
            )
            self._post(ChatEvent, event)

        @on_fn(js_bot, "whisper")
        def _on_whisper(*args: Any) -> None:
            if len(args) < 2:
                return
            username = str(args[0])
            message = str(args[1])
            event = WhisperEvent(
                sender=username,
                message=message,
                timestamp=time.time(),
            )
            self._post(WhisperEvent, event)

        @on_fn(js_bot, "actionBar")
        def _on_action_bar(*args: Any) -> None:
            if args:
                try:
                    self._post(ActionBarEvent, ActionBarEvent(
                        message=str(args[0]),
                    ))
                except (AttributeError, TypeError):
                    pass

        @on_fn(js_bot, "message")
        def _on_message(*args: Any) -> None:
            if args:
                try:
                    json_msg = args[0]
                    position = str(args[1]) if len(args) > 1 else "chat"
                    sender = str(args[2]) if len(args) > 2 and args[2] is not None else None
                    self._post(MessageEvent, MessageEvent(
                        message=str(json_msg),
                        position=position,
                        sender=sender,
                    ))
                except (AttributeError, TypeError):
                    pass

        @on_fn(js_bot, "messagestr")
        def _on_messagestr(*args: Any) -> None:
            if args:
                try:
                    message = str(args[0])
                    position = str(args[1]) if len(args) > 1 else "chat"
                    sender = str(args[2]) if len(args) > 2 and args[2] is not None else None
                    self._post(MessageStrEvent, MessageStrEvent(
                        message=message,
                        position=position,
                        sender=sender,
                    ))
                except (AttributeError, TypeError):
                    pass

        # ================================================================
        # Title
        # ================================================================

        @on_fn(js_bot, "title")
        def _on_title(*args: Any) -> None:
            if args:
                try:
                    self._post(TitleEvent, TitleEvent(
                        text=str(args[0]),
                        type=str(args[1]) if len(args) > 1 else "title",
                    ))
                except (AttributeError, TypeError):
                    pass

        @on_fn(js_bot, "title_times")
        def _on_title_times(*args: Any) -> None:
            if len(args) >= 3:
                try:
                    self._post(TitleTimesEvent, TitleTimesEvent(
                        fade_in=int(args[0]),
                        stay=int(args[1]),
                        fade_out=int(args[2]),
                    ))
                except (AttributeError, TypeError, ValueError):
                    pass

        @on_fn(js_bot, "title_clear")
        def _on_title_clear(*_args: Any) -> None:
            self._post(TitleClearEvent, TitleClearEvent())

        # ================================================================
        # Health & State
        # ================================================================

        @on_fn(js_bot, "health")
        def _on_health(*_args: Any) -> None:
            try:
                event = HealthChangedEvent(
                    health=float(js_bot.health),
                    food=float(js_bot.food),
                    saturation=float(js_bot.foodSaturation),
                )
                self._post(HealthChangedEvent, event)
            except (AttributeError, TypeError):
                _log.debug("Failed to read health data", exc_info=True)

        @on_fn(js_bot, "breath")
        def _on_breath(*_args: Any) -> None:
            try:
                self._post(BreathEvent, BreathEvent(
                    oxygen_level=int(js_bot.oxygenLevel),
                ))
            except (AttributeError, TypeError):
                _log.debug("Failed to read oxygen level", exc_info=True)

        @on_fn(js_bot, "experience")
        def _on_experience(*_args: Any) -> None:
            try:
                exp = js_bot.experience
                self._post(ExperienceEvent, ExperienceEvent(
                    level=int(exp.level),
                    points=int(exp.points),
                    progress=float(exp.progress),
                ))
            except (AttributeError, TypeError):
                _log.debug("Failed to read experience data", exc_info=True)

        @on_fn(js_bot, "sleep")
        def _on_sleep(*_args: Any) -> None:
            self._post(SleepEvent, SleepEvent())

        @on_fn(js_bot, "wake")
        def _on_wake(*_args: Any) -> None:
            self._post(WakeEvent, WakeEvent())

        @on_fn(js_bot, "heldItemChanged")
        def _on_held_item_changed(*_args: Any) -> None:
            self._post(HeldItemChangedEvent, HeldItemChangedEvent())

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
            try:
                vehicle = args[0] if args else None
                vehicle_id = int(vehicle.id) if vehicle is not None else -1
                self._post(DismountEvent, DismountEvent(vehicle_id=vehicle_id))
            except (AttributeError, TypeError):
                self._post(DismountEvent, DismountEvent(vehicle_id=-1))

        # ================================================================
        # Navigation
        # ================================================================

        @on_fn(js_bot, "goal_reached")
        def _on_goal_reached(*_args: Any) -> None:
            self._goal_just_reached = True
            try:
                pos = js_bot.entity.position
                event = GoalReachedEvent(
                    position=Vec3(float(pos.x), float(pos.y), float(pos.z))
                )
                self._post(GoalReachedEvent, event)
            except (AttributeError, TypeError):
                self._post(
                    GoalReachedEvent,
                    GoalReachedEvent(position=Vec3(0.0, 0.0, 0.0)),
                )

        @on_fn(js_bot, "path_update")
        def _on_path_update(*args: Any) -> None:
            if not args:
                return
            result = args[0]
            status = getattr(result, "status", None)
            if status is not None and str(status) == "noPath":
                self._post(
                    GoalFailedEvent,
                    GoalFailedEvent(reason="noPath"),
                )

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
            if args:
                try:
                    self._post(EntitySwingArmEvent, EntitySwingArmEvent(
                        entity_id=int(args[0].id),
                    ))
                except (AttributeError, TypeError):
                    pass

        @on_fn(js_bot, "entityHurt")
        def _on_entity_hurt(*args: Any) -> None:
            if args:
                try:
                    self._post(EntityHurtEvent, EntityHurtEvent(
                        entity_id=int(args[0].id),
                    ))
                except (AttributeError, TypeError):
                    pass

        @on_fn(js_bot, "entityDead")
        def _on_entity_dead(*args: Any) -> None:
            if args:
                try:
                    self._post(EntityDeadEvent, EntityDeadEvent(
                        entity_id=int(args[0].id),
                    ))
                except (AttributeError, TypeError):
                    pass

        @on_fn(js_bot, "entityTaming")
        def _on_entity_taming(*args: Any) -> None:
            if args:
                try:
                    self._post(EntityTamingEvent, EntityTamingEvent(
                        entity_id=int(args[0].id),
                    ))
                except (AttributeError, TypeError):
                    pass

        @on_fn(js_bot, "entityTamed")
        def _on_entity_tamed(*args: Any) -> None:
            if args:
                try:
                    self._post(EntityTamedEvent, EntityTamedEvent(
                        entity_id=int(args[0].id),
                    ))
                except (AttributeError, TypeError):
                    pass

        @on_fn(js_bot, "entityShakingOffWater")
        def _on_entity_shaking_off_water(*args: Any) -> None:
            if args:
                try:
                    self._post(EntityShakingOffWaterEvent, EntityShakingOffWaterEvent(
                        entity_id=int(args[0].id),
                    ))
                except (AttributeError, TypeError):
                    pass

        @on_fn(js_bot, "entityEatingGrass")
        def _on_entity_eating_grass(*args: Any) -> None:
            if args:
                try:
                    self._post(EntityEatingGrassEvent, EntityEatingGrassEvent(
                        entity_id=int(args[0].id),
                    ))
                except (AttributeError, TypeError):
                    pass

        @on_fn(js_bot, "entityHandSwap")
        def _on_entity_hand_swap(*args: Any) -> None:
            if args:
                try:
                    self._post(EntityHandSwapEvent, EntityHandSwapEvent(
                        entity_id=int(args[0].id),
                    ))
                except (AttributeError, TypeError):
                    pass

        @on_fn(js_bot, "entityWake")
        def _on_entity_wake(*args: Any) -> None:
            if args:
                try:
                    self._post(EntityWakeEvent, EntityWakeEvent(
                        entity_id=int(args[0].id),
                    ))
                except (AttributeError, TypeError):
                    pass

        @on_fn(js_bot, "entityEat")
        def _on_entity_eat(*args: Any) -> None:
            if args:
                try:
                    self._post(EntityEatEvent, EntityEatEvent(
                        entity_id=int(args[0].id),
                    ))
                except (AttributeError, TypeError):
                    pass

        @on_fn(js_bot, "entityCriticalEffect")
        def _on_entity_critical_effect(*args: Any) -> None:
            if args:
                try:
                    self._post(EntityCriticalEffectEvent, EntityCriticalEffectEvent(
                        entity_id=int(args[0].id),
                    ))
                except (AttributeError, TypeError):
                    pass

        @on_fn(js_bot, "entityMagicCriticalEffect")
        def _on_entity_magic_critical_effect(*args: Any) -> None:
            if args:
                try:
                    self._post(EntityMagicCriticalEffectEvent, EntityMagicCriticalEffectEvent(
                        entity_id=int(args[0].id),
                    ))
                except (AttributeError, TypeError):
                    pass

        @on_fn(js_bot, "entityCrouch")
        def _on_entity_crouch(*args: Any) -> None:
            if args:
                try:
                    self._post(EntityCrouchEvent, EntityCrouchEvent(
                        entity_id=int(args[0].id),
                    ))
                except (AttributeError, TypeError):
                    pass

        @on_fn(js_bot, "entityUncrouch")
        def _on_entity_uncrouch(*args: Any) -> None:
            if args:
                try:
                    self._post(EntityUncrouchEvent, EntityUncrouchEvent(
                        entity_id=int(args[0].id),
                    ))
                except (AttributeError, TypeError):
                    pass

        @on_fn(js_bot, "entityEquip")
        def _on_entity_equip(*args: Any) -> None:
            if args:
                try:
                    self._post(EntityEquipEvent, EntityEquipEvent(
                        entity_id=int(args[0].id),
                    ))
                except (AttributeError, TypeError):
                    pass

        @on_fn(js_bot, "entitySleep")
        def _on_entity_sleep(*args: Any) -> None:
            if args:
                try:
                    self._post(EntitySleepEvent, EntitySleepEvent(
                        entity_id=int(args[0].id),
                    ))
                except (AttributeError, TypeError):
                    pass

        @on_fn(js_bot, "entitySpawn")
        def _on_entity_spawn(*args: Any) -> None:
            if args:
                try:
                    self._post(EntitySpawnEvent, EntitySpawnEvent(
                        entity_id=int(args[0].id),
                    ))
                except (AttributeError, TypeError):
                    pass

        @on_fn(js_bot, "entityElytraFlew")
        def _on_entity_elytra_flew(*args: Any) -> None:
            if args:
                try:
                    self._post(EntityElytraFlewEvent, EntityElytraFlewEvent(
                        entity_id=int(args[0].id),
                    ))
                except (AttributeError, TypeError):
                    pass

        @on_fn(js_bot, "entityGone")
        def _on_entity_gone(*args: Any) -> None:
            if args:
                try:
                    self._post(EntityGoneEvent, EntityGoneEvent(
                        entity_id=int(args[0].id),
                    ))
                except (AttributeError, TypeError):
                    pass

        @on_fn(js_bot, "entityUpdate")
        def _on_entity_update(*args: Any) -> None:
            if args:
                try:
                    self._post(EntityUpdateEvent, EntityUpdateEvent(
                        entity_id=int(args[0].id),
                    ))
                except (AttributeError, TypeError):
                    pass

        @on_fn(js_bot, "entityAttach")
        def _on_entity_attach(*args: Any) -> None:
            if len(args) >= 2:
                try:
                    self._post(EntityAttachEvent, EntityAttachEvent(
                        entity_id=int(args[0].id),
                        vehicle_id=int(args[1].id),
                    ))
                except (AttributeError, TypeError):
                    pass

        @on_fn(js_bot, "entityDetach")
        def _on_entity_detach(*args: Any) -> None:
            if len(args) >= 2:
                try:
                    self._post(EntityDetachEvent, EntityDetachEvent(
                        entity_id=int(args[0].id),
                        vehicle_id=int(args[1].id),
                    ))
                except (AttributeError, TypeError):
                    pass

        @on_fn(js_bot, "entityAttributes")
        def _on_entity_attributes(*args: Any) -> None:
            if args:
                try:
                    self._post(EntityAttributesEvent, EntityAttributesEvent(
                        entity_id=int(args[0].id),
                    ))
                except (AttributeError, TypeError):
                    pass

        @on_fn(js_bot, "entityEffect")
        def _on_entity_effect(*args: Any) -> None:
            if args:
                try:
                    entity = args[0]
                    effect = args[1] if len(args) > 1 else None
                    self._post(EntityEffectEvent, EntityEffectEvent(
                        entity_id=int(entity.id),
                        effect_id=int(effect.id) if effect is not None else -1,
                        amplifier=int(effect.amplifier) if effect is not None else 0,
                        duration=int(effect.duration) if effect is not None else 0,
                    ))
                except (AttributeError, TypeError):
                    pass

        @on_fn(js_bot, "entityEffectEnd")
        def _on_entity_effect_end(*args: Any) -> None:
            if args:
                try:
                    entity = args[0]
                    effect = args[1] if len(args) > 1 else None
                    self._post(EntityEffectEndEvent, EntityEffectEndEvent(
                        entity_id=int(entity.id),
                        effect_id=int(effect.id) if effect is not None else -1,
                    ))
                except (AttributeError, TypeError):
                    pass

        @on_fn(js_bot, "itemDrop")
        def _on_item_drop(*args: Any) -> None:
            if args:
                try:
                    self._post(ItemDropEvent, ItemDropEvent(
                        entity_id=int(args[0].id),
                    ))
                except (AttributeError, TypeError):
                    pass

        @on_fn(js_bot, "playerCollect")
        def _on_player_collect(*args: Any) -> None:
            if len(args) >= 2:
                try:
                    self._post(PlayerCollectEvent, PlayerCollectEvent(
                        collector_id=int(args[0].id),
                        collected_id=int(args[1].id),
                    ))
                except (AttributeError, TypeError):
                    pass

        # ================================================================
        # Player events
        # ================================================================

        @on_fn(js_bot, "playerJoined")
        def _on_player_joined(*args: Any) -> None:
            if args:
                try:
                    self._post(PlayerJoinedEvent, PlayerJoinedEvent(
                        username=str(args[0].username),
                    ))
                except (AttributeError, TypeError):
                    pass

        @on_fn(js_bot, "playerUpdated")
        def _on_player_updated(*args: Any) -> None:
            if args:
                try:
                    self._post(PlayerUpdatedEvent, PlayerUpdatedEvent(
                        username=str(args[0].username),
                    ))
                except (AttributeError, TypeError):
                    pass

        @on_fn(js_bot, "playerLeft")
        def _on_player_left(*args: Any) -> None:
            if args:
                try:
                    self._post(PlayerLeftEvent, PlayerLeftEvent(
                        username=str(args[0].username),
                    ))
                except (AttributeError, TypeError):
                    pass

        # ================================================================
        # Block events
        # ================================================================

        @on_fn(js_bot, "blockUpdate")
        def _on_block_update(*args: Any) -> None:
            if len(args) >= 2:
                try:
                    old_b = args[0]
                    new_b = args[1]
                    pos = (
                        new_b.position
                        if new_b is not None
                        else (old_b.position if old_b is not None else None)
                    )
                    if pos is not None:
                        self._post(BlockUpdateEvent, BlockUpdateEvent(
                            position=Vec3(float(pos.x), float(pos.y), float(pos.z)),
                            old_block_name=str(old_b.name) if old_b is not None else None,
                            new_block_name=str(new_b.name) if new_b is not None else None,
                        ))
                except (AttributeError, TypeError):
                    pass

        @on_fn(js_bot, "blockPlaced")
        def _on_block_placed(*args: Any) -> None:
            if len(args) >= 2:
                try:
                    old_b = args[0]
                    new_b = args[1]
                    pos = (
                        new_b.position
                        if new_b is not None
                        else (old_b.position if old_b is not None else None)
                    )
                    if pos is not None:
                        self._post(BlockPlacedEvent, BlockPlacedEvent(
                            position=Vec3(float(pos.x), float(pos.y), float(pos.z)),
                            old_block_name=str(old_b.name) if old_b is not None else None,
                            new_block_name=str(new_b.name) if new_b is not None else None,
                        ))
                except (AttributeError, TypeError):
                    pass

        @on_fn(js_bot, "chunkColumnLoad")
        def _on_chunk_column_load(*args: Any) -> None:
            if args:
                try:
                    point = args[0]
                    self._post(ChunkColumnLoadEvent, ChunkColumnLoadEvent(
                        position=Vec3(float(point.x), 0.0, float(point.z)),
                    ))
                except (AttributeError, TypeError):
                    pass

        @on_fn(js_bot, "chunkColumnUnload")
        def _on_chunk_column_unload(*args: Any) -> None:
            if args:
                try:
                    point = args[0]
                    self._post(ChunkColumnUnloadEvent, ChunkColumnUnloadEvent(
                        position=Vec3(float(point.x), 0.0, float(point.z)),
                    ))
                except (AttributeError, TypeError):
                    pass

        # ================================================================
        # Digging
        # ================================================================

        @on_fn(js_bot, "diggingCompleted")
        def _on_digging_completed(*args: Any) -> None:
            if args:
                try:
                    block = args[0]
                    pos = block.position
                    self._post(DiggingCompletedEvent, DiggingCompletedEvent(
                        position=Vec3(float(pos.x), float(pos.y), float(pos.z)),
                        block_name=str(block.name),
                    ))
                except (AttributeError, TypeError):
                    pass

        @on_fn(js_bot, "diggingAborted")
        def _on_digging_aborted(*args: Any) -> None:
            if args:
                try:
                    block = args[0]
                    pos = block.position
                    self._post(DiggingAbortedEvent, DiggingAbortedEvent(
                        position=Vec3(float(pos.x), float(pos.y), float(pos.z)),
                        block_name=str(block.name),
                    ))
                except (AttributeError, TypeError):
                    pass

        @on_fn(js_bot, "blockBreakProgressObserved")
        def _on_block_break_progress_observed(*args: Any) -> None:
            if len(args) >= 2:
                try:
                    block = args[0]
                    pos = block.position
                    destroy_stage = int(args[1])
                    entity = args[2] if len(args) > 2 else None
                    entity_id = int(entity.id) if entity is not None else -1
                    self._post(BlockBreakProgressObservedEvent, BlockBreakProgressObservedEvent(
                        position=Vec3(float(pos.x), float(pos.y), float(pos.z)),
                        destroy_stage=destroy_stage,
                        entity_id=entity_id,
                    ))
                except (AttributeError, TypeError):
                    pass

        @on_fn(js_bot, "blockBreakProgressEnd")
        def _on_block_break_progress_end(*args: Any) -> None:
            if args:
                try:
                    block = args[0]
                    pos = block.position
                    entity = args[1] if len(args) > 1 else None
                    entity_id = int(entity.id) if entity is not None else -1
                    self._post(BlockBreakProgressEndEvent, BlockBreakProgressEndEvent(
                        position=Vec3(float(pos.x), float(pos.y), float(pos.z)),
                        entity_id=entity_id,
                    ))
                except (AttributeError, TypeError):
                    pass

        # ================================================================
        # Sound
        # ================================================================

        @on_fn(js_bot, "soundEffectHeard")
        def _on_sound_effect_heard(*args: Any) -> None:
            if len(args) >= 5:
                try:
                    self._post(SoundEffectHeardEvent, SoundEffectHeardEvent(
                        sound_name=str(args[0]),
                        position=Vec3(float(args[1]), float(args[2]), float(args[3])),
                        volume=float(args[4]),
                        pitch=float(args[5]) if len(args) > 5 else 1.0,
                    ))
                except (AttributeError, TypeError, ValueError):
                    pass

        @on_fn(js_bot, "hardcodedSoundEffectHeard")
        def _on_hardcoded_sound_effect_heard(*args: Any) -> None:
            if len(args) >= 6:
                try:
                    self._post(HardcodedSoundEffectHeardEvent, HardcodedSoundEffectHeardEvent(
                        sound_id=int(args[0]),
                        sound_category=int(args[1]),
                        position=Vec3(float(args[2]), float(args[3]), float(args[4])),
                        volume=float(args[5]),
                        pitch=float(args[6]) if len(args) > 6 else 1.0,
                    ))
                except (AttributeError, TypeError, ValueError):
                    pass

        @on_fn(js_bot, "noteHeard")
        def _on_note_heard(*args: Any) -> None:
            if len(args) >= 2:
                try:
                    block = args[0]
                    pos = block.position
                    instrument = args[1]
                    pitch = int(args[2]) if len(args) > 2 else 0
                    self._post(NoteHeardEvent, NoteHeardEvent(
                        position=Vec3(float(pos.x), float(pos.y), float(pos.z)),
                        instrument_id=int(instrument.id) if hasattr(instrument, "id") else int(instrument),
                        pitch=pitch,
                    ))
                except (AttributeError, TypeError, ValueError):
                    pass

        # ================================================================
        # Weather & Time
        # ================================================================

        @on_fn(js_bot, "rain")
        def _on_rain(*_args: Any) -> None:
            self._post(RainEvent, RainEvent())

        @on_fn(js_bot, "weatherUpdate")
        def _on_weather_update(*_args: Any) -> None:
            try:
                self._post(WeatherUpdateEvent, WeatherUpdateEvent(
                    rain_state=float(js_bot.rainState),
                    thunder_state=float(js_bot.thunderState),
                ))
            except (AttributeError, TypeError):
                _log.debug("Failed to read weather state", exc_info=True)

        @on_fn(js_bot, "time")
        def _on_time(*_args: Any) -> None:
            try:
                self._post(TimeEvent, TimeEvent(
                    time_of_day=int(js_bot.time.timeOfDay),
                    age=int(js_bot.time.age),
                ))
            except (AttributeError, TypeError):
                _log.debug("Failed to read time data", exc_info=True)

        # ================================================================
        # World events
        # ================================================================

        @on_fn(js_bot, "pistonMove")
        def _on_piston_move(*args: Any) -> None:
            if len(args) >= 3:
                try:
                    block = args[0]
                    pos = block.position
                    self._post(PistonMoveEvent, PistonMoveEvent(
                        position=Vec3(float(pos.x), float(pos.y), float(pos.z)),
                        is_pulling=bool(args[1]),
                        direction=int(args[2]),
                    ))
                except (AttributeError, TypeError):
                    pass

        @on_fn(js_bot, "chestLidMove")
        def _on_chest_lid_move(*args: Any) -> None:
            if len(args) >= 2:
                try:
                    block = args[0]
                    pos = block.position
                    self._post(ChestLidMoveEvent, ChestLidMoveEvent(
                        position=Vec3(float(pos.x), float(pos.y), float(pos.z)),
                        is_open=int(args[1]),
                    ))
                except (AttributeError, TypeError):
                    pass

        @on_fn(js_bot, "usedFirework")
        def _on_used_firework(*args: Any) -> None:
            if args:
                try:
                    self._post(UsedFireworkEvent, UsedFireworkEvent(
                        firework_entity_id=int(args[0].id) if hasattr(args[0], "id") else int(args[0]),
                    ))
                except (AttributeError, TypeError):
                    pass

        # ================================================================
        # Window
        # ================================================================

        @on_fn(js_bot, "windowOpen")
        def _on_window_open(*args: Any) -> None:
            if args:
                try:
                    window = args[0]
                    self._post(WindowOpenEvent, WindowOpenEvent(
                        window_id=int(window.id) if hasattr(window, "id") else 0,
                    ))
                except (AttributeError, TypeError):
                    pass

        @on_fn(js_bot, "windowClose")
        def _on_window_close(*args: Any) -> None:
            if args:
                try:
                    window = args[0]
                    self._post(WindowCloseEvent, WindowCloseEvent(
                        window_id=int(window.id) if hasattr(window, "id") else 0,
                    ))
                except (AttributeError, TypeError):
                    pass

        # ================================================================
        # Resource pack
        # ================================================================

        @on_fn(js_bot, "resourcePack")
        def _on_resource_pack(*args: Any) -> None:
            if args:
                try:
                    self._post(ResourcePackEvent, ResourcePackEvent(
                        url=str(args[0]),
                        hash=str(args[1]) if len(args) > 1 else "",
                    ))
                except (AttributeError, TypeError):
                    pass

        # ================================================================
        # Scoreboard
        # ================================================================

        @on_fn(js_bot, "scoreboardCreated")
        def _on_scoreboard_created(*args: Any) -> None:
            if args:
                try:
                    self._post(ScoreboardCreatedEvent, ScoreboardCreatedEvent(
                        name=str(args[0].name) if hasattr(args[0], "name") else str(args[0]),
                    ))
                except (AttributeError, TypeError):
                    pass

        @on_fn(js_bot, "scoreboardDeleted")
        def _on_scoreboard_deleted(*args: Any) -> None:
            if args:
                try:
                    self._post(ScoreboardDeletedEvent, ScoreboardDeletedEvent(
                        name=str(args[0].name) if hasattr(args[0], "name") else str(args[0]),
                    ))
                except (AttributeError, TypeError):
                    pass

        @on_fn(js_bot, "scoreboardTitleChanged")
        def _on_scoreboard_title_changed(*args: Any) -> None:
            if args:
                try:
                    self._post(ScoreboardTitleChangedEvent, ScoreboardTitleChangedEvent(
                        name=str(args[0].name) if hasattr(args[0], "name") else str(args[0]),
                    ))
                except (AttributeError, TypeError):
                    pass

        @on_fn(js_bot, "scoreUpdated")
        def _on_score_updated(*args: Any) -> None:
            if args:
                try:
                    score = args[0]
                    self._post(ScoreUpdatedEvent, ScoreUpdatedEvent(
                        scoreboard_name=str(score.scoreName) if hasattr(score, "scoreName") else "",
                        item_name=str(score.itemName) if hasattr(score, "itemName") else str(score),
                        value=int(score.value) if hasattr(score, "value") else 0,
                    ))
                except (AttributeError, TypeError):
                    pass

        @on_fn(js_bot, "scoreRemoved")
        def _on_score_removed(*args: Any) -> None:
            if args:
                try:
                    score = args[0]
                    self._post(ScoreRemovedEvent, ScoreRemovedEvent(
                        scoreboard_name=str(score.scoreName) if hasattr(score, "scoreName") else "",
                        item_name=str(score.itemName) if hasattr(score, "itemName") else str(score),
                    ))
                except (AttributeError, TypeError):
                    pass

        @on_fn(js_bot, "scoreboardPosition")
        def _on_scoreboard_position(*args: Any) -> None:
            if len(args) >= 2:
                try:
                    self._post(ScoreboardPositionEvent, ScoreboardPositionEvent(
                        position=int(args[0]),
                        scoreboard_name=str(args[1].name) if hasattr(args[1], "name") else str(args[1]),
                    ))
                except (AttributeError, TypeError):
                    pass

        # ================================================================
        # Team
        # ================================================================

        @on_fn(js_bot, "teamCreated")
        def _on_team_created(*args: Any) -> None:
            if args:
                try:
                    self._post(TeamCreatedEvent, TeamCreatedEvent(
                        name=str(args[0].name) if hasattr(args[0], "name") else str(args[0]),
                    ))
                except (AttributeError, TypeError):
                    pass

        @on_fn(js_bot, "teamRemoved")
        def _on_team_removed(*args: Any) -> None:
            if args:
                try:
                    self._post(TeamRemovedEvent, TeamRemovedEvent(
                        name=str(args[0].name) if hasattr(args[0], "name") else str(args[0]),
                    ))
                except (AttributeError, TypeError):
                    pass

        @on_fn(js_bot, "teamUpdated")
        def _on_team_updated(*args: Any) -> None:
            if args:
                try:
                    self._post(TeamUpdatedEvent, TeamUpdatedEvent(
                        name=str(args[0].name) if hasattr(args[0], "name") else str(args[0]),
                    ))
                except (AttributeError, TypeError):
                    pass

        @on_fn(js_bot, "teamMemberAdded")
        def _on_team_member_added(*args: Any) -> None:
            if args:
                try:
                    self._post(TeamMemberAddedEvent, TeamMemberAddedEvent(
                        team_name=str(args[0].name) if hasattr(args[0], "name") else str(args[0]),
                    ))
                except (AttributeError, TypeError):
                    pass

        @on_fn(js_bot, "teamMemberRemoved")
        def _on_team_member_removed(*args: Any) -> None:
            if args:
                try:
                    self._post(TeamMemberRemovedEvent, TeamMemberRemovedEvent(
                        team_name=str(args[0].name) if hasattr(args[0], "name") else str(args[0]),
                    ))
                except (AttributeError, TypeError):
                    pass

        # ================================================================
        # Boss bar
        # ================================================================

        @on_fn(js_bot, "bossBarCreated")
        def _on_boss_bar_created(*args: Any) -> None:
            if args:
                try:
                    bar = args[0]
                    self._post(BossBarCreatedEvent, BossBarCreatedEvent(
                        entity_uuid=str(bar.entityUUID) if hasattr(bar, "entityUUID") else str(bar),
                        title=str(bar.title) if hasattr(bar, "title") else "",
                        health=float(bar.health) if hasattr(bar, "health") else 0.0,
                    ))
                except (AttributeError, TypeError):
                    pass

        @on_fn(js_bot, "bossBarDeleted")
        def _on_boss_bar_deleted(*args: Any) -> None:
            if args:
                try:
                    bar = args[0]
                    self._post(BossBarDeletedEvent, BossBarDeletedEvent(
                        entity_uuid=str(bar.entityUUID) if hasattr(bar, "entityUUID") else str(bar),
                    ))
                except (AttributeError, TypeError):
                    pass

        @on_fn(js_bot, "bossBarUpdated")
        def _on_boss_bar_updated(*args: Any) -> None:
            if args:
                try:
                    bar = args[0]
                    self._post(BossBarUpdatedEvent, BossBarUpdatedEvent(
                        entity_uuid=str(bar.entityUUID) if hasattr(bar, "entityUUID") else str(bar),
                        title=str(bar.title) if hasattr(bar, "title") else "",
                        health=float(bar.health) if hasattr(bar, "health") else 0.0,
                    ))
                except (AttributeError, TypeError):
                    pass

        # ================================================================
        # Physics & Particles
        # ================================================================

        @on_fn(js_bot, "particle")
        def _on_particle(*args: Any) -> None:
            if args:
                try:
                    p = args[0]
                    pos = p.position if hasattr(p, "position") else p
                    self._post(ParticleEvent, ParticleEvent(
                        particle_id=int(p.id) if hasattr(p, "id") else 0,
                        particle_name=str(p.name) if hasattr(p, "name") else "",
                        position=Vec3(float(pos.x), float(pos.y), float(pos.z)),
                        count=int(p.amount) if hasattr(p, "amount") else 1,
                    ))
                except (AttributeError, TypeError):
                    pass

        # ================================================================
        # Internal async-operation completion events (void pattern)
        # ================================================================

        @on_fn(js_bot, "_minethon:digDone")
        def _on_dig_done(*args: Any) -> None:
            error = str(args[0]) if args and args[0] is not None else None
            self._post(DigDoneEvent, DigDoneEvent(error=error))

        @on_fn(js_bot, "_minethon:placeDone")
        def _on_place_done(*args: Any) -> None:
            error = str(args[0]) if args and args[0] is not None else None
            self._post(PlaceDoneEvent, PlaceDoneEvent(error=error))

        @on_fn(js_bot, "_minethon:equipDone")
        def _on_equip_done(*args: Any) -> None:
            error = str(args[0]) if args and args[0] is not None else None
            self._post(EquipDoneEvent, EquipDoneEvent(error=error))

        @on_fn(js_bot, "_minethon:lookAtDone")
        def _on_look_at_done(*args: Any) -> None:
            error = str(args[0]) if args and args[0] is not None else None
            self._post(LookAtDoneEvent, LookAtDoneEvent(error=error))

        @on_fn(js_bot, "_minethon:lookDone")
        def _on_look_done(*args: Any) -> None:
            error = str(args[0]) if args and args[0] is not None else None
            self._post(LookDoneEvent, LookDoneEvent(error=error))

        @on_fn(js_bot, "_minethon:sleepDone")
        def _on_sleep_done(*args: Any) -> None:
            error = str(args[0]) if args and args[0] is not None else None
            self._post(SleepDoneEvent, SleepDoneEvent(error=error))

        @on_fn(js_bot, "_minethon:wakeDone")
        def _on_wake_done(*args: Any) -> None:
            error = str(args[0]) if args and args[0] is not None else None
            self._post(WakeDoneEvent, WakeDoneEvent(error=error))

        @on_fn(js_bot, "_minethon:unequipDone")
        def _on_unequip_done(*args: Any) -> None:
            error = str(args[0]) if args and args[0] is not None else None
            self._post(UnequipDoneEvent, UnequipDoneEvent(error=error))

        @on_fn(js_bot, "_minethon:tossStackDone")
        def _on_toss_stack_done(*args: Any) -> None:
            error = str(args[0]) if args and args[0] is not None else None
            self._post(TossStackDoneEvent, TossStackDoneEvent(error=error))

        @on_fn(js_bot, "_minethon:tossDone")
        def _on_toss_done(*args: Any) -> None:
            error = str(args[0]) if args and args[0] is not None else None
            self._post(TossDoneEvent, TossDoneEvent(error=error))

        @on_fn(js_bot, "_minethon:consumeDone")
        def _on_consume_done(*args: Any) -> None:
            error = str(args[0]) if args and args[0] is not None else None
            self._post(ConsumeDoneEvent, ConsumeDoneEvent(error=error))

        @on_fn(js_bot, "_minethon:fishDone")
        def _on_fish_done(*args: Any) -> None:
            error = str(args[0]) if args and args[0] is not None else None
            self._post(FishDoneEvent, FishDoneEvent(error=error))

        @on_fn(js_bot, "_minethon:elytraFlyDone")
        def _on_elytra_fly_done(*args: Any) -> None:
            error = str(args[0]) if args and args[0] is not None else None
            self._post(ElytraFlyDoneEvent, ElytraFlyDoneEvent(error=error))

        @on_fn(js_bot, "_minethon:craftDone")
        def _on_craft_done(*args: Any) -> None:
            error = str(args[0]) if args and args[0] is not None else None
            self._post(CraftDoneEvent, CraftDoneEvent(error=error))

        @on_fn(js_bot, "_minethon:activateBlockDone")
        def _on_activate_block_done(*args: Any) -> None:
            error = str(args[0]) if args and args[0] is not None else None
            self._post(ActivateBlockDoneEvent, ActivateBlockDoneEvent(error=error))

        @on_fn(js_bot, "_minethon:activateEntityDone")
        def _on_activate_entity_done(*args: Any) -> None:
            error = str(args[0]) if args and args[0] is not None else None
            self._post(ActivateEntityDoneEvent, ActivateEntityDoneEvent(error=error))

        @on_fn(js_bot, "_minethon:activateEntityAtDone")
        def _on_activate_entity_at_done(*args: Any) -> None:
            error = str(args[0]) if args and args[0] is not None else None
            self._post(ActivateEntityAtDoneEvent, ActivateEntityAtDoneEvent(error=error))

        @on_fn(js_bot, "_minethon:tradeDone")
        def _on_trade_done(*args: Any) -> None:
            error = str(args[0]) if args and args[0] is not None else None
            self._post(TradeDoneEvent, TradeDoneEvent(error=error))

        @on_fn(js_bot, "_minethon:writeBookDone")
        def _on_write_book_done(*args: Any) -> None:
            error = str(args[0]) if args and args[0] is not None else None
            self._post(WriteBookDoneEvent, WriteBookDoneEvent(error=error))

        @on_fn(js_bot, "_minethon:chunksLoadedDone")
        def _on_chunks_loaded_done(*args: Any) -> None:
            error = str(args[0]) if args and args[0] is not None else None
            self._post(ChunksLoadedDoneEvent, ChunksLoadedDoneEvent(error=error))

        @on_fn(js_bot, "_minethon:waitForTicksDone")
        def _on_wait_for_ticks_done(*args: Any) -> None:
            error = str(args[0]) if args and args[0] is not None else None
            self._post(WaitForTicksDoneEvent, WaitForTicksDoneEvent(error=error))

        @on_fn(js_bot, "_minethon:clickWindowDone")
        def _on_click_window_done(*args: Any) -> None:
            error = str(args[0]) if args and args[0] is not None else None
            self._post(ClickWindowDoneEvent, ClickWindowDoneEvent(error=error))

        @on_fn(js_bot, "_minethon:transferDone")
        def _on_transfer_done(*args: Any) -> None:
            error = str(args[0]) if args and args[0] is not None else None
            self._post(TransferDoneEvent, TransferDoneEvent(error=error))

        @on_fn(js_bot, "_minethon:moveSlotItemDone")
        def _on_move_slot_item_done(*args: Any) -> None:
            error = str(args[0]) if args and args[0] is not None else None
            self._post(MoveSlotItemDoneEvent, MoveSlotItemDoneEvent(error=error))

        @on_fn(js_bot, "_minethon:putAwayDone")
        def _on_put_away_done(*args: Any) -> None:
            error = str(args[0]) if args and args[0] is not None else None
            self._post(PutAwayDoneEvent, PutAwayDoneEvent(error=error))

        @on_fn(js_bot, "_minethon:creativeFlyToDone")
        def _on_creative_fly_to_done(*args: Any) -> None:
            error = str(args[0]) if args and args[0] is not None else None
            self._post(CreativeFlyToDoneEvent, CreativeFlyToDoneEvent(error=error))

        @on_fn(js_bot, "_minethon:creativeSetSlotDone")
        def _on_creative_set_slot_done(*args: Any) -> None:
            error = str(args[0]) if args and args[0] is not None else None
            self._post(CreativeSetSlotDoneEvent, CreativeSetSlotDoneEvent(error=error))

        @on_fn(js_bot, "_minethon:creativeClearSlotDone")
        def _on_creative_clear_slot_done(*args: Any) -> None:
            error = str(args[0]) if args and args[0] is not None else None
            self._post(CreativeClearSlotDoneEvent, CreativeClearSlotDoneEvent(error=error))

        @on_fn(js_bot, "_minethon:creativeClearInventoryDone")
        def _on_creative_clear_inventory_done(*args: Any) -> None:
            error = str(args[0]) if args and args[0] is not None else None
            self._post(CreativeClearInventoryDoneEvent, CreativeClearInventoryDoneEvent(error=error))

        # -- Internal done events with return value --

        @on_fn(js_bot, "_minethon:openContainerDone")
        def _on_open_container_done(*args: Any) -> None:
            error = str(args[0]) if args and args[0] is not None else None
            result = args[1] if len(args) > 1 else None
            self._post(OpenContainerDoneEvent, OpenContainerDoneEvent(error=error, result=result))

        @on_fn(js_bot, "_minethon:openFurnaceDone")
        def _on_open_furnace_done(*args: Any) -> None:
            error = str(args[0]) if args and args[0] is not None else None
            result = args[1] if len(args) > 1 else None
            self._post(OpenFurnaceDoneEvent, OpenFurnaceDoneEvent(error=error, result=result))

        @on_fn(js_bot, "_minethon:openEnchantmentTableDone")
        def _on_open_enchantment_table_done(*args: Any) -> None:
            error = str(args[0]) if args and args[0] is not None else None
            result = args[1] if len(args) > 1 else None
            self._post(OpenEnchantmentTableDoneEvent, OpenEnchantmentTableDoneEvent(
                error=error, result=result,
            ))

        @on_fn(js_bot, "_minethon:openAnvilDone")
        def _on_open_anvil_done(*args: Any) -> None:
            error = str(args[0]) if args and args[0] is not None else None
            result = args[1] if len(args) > 1 else None
            self._post(OpenAnvilDoneEvent, OpenAnvilDoneEvent(error=error, result=result))

        @on_fn(js_bot, "_minethon:openVillagerDone")
        def _on_open_villager_done(*args: Any) -> None:
            error = str(args[0]) if args and args[0] is not None else None
            result = args[1] if len(args) > 1 else None
            self._post(OpenVillagerDoneEvent, OpenVillagerDoneEvent(error=error, result=result))

        @on_fn(js_bot, "_minethon:tabCompleteDone")
        def _on_tab_complete_done(*args: Any) -> None:
            error = str(args[0]) if args and args[0] is not None else None
            result = args[1] if len(args) > 1 else None
            self._post(TabCompleteDoneEvent, TabCompleteDoneEvent(error=error, result=result))

        @on_fn(js_bot, "_minethon:placeEntityDone")
        def _on_place_entity_done(*args: Any) -> None:
            error = str(args[0]) if args and args[0] is not None else None
            result = args[1] if len(args) > 1 else None
            self._post(PlaceEntityDoneEvent, PlaceEntityDoneEvent(error=error, result=result))

        # ================================================================
        # Throttled high-frequency events (raw dispatch only)
        # ================================================================

        throttled_handlers: list[object] = []
        for event_name in self._throttle_intervals:
            interval = self._throttle_intervals[event_name]
            # Capture event_name and interval per-iteration
            def _make_throttled(
                evt: str, intv: float
            ) -> Callable[..., None]:
                def _handler(*_args: Any) -> None:
                    now = time.monotonic()
                    last = self._throttle_last_post.get(evt, 0.0)
                    if now - last < intv:
                        return
                    self._throttle_last_post[evt] = now
                    if evt == "move":
                        self._post(MoveEvent, MoveEvent())
                    else:
                        self._post_raw(evt, {"args": list(_args)})
                return _handler

            handler = _make_throttled(event_name, interval)
            on_fn(js_bot, event_name)(handler)
            throttled_handlers.append(handler)
            self._registered_events.add(event_name)

        # ================================================================
        # Keep strong refs to ALL handlers to prevent GC
        # ================================================================

        self._js_handler_refs.extend([
            # Lifecycle
            _on_spawn, _on_login, _on_respawn, _on_game,
            _on_spawn_reset, _on_error, _on_death, _on_kicked, _on_end,
            # Chat / message
            _on_chat, _on_whisper, _on_action_bar,
            _on_message, _on_messagestr,
            # Title
            _on_title, _on_title_times, _on_title_clear,
            # Health & state
            _on_health, _on_breath, _on_experience,
            _on_sleep, _on_wake, _on_held_item_changed,
            # Movement
            _on_forced_move, _on_mount, _on_dismount,
            # Navigation
            _on_goal_reached, _on_path_update, _on_path_stop,
            # Entity events
            _on_entity_swing_arm, _on_entity_hurt, _on_entity_dead,
            _on_entity_taming, _on_entity_tamed,
            _on_entity_shaking_off_water, _on_entity_eating_grass,
            _on_entity_hand_swap, _on_entity_wake, _on_entity_eat,
            _on_entity_critical_effect, _on_entity_magic_critical_effect,
            _on_entity_crouch, _on_entity_uncrouch,
            _on_entity_equip, _on_entity_sleep,
            _on_entity_spawn, _on_entity_elytra_flew,
            _on_entity_gone, _on_entity_update,
            _on_entity_attach, _on_entity_detach,
            _on_entity_attributes,
            _on_entity_effect, _on_entity_effect_end,
            _on_item_drop, _on_player_collect,
            # Player events
            _on_player_joined, _on_player_updated, _on_player_left,
            # Block events
            _on_block_update, _on_block_placed,
            _on_chunk_column_load, _on_chunk_column_unload,
            # Digging
            _on_digging_completed, _on_digging_aborted,
            _on_block_break_progress_observed, _on_block_break_progress_end,
            # Sound
            _on_sound_effect_heard, _on_hardcoded_sound_effect_heard,
            _on_note_heard,
            # Weather & time
            _on_rain, _on_weather_update, _on_time,
            # World events
            _on_piston_move, _on_chest_lid_move, _on_used_firework,
            # Window
            _on_window_open, _on_window_close,
            # Resource pack
            _on_resource_pack,
            # Scoreboard
            _on_scoreboard_created, _on_scoreboard_deleted,
            _on_scoreboard_title_changed, _on_score_updated,
            _on_score_removed, _on_scoreboard_position,
            # Team
            _on_team_created, _on_team_removed, _on_team_updated,
            _on_team_member_added, _on_team_member_removed,
            # Boss bar
            _on_boss_bar_created, _on_boss_bar_deleted, _on_boss_bar_updated,
            # Physics & particles
            _on_particle,
            # Internal done events (void)
            _on_dig_done, _on_place_done, _on_equip_done, _on_look_at_done,
            _on_look_done, _on_sleep_done, _on_wake_done,
            _on_unequip_done, _on_toss_stack_done, _on_toss_done,
            _on_consume_done, _on_fish_done, _on_elytra_fly_done,
            _on_craft_done,
            _on_activate_block_done, _on_activate_entity_done,
            _on_activate_entity_at_done,
            _on_trade_done, _on_write_book_done,
            _on_chunks_loaded_done, _on_wait_for_ticks_done,
            _on_click_window_done, _on_transfer_done,
            _on_move_slot_item_done, _on_put_away_done,
            _on_creative_fly_to_done, _on_creative_set_slot_done,
            _on_creative_clear_slot_done, _on_creative_clear_inventory_done,
            # Internal done events (with result)
            _on_open_container_done, _on_open_furnace_done,
            _on_open_enchantment_table_done, _on_open_anvil_done,
            _on_open_villager_done,
            _on_tab_complete_done, _on_place_entity_done,
            # Throttled
            *throttled_handlers,
        ])

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

    def bind_raw_js_event(
        self, js_bot: Any, on_fn: Any, event_name: str
    ) -> None:
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
            data: dict[str, Any] = {"args": list(args)}
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

    def _post_raw(self, event_name: str, data: dict[str, Any]) -> None:
        """Thread-safe post for raw events."""
        if self._loop is not None and self._loop.is_running():
            try:
                self._loop.call_soon_threadsafe(
                    self._dispatch_raw, event_name, data
                )
            except RuntimeError:
                pass

    @staticmethod
    async def _timed(
        coro: Coroutine[Any, Any, None], name: str
    ) -> None:
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
