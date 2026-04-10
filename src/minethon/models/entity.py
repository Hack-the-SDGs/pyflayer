"""Entity types for mobs, players, and other world entities."""

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from minethon.models.vec3 import Vec3


class EntityKind(Enum):
    """Classification of an entity."""

    PLAYER = "player"
    MOB = "mob"
    ANIMAL = "animal"
    HOSTILE = "hostile"
    PROJECTILE = "projectile"
    OBJECT = "object"
    OTHER = "other"


@dataclass(frozen=True, slots=True)
class Entity:
    """An immutable snapshot of a world entity.

    Attributes:
        id: Numeric entity ID assigned by the server.
        name: Entity type name (e.g. ``"zombie"``, ``"Steve"``),
            or ``None`` if unknown.
        kind: High-level classification.
        position: Current position in the world.
        velocity: Current velocity, or ``None`` if unavailable.
        health: Current health points, or ``None`` if unknown.
        metadata: Raw metadata dict, or ``None``.
    """

    id: int
    name: str | None
    kind: EntityKind
    position: Vec3
    velocity: Vec3 | None = None
    health: float | None = None
    metadata: dict[str, Any] | None = None
