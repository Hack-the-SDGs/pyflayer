"""High-level event dataclasses."""

from dataclasses import dataclass

from pyflayer.models.vec3 import Vec3


@dataclass(frozen=True, slots=True)
class SpawnEvent:
    """Bot has spawned in the world."""


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
class HealthChangedEvent:
    """Bot health, food, or saturation changed."""

    health: float
    food: float
    saturation: float


@dataclass(frozen=True, slots=True)
class DeathEvent:
    """Bot has died."""

    reason: str | None


@dataclass(frozen=True, slots=True)
class KickedEvent:
    """Bot was kicked from the server."""

    reason: str
    logged_in: bool


@dataclass(frozen=True, slots=True)
class GoalReachedEvent:
    """Navigation goal was reached."""

    position: Vec3


@dataclass(frozen=True, slots=True)
class GoalFailedEvent:
    """Navigation goal could not be reached."""

    reason: str


@dataclass(frozen=True, slots=True)
class BlockBrokenEvent:
    """A block was successfully broken by the bot."""

    block_name: str
    position: Vec3


@dataclass(frozen=True, slots=True)
class CollectCompletedEvent:
    """Item collection completed."""

    item_name: str
    count: int
