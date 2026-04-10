"""Convert JS proxy objects to Python domain models.

All functions in this module accept a raw JSPyBridge proxy and return
the corresponding :mod:`minethon.models` dataclass.  They are the sole
boundary between Layer 1 (bridge) and Layer 2 (domain model).
"""

from typing import Any

from minethon.models.block import Block
from minethon.models.entity import Entity, EntityKind
from minethon.models.item import ItemStack
from minethon.models.recipe import Recipe
from minethon.models.vec3 import Vec3
from minethon.models.window import TradeOffer, VillagerSession, WindowHandle


def js_vec3_to_vec3(js_obj: Any) -> Vec3:
    """Convert a JS ``Vec3`` proxy to :class:`Vec3`."""
    return Vec3(
        x=float(js_obj.x),
        y=float(js_obj.y),
        z=float(js_obj.z),
    )


def js_block_to_block(js_obj: Any) -> Block:
    """Convert a JS ``Block`` proxy to :class:`Block`.

    Args:
        js_obj: A mineflayer Block proxy object.

    Returns:
        An immutable :class:`Block` snapshot.
    """
    pos = js_obj.position
    hardness = js_obj.hardness
    return Block(
        name=str(js_obj.name),
        display_name=str(js_obj.displayName),
        position=Vec3(float(pos.x), float(pos.y), float(pos.z)),
        hardness=float(hardness) if hardness is not None else None,
        is_solid=bool(js_obj.boundingBox == "block"),
        is_liquid=bool(getattr(js_obj, "liquid", False)),
        bounding_box=str(js_obj.boundingBox),
    )


_ENTITY_KIND_MAP: dict[str, EntityKind] = {
    "player": EntityKind.PLAYER,
    "mob": EntityKind.MOB,
    "animal": EntityKind.ANIMAL,
    "hostile": EntityKind.HOSTILE,
    "projectile": EntityKind.PROJECTILE,
    "object": EntityKind.OBJECT,
}


def _classify_entity(js_entity: Any) -> EntityKind:
    """Determine :class:`EntityKind` from a JS entity proxy."""
    entity_type = getattr(js_entity, "type", None)
    if entity_type is not None:
        kind = _ENTITY_KIND_MAP.get(str(entity_type))
        if kind is not None:
            return kind
    return EntityKind.OTHER


def js_entity_to_entity(js_obj: Any) -> Entity:
    """Convert a JS ``Entity`` proxy to :class:`Entity`.

    Args:
        js_obj: A mineflayer Entity proxy object.

    Returns:
        An immutable :class:`Entity` snapshot.
    """
    pos = js_obj.position
    position = Vec3(float(pos.x), float(pos.y), float(pos.z))

    velocity: Vec3 | None = None
    js_vel = getattr(js_obj, "velocity", None)
    if js_vel is not None:
        try:
            velocity = Vec3(float(js_vel.x), float(js_vel.y), float(js_vel.z))
        except (AttributeError, TypeError):
            pass

    health: float | None = None
    js_health = getattr(js_obj, "health", None)
    if js_health is not None:
        try:
            health = float(js_health)
        except (TypeError, ValueError):
            pass

    name: str | None = None
    # Prefer username (set for players) over name (entity type string).
    # Player entities have name="player", so checking name first would
    # produce a misleading Entity.name value.
    js_name = getattr(js_obj, "username", None) or getattr(js_obj, "name", None)
    if js_name is not None:
        name = str(js_name)

    metadata: dict[str, Any] | None = None
    js_meta = getattr(js_obj, "metadata", None)
    if js_meta is not None:
        try:
            metadata = dict(js_meta.valueOf())
        except (AttributeError, TypeError, ValueError):
            pass

    return Entity(
        id=int(js_obj.id),
        name=name,
        kind=_classify_entity(js_obj),
        position=position,
        velocity=velocity,
        health=health,
        metadata=metadata,
    )


def js_item_to_item_stack(js_obj: Any) -> ItemStack:
    """Convert a JS ``Item`` proxy to :class:`ItemStack`.

    Args:
        js_obj: A mineflayer Item proxy object.

    Returns:
        An immutable :class:`ItemStack` snapshot.
    """
    enchants: list[dict[str, Any]] | None = None
    js_enchants = getattr(js_obj, "enchants", None)
    if js_enchants is not None:
        try:
            enchants = list(js_enchants.valueOf())
        except (AttributeError, TypeError):
            pass

    nbt: dict[str, Any] | None = None
    js_nbt = getattr(js_obj, "nbt", None)
    if js_nbt is not None:
        try:
            nbt = dict(js_nbt.valueOf())
        except (AttributeError, TypeError):
            pass

    return ItemStack(
        name=str(js_obj.name),
        display_name=str(js_obj.displayName),
        count=int(js_obj.count),
        slot=int(js_obj.slot),
        max_stack_size=int(js_obj.stackSize),
        enchantments=enchants,
        nbt=nbt,
    )


def js_recipe_to_recipe(js_obj: Any) -> Recipe:
    """Wrap a JS ``Recipe`` proxy in an opaque typed handle."""
    return Recipe(_raw=js_obj)


def js_window_to_window_handle(js_obj: Any) -> WindowHandle:
    """Convert a JS ``Window`` proxy to a pure-Python handle.

    The caller is responsible for registering the JS proxy in the
    window registry (``Bot._window_registry``) keyed by ``handle.id``.
    """
    return WindowHandle(
        id=int(js_obj.id),
        title=str(js_obj.title),
        kind=str(js_obj.type),
    )


def _dict_to_item_stack(raw: dict[str, Any]) -> ItemStack:
    """Convert a plain dict (from JS snapshot) to :class:`ItemStack`."""
    enchants = raw.get("enchants")
    nbt = raw.get("nbt")
    return ItemStack(
        name=str(raw["name"]),
        display_name=str(raw["displayName"]) if raw.get("displayName") else str(raw["name"]),
        count=int(raw["count"]),
        slot=int(raw["slot"]),
        max_stack_size=int(raw["stackSize"]),
        enchantments=list(enchants) if enchants else None,
        nbt=dict(nbt) if nbt else None,
    )


def villager_snapshot_to_session(data: dict[str, Any]) -> VillagerSession:
    """Convert a plain dict snapshot to :class:`VillagerSession`.

    Expects output from ``helpers.snapshotVillagerSession()``.
    """
    trades: list[TradeOffer] = []
    for trade in data.get("trades", []) or []:
        secondary = trade.get("inputItem2")
        trades.append(
            TradeOffer(
                first_input=_dict_to_item_stack(trade["inputItem1"]),
                output=_dict_to_item_stack(trade["outputItem"]),
                secondary_input=(
                    _dict_to_item_stack(secondary) if secondary else None
                ),
                disabled=bool(trade.get("tradeDisabled", False)),
                uses=int(trade.get("nbTradeUses", 0)),
                max_uses=int(trade.get("maximumNbTradeUses", 0)),
            )
        )
    return VillagerSession(
        id=int(data["id"]),
        title=str(data["title"]),
        trades=tuple(trades),
    )
