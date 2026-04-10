"""High-level event dataclasses for all mineflayer events."""

from __future__ import annotations

from dataclasses import dataclass

from minethon.models.entity import Entity
from minethon.models.item import ItemStack
from minethon.models.vec3 import Vec3


# -- Lifecycle --


@dataclass(frozen=True, slots=True)
class SpawnEvent:
    """Bot has spawned in the world."""


@dataclass(frozen=True, slots=True)
class LoginEvent:
    """Bot has successfully logged in."""


@dataclass(frozen=True, slots=True)
class RespawnEvent:
    """Bot has respawned after death."""


@dataclass(frozen=True, slots=True)
class DeathEvent:
    """Bot has died."""

    reason: str | None


@dataclass(frozen=True, slots=True)
class EndEvent:
    """Bot connection has ended (kicked, quit, or network error)."""

    reason: str


@dataclass(frozen=True, slots=True)
class KickedEvent:
    """Bot was kicked from the server."""

    reason: str
    logged_in: bool


@dataclass(frozen=True, slots=True)
class ErrorEvent:
    """An error occurred."""

    message: str


# -- Chat & Messages --


@dataclass(frozen=True, slots=True)
class ChatEvent:
    """A chat message was received."""

    sender: str
    message: str
    timestamp: float


@dataclass(frozen=True, slots=True)
class WhisperEvent:
    """A whisper (private message) was received."""

    sender: str
    message: str
    timestamp: float


@dataclass(frozen=True, slots=True)
class ActionBarEvent:
    """An action bar message was received."""

    message: str
    verified: bool | None = None


@dataclass(frozen=True, slots=True)
class MessageEvent:
    """A parsed chat message was received."""

    message: str
    position: str
    sender: str | None
    verified: bool | None = None


@dataclass(frozen=True, slots=True)
class MessageStrEvent:
    """A raw string chat message was received."""

    message: str
    position: str
    sender: str | None
    verified: bool | None = None


# -- Title --


@dataclass(frozen=True, slots=True)
class TitleEvent:
    """A title or subtitle was displayed."""

    text: str
    type: str


@dataclass(frozen=True, slots=True)
class TitleTimesEvent:
    """Title display timing was updated."""

    fade_in: int
    stay: int
    fade_out: int


@dataclass(frozen=True, slots=True)
class TitleClearEvent:
    """Title display was cleared."""


# -- Health & State --


@dataclass(frozen=True, slots=True)
class HealthChangedEvent:
    """Bot health, food, or saturation changed."""

    health: float
    food: float
    saturation: float


@dataclass(frozen=True, slots=True)
class BreathEvent:
    """Bot oxygen level changed."""

    oxygen_level: int


@dataclass(frozen=True, slots=True)
class ExperienceEvent:
    """Bot experience changed."""

    level: int
    points: int
    progress: float


@dataclass(frozen=True, slots=True)
class GameEvent:
    """Game properties changed (difficulty, game mode, etc.)."""


@dataclass(frozen=True, slots=True)
class SpawnResetEvent:
    """Spawn point was reset."""


@dataclass(frozen=True, slots=True)
class SleepEvent:
    """Bot started sleeping."""


@dataclass(frozen=True, slots=True)
class WakeEvent:
    """Bot woke up."""


@dataclass(frozen=True, slots=True)
class HeldItemChangedEvent:
    """Bot held item changed.

    Ref: mineflayer/lib/plugins/inventory.js:670-672 — held_item_slot
    packet triggers setQuickBarSlot before emitting heldItemChanged,
    so ``quick_bar_slot`` is already up-to-date when this fires.
    """

    item: ItemStack | None
    quick_bar_slot: int


# -- Movement --


@dataclass(frozen=True, slots=True)
class MoveEvent:
    """Bot position changed."""

    position: Vec3


@dataclass(frozen=True, slots=True)
class ForcedMoveEvent:
    """Bot was teleported by the server."""


@dataclass(frozen=True, slots=True)
class MountEvent:
    """Bot mounted a vehicle."""


@dataclass(frozen=True, slots=True)
class DismountEvent:
    """Bot dismounted from a vehicle."""

    vehicle_id: int


# -- Navigation --


@dataclass(frozen=True, slots=True)
class GoalReachedEvent:
    """Navigation goal was reached."""

    position: Vec3


@dataclass(frozen=True, slots=True)
class GoalFailedEvent:
    """Navigation goal could not be reached."""

    reason: str


# -- Entity Events --


@dataclass(frozen=True, slots=True)
class EntitySpawnEvent:
    """A new entity spawned in the world."""

    entity_id: int
    entity: Entity | None = None


@dataclass(frozen=True, slots=True)
class EntityGoneEvent:
    """An entity was removed from the world."""

    entity_id: int


@dataclass(frozen=True, slots=True)
class EntityMovedEvent:
    """An entity moved."""

    entity_id: int
    position: Vec3


@dataclass(frozen=True, slots=True)
class EntityUpdateEvent:
    """An entity was updated."""

    entity_id: int
    entity: Entity | None = None


@dataclass(frozen=True, slots=True)
class EntitySwingArmEvent:
    """An entity swung its arm."""

    entity_id: int


@dataclass(frozen=True, slots=True)
class EntityHurtEvent:
    """An entity was hurt."""

    entity_id: int


@dataclass(frozen=True, slots=True)
class EntityDeadEvent:
    """An entity died."""

    entity_id: int


@dataclass(frozen=True, slots=True)
class EntityTamingEvent:
    """An entity is being tamed."""

    entity_id: int


@dataclass(frozen=True, slots=True)
class EntityTamedEvent:
    """An entity was tamed."""

    entity_id: int


@dataclass(frozen=True, slots=True)
class EntityShakingOffWaterEvent:
    """An entity is shaking off water."""

    entity_id: int


@dataclass(frozen=True, slots=True)
class EntityEatingGrassEvent:
    """An entity is eating grass."""

    entity_id: int


@dataclass(frozen=True, slots=True)
class EntityHandSwapEvent:
    """An entity swapped hand items."""

    entity_id: int


@dataclass(frozen=True, slots=True)
class EntityWakeEvent:
    """An entity woke up."""

    entity_id: int


@dataclass(frozen=True, slots=True)
class EntityEatEvent:
    """An entity is eating."""

    entity_id: int


@dataclass(frozen=True, slots=True)
class EntityCriticalEffectEvent:
    """An entity triggered a critical hit effect."""

    entity_id: int


@dataclass(frozen=True, slots=True)
class EntityMagicCriticalEffectEvent:
    """An entity triggered a magic critical hit effect."""

    entity_id: int


@dataclass(frozen=True, slots=True)
class EntityCrouchEvent:
    """An entity crouched."""

    entity_id: int


@dataclass(frozen=True, slots=True)
class EntityUncrouchEvent:
    """An entity stopped crouching."""

    entity_id: int


@dataclass(frozen=True, slots=True)
class EntityEquipEvent:
    """An entity changed equipment."""

    entity_id: int


@dataclass(frozen=True, slots=True)
class EntitySleepEvent:
    """An entity started sleeping."""

    entity_id: int


@dataclass(frozen=True, slots=True)
class EntityElytraFlewEvent:
    """An entity started flying with elytra."""

    entity_id: int


@dataclass(frozen=True, slots=True)
class EntityAttachEvent:
    """An entity attached to a vehicle."""

    entity_id: int
    vehicle_id: int


@dataclass(frozen=True, slots=True)
class EntityDetachEvent:
    """An entity detached from a vehicle."""

    entity_id: int
    vehicle_id: int


@dataclass(frozen=True, slots=True)
class EntityEffectEvent:
    """A status effect was applied to an entity."""

    entity_id: int
    effect_id: int
    amplifier: int
    duration: int


@dataclass(frozen=True, slots=True)
class EntityEffectEndEvent:
    """A status effect ended on an entity."""

    entity_id: int
    effect_id: int


@dataclass(frozen=True, slots=True)
class EntityAttributesEvent:
    """Entity attributes were updated."""

    entity_id: int


@dataclass(frozen=True, slots=True)
class ItemDropEvent:
    """An item entity was dropped."""

    entity_id: int


@dataclass(frozen=True, slots=True)
class PlayerCollectEvent:
    """A player collected an item entity."""

    collector_id: int
    collected_id: int


# -- Player Events --


@dataclass(frozen=True, slots=True)
class PlayerJoinedEvent:
    """A player joined the server.

    Ref: mineflayer/docs/api.md — "playerJoined" (player)
    """

    username: str
    uuid: str
    ping: int
    game_mode: int
    display_name: str | None


@dataclass(frozen=True, slots=True)
class PlayerUpdatedEvent:
    """A player's info was updated.

    Ref: mineflayer/docs/api.md — "playerUpdated" (player)
    """

    username: str
    uuid: str
    ping: int
    game_mode: int
    display_name: str | None


@dataclass(frozen=True, slots=True)
class PlayerLeftEvent:
    """A player left the server.

    Ref: mineflayer/docs/api.md — "playerLeft" (player)
    """

    username: str


# -- Block Events --


@dataclass(frozen=True, slots=True)
class BlockBrokenEvent:
    """A block was successfully broken by the bot."""

    block_name: str
    position: Vec3


@dataclass(frozen=True, slots=True)
class BlockUpdateEvent:
    """A block was updated in the world."""

    position: Vec3
    old_block_name: str | None
    new_block_name: str | None


@dataclass(frozen=True, slots=True)
class BlockPlacedEvent:
    """A block was placed in the world."""

    position: Vec3
    old_block_name: str | None
    new_block_name: str | None


@dataclass(frozen=True, slots=True)
class ChunkColumnLoadEvent:
    """A chunk column was loaded."""

    position: Vec3


@dataclass(frozen=True, slots=True)
class ChunkColumnUnloadEvent:
    """A chunk column was unloaded."""

    position: Vec3


# -- Digging --


@dataclass(frozen=True, slots=True)
class DiggingCompletedEvent:
    """Digging was completed."""

    position: Vec3
    block_name: str


@dataclass(frozen=True, slots=True)
class DiggingAbortedEvent:
    """Digging was aborted."""

    position: Vec3
    block_name: str


@dataclass(frozen=True, slots=True)
class BlockBreakProgressObservedEvent:
    """Block break progress was observed from another entity."""

    position: Vec3
    destroy_stage: int
    entity_id: int


@dataclass(frozen=True, slots=True)
class BlockBreakProgressEndEvent:
    """Block break progress ended."""

    position: Vec3
    entity_id: int


# -- Collection --


@dataclass(frozen=True, slots=True)
class CollectCompletedEvent:
    """Item collection completed."""

    item_name: str
    count: int


# -- Sound Events --


@dataclass(frozen=True, slots=True)
class SoundEffectHeardEvent:
    """A named sound effect was heard."""

    sound_name: str
    position: Vec3
    volume: float
    pitch: float


@dataclass(frozen=True, slots=True)
class HardcodedSoundEffectHeardEvent:
    """A hardcoded sound effect was heard."""

    sound_id: int
    sound_category: int
    position: Vec3
    volume: float
    pitch: float


@dataclass(frozen=True, slots=True)
class NoteHeardEvent:
    """A note block was heard."""

    position: Vec3
    instrument_id: int
    pitch: int


# -- Weather & Time --


@dataclass(frozen=True, slots=True)
class RainEvent:
    """Rain started or stopped."""


@dataclass(frozen=True, slots=True)
class WeatherUpdateEvent:
    """Weather state was updated."""

    rain_state: float
    thunder_state: float


@dataclass(frozen=True, slots=True)
class TimeEvent:
    """World time changed."""

    time_of_day: int
    age: int


# -- World Events --


@dataclass(frozen=True, slots=True)
class PistonMoveEvent:
    """A piston moved."""

    position: Vec3
    is_pulling: bool
    direction: int


@dataclass(frozen=True, slots=True)
class ChestLidMoveEvent:
    """A chest lid opened or closed."""

    position: Vec3
    is_open: int


@dataclass(frozen=True, slots=True)
class UsedFireworkEvent:
    """A firework was used for elytra boost."""

    firework_entity_id: int


# -- Window Events --


@dataclass(frozen=True, slots=True)
class WindowOpenEvent:
    """A window (container) was opened."""

    window_id: int


@dataclass(frozen=True, slots=True)
class WindowCloseEvent:
    """A window (container) was closed."""

    window_id: int


# -- Resource Pack --


@dataclass(frozen=True, slots=True)
class ResourcePackEvent:
    """Server requested a resource pack."""

    url: str
    hash: str


# -- Scoreboard Events --


@dataclass(frozen=True, slots=True)
class ScoreboardCreatedEvent:
    """A scoreboard objective was created."""

    name: str


@dataclass(frozen=True, slots=True)
class ScoreboardDeletedEvent:
    """A scoreboard objective was deleted."""

    name: str


@dataclass(frozen=True, slots=True)
class ScoreboardTitleChangedEvent:
    """A scoreboard title was changed."""

    name: str


@dataclass(frozen=True, slots=True)
class ScoreUpdatedEvent:
    """A score was updated."""

    scoreboard_name: str
    item_name: str
    value: int


@dataclass(frozen=True, slots=True)
class ScoreRemovedEvent:
    """A score was removed."""

    scoreboard_name: str
    item_name: str


@dataclass(frozen=True, slots=True)
class ScoreboardPositionEvent:
    """A scoreboard display position was set."""

    position: int
    scoreboard_name: str


# -- Team Events --


@dataclass(frozen=True, slots=True)
class TeamCreatedEvent:
    """A team was created."""

    name: str


@dataclass(frozen=True, slots=True)
class TeamRemovedEvent:
    """A team was removed."""

    name: str


@dataclass(frozen=True, slots=True)
class TeamUpdatedEvent:
    """A team was updated."""

    name: str


@dataclass(frozen=True, slots=True)
class TeamMemberAddedEvent:
    """A member was added to a team."""

    team_name: str


@dataclass(frozen=True, slots=True)
class TeamMemberRemovedEvent:
    """A member was removed from a team."""

    team_name: str


# -- Boss Bar Events --


@dataclass(frozen=True, slots=True)
class BossBarCreatedEvent:
    """A boss bar was created."""

    entity_uuid: str
    title: str
    health: float


@dataclass(frozen=True, slots=True)
class BossBarDeletedEvent:
    """A boss bar was deleted."""

    entity_uuid: str


@dataclass(frozen=True, slots=True)
class BossBarUpdatedEvent:
    """A boss bar was updated."""

    entity_uuid: str
    title: str
    health: float


# -- Physics & Particles --


@dataclass(frozen=True, slots=True)
class PhysicsTickEvent:
    """A physics tick occurred."""


@dataclass(frozen=True, slots=True)
class ParticleEvent:
    """A particle effect was spawned."""

    particle_id: int
    particle_name: str
    position: Vec3
    count: int
