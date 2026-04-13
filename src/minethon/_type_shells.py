"""Runtime-importable type shells.

These classes exist so users can write annotations like
`from minethon.models import ChatMessage` without hitting ImportError.
Their real member surfaces live in `src/minethon/bot.pyi`.
"""

from __future__ import annotations


class _Shell:
    """Runtime type shell. See `minethon.bot` stubs for members."""


class Vec3(_Shell):
    pass


class ChatMessageScore(_Shell):
    pass


class ChatMessage(_Shell):
    pass


class Effect(_Shell):
    pass


class Entity(_Shell):
    pass


class Block(_Shell):
    pass


class Item(_Shell):
    pass


class Window(_Shell):
    pass


class Recipe(_Shell):
    pass


class Move(_Shell):
    pass


class Goal(_Shell):
    pass


class GoalBlock(_Shell):
    pass


class GoalNear(_Shell):
    pass


class GoalXZ(_Shell):
    pass


class GoalNearXZ(_Shell):
    pass


class GoalY(_Shell):
    pass


class GoalGetToBlock(_Shell):
    pass


class GoalFollow(_Shell):
    pass


class GoalCompositeAll(_Shell):
    pass


class GoalCompositeAny(_Shell):
    pass


class GoalInvert(_Shell):
    pass


class GoalPlaceBlock(_Shell):
    pass


class GoalLookAtBlock(_Shell):
    pass


class GoalBreakBlock(_Shell):
    pass


class Goals(_Shell):
    pass


class Movements(_Shell):
    pass


class Pathfinder(_Shell):
    pass


class ComputedPath(_Shell):
    pass


class PartiallyComputedPath(_Shell):
    pass


class PathfinderModule(_Shell):
    pass


class Player(_Shell):
    pass


class SkinData(_Shell):
    pass


class ChatPattern(_Shell):
    pass


class SkinParts(_Shell):
    pass


class GameSettings(_Shell):
    pass


class GameState(_Shell):
    pass


class Experience(_Shell):
    pass


class PhysicsOptions(_Shell):
    pass


class Time(_Shell):
    pass


class ControlStateStatus(_Shell):
    pass


class Instrument(_Shell):
    pass


class FindBlockOptions(_Shell):
    pass


class TransferOptions(_Shell):
    pass


class creativeMethods(_Shell):  # noqa: N801
    pass


class simpleClick(_Shell):  # noqa: N801
    pass


class Tablist(_Shell):
    pass


class chatPatternOptions(_Shell):  # noqa: N801
    pass


class CommandBlockOptions(_Shell):
    pass


class VillagerTrade(_Shell):
    pass


class Enchantment(_Shell):
    pass


class Chest(_Shell):
    pass


class Dispenser(_Shell):
    pass


class Furnace(_Shell):
    pass


class EnchantmentTable(_Shell):
    pass


class Anvil(_Shell):
    pass


class Villager(_Shell):
    pass


class ScoreBoard(_Shell):
    pass


class ScoreBoardItem(_Shell):
    pass


class Team(_Shell):
    pass


class BossBar(_Shell):
    pass


class Particle(_Shell):
    pass


class Location(_Shell):
    pass


class Painting(_Shell):
    pass


class BotOptions(dict[str, object]):
    """Runtime shell for the generated `TypedDict` in `bot.pyi`."""


class CreateBotOptions(dict[str, object]):
    """Runtime shell for the snake-case `TypedDict` in `bot.pyi`."""


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
    "SkinData",
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
    "ScoreBoard",
    "ScoreBoardItem",
    "Team",
    "BossBar",
    "Particle",
    "Location",
    "Painting",
    "BotOptions",
    "CreateBotOptions",
)
