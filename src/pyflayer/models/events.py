"""High-level event dataclasses."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SpawnEvent:
    """Bot has spawned in the world."""


@dataclass(frozen=True, slots=True)
class ChatEvent:
    """A chat message was received."""

    sender: str
    message: str
    timestamp: float
