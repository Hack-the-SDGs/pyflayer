"""Runtime-importable type shells.

These classes exist so users can write annotations like
`from minethon.models import ChatMessage` without hitting ImportError.
Their real member surfaces live in `src/minethon/bot.pyi`.
"""

from __future__ import annotations


def _shell(name: str) -> type:
    return type(
        name,
        (),
        {
            "__module__": __name__,
            "__doc__": "Runtime type shell. See `minethon.bot` stubs for members.",
        },
    )


TYPE_SHELL_NAMES = (
    "Vec3",
    "ChatMessageScore",
    "ChatMessage",
    "Effect",
    "Entity",
    "Block",
    "Item",
    "Window",
    "Recipe",
    "Move",
    "Goal",
    "GoalBlock",
    "GoalNear",
    "GoalXZ",
    "GoalNearXZ",
    "GoalY",
    "GoalGetToBlock",
    "GoalFollow",
    "GoalCompositeAll",
    "GoalCompositeAny",
    "GoalInvert",
    "GoalPlaceBlock",
    "GoalLookAtBlock",
    "GoalBreakBlock",
    "Goals",
    "Movements",
    "Pathfinder",
    "ComputedPath",
    "PartiallyComputedPath",
    "PathfinderModule",
    "Player",
    "ChatPattern",
    "SkinParts",
    "GameSettings",
    "GameState",
    "Experience",
    "PhysicsOptions",
    "Time",
    "ControlStateStatus",
    "Instrument",
    "FindBlockOptions",
    "TransferOptions",
    "creativeMethods",
    "simpleClick",
    "Tablist",
    "chatPatternOptions",
    "CommandBlockOptions",
    "VillagerTrade",
    "Enchantment",
    "Chest",
    "Dispenser",
    "Furnace",
    "EnchantmentTable",
    "Anvil",
    "Villager",
)

globals().update({name: _shell(name) for name in TYPE_SHELL_NAMES})


class BotOptions(dict[str, object]):
    """Runtime shell for the generated `TypedDict` in `bot.pyi`."""
