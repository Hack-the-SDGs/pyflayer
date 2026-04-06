"""Item stack type for inventory items."""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ItemStack:
    """An immutable snapshot of an inventory item stack.

    Attributes:
        name: Internal item name (e.g. ``"diamond_pickaxe"``).
        display_name: Human-readable name (e.g. ``"Diamond Pickaxe"``).
        count: Number of items in this stack.
        slot: Inventory slot index.
        max_stack_size: Maximum stack size for this item type.
        enchantments: List of enchantment dicts, or ``None``.
        nbt: Raw NBT data as a dict, or ``None``.
    """

    name: str
    display_name: str
    count: int
    slot: int
    max_stack_size: int
    enchantments: list[dict[str, Any]] | None = None
    nbt: dict[str, Any] | None = None
