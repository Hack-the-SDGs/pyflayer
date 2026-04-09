"""minethon -- A Python-first Mineflayer SDK."""

from minethon.api.navigation import NavigationAPI
from minethon.api.observe import ObserveAPI
from minethon.api.plugins import PluginAPI
from minethon.bot import Bot
from minethon.models.block import Block
from minethon.models.entity import Entity, EntityKind
from minethon.models.errors import (
    BridgeError,
    InventoryError,
    NavigationError,
    NotSpawnedError,
    PluginError,
    MinethonConnectionError,
    MinethonError,
)
from minethon.models.experience import Experience
from minethon.models.game_state import GameState
from minethon.models.item import ItemStack
from minethon.models.player_info import PlayerInfo
from minethon.models.recipe import Recipe
from minethon.models.time_state import TimeState
from minethon.models.vec3 import Vec3
from minethon.models.window import TradeOffer, VillagerSession, WindowHandle
from minethon.raw import RawBotHandle

__all__ = [
    # Core
    "Bot",
    "RawBotHandle",
    # Sub-APIs
    "NavigationAPI",
    "ObserveAPI",
    "PluginAPI",
    # Types
    "Block",
    "Entity",
    "EntityKind",
    "Experience",
    "GameState",
    "ItemStack",
    "PlayerInfo",
    "Recipe",
    "TimeState",
    "TradeOffer",
    "Vec3",
    "VillagerSession",
    "WindowHandle",
    # Errors
    "BridgeError",
    "InventoryError",
    "MinethonConnectionError",
    "MinethonError",
    "NavigationError",
    "NotSpawnedError",
    "PluginError",
]
