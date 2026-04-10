"""Block type for world blocks."""

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from minethon.models.vec3 import Vec3


@dataclass(frozen=True, slots=True)
class Block:
    """An immutable snapshot of a world block.

    Attributes:
        name: Internal block name (e.g. ``"oak_log"``).
        display_name: Human-readable name (e.g. ``"Oak Log"``).
        position: Block position in the world.
        hardness: Time multiplier for mining, or ``None`` if unbreakable.
        is_solid: Whether the block has a solid bounding box.
        is_liquid: Whether the block is a liquid (water/lava).
        bounding_box: ``"block"`` for solid, ``"empty"`` for passable.
    """

    name: str
    display_name: str
    position: Vec3
    hardness: float | None
    is_solid: bool
    is_liquid: bool
    bounding_box: str
