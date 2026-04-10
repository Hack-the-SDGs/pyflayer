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
    MinethonConnectionError,
    MinethonError,
    NavigationError,
    NotSpawnedError,
    PluginError,
)
from minethon.models.events import (
    BlockBrokenEvent,
    ChatEvent,
    CollectCompletedEvent,
    DeathEvent,
    EndEvent,
    GoalFailedEvent,
    GoalReachedEvent,
    HealthChangedEvent,
    KickedEvent,
    SpawnEvent,
    WhisperEvent,
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
    # Types
    "Block",
    # Events
    "BlockBrokenEvent",
    # Core
    "Bot",
    # Errors
    "BridgeError",
    "ChatEvent",
    "CollectCompletedEvent",
    "DeathEvent",
    "EndEvent",
    "Entity",
    "EntityKind",
    "Experience",
    "GameState",
    "GoalFailedEvent",
    "GoalReachedEvent",
    "HealthChangedEvent",
    "InventoryError",
    "ItemStack",
    "KickedEvent",
    "MinethonConnectionError",
    "MinethonError",
    # Sub-APIs
    "NavigationAPI",
    "NavigationError",
    "NotSpawnedError",
    "ObserveAPI",
    "PlayerInfo",
    "PluginAPI",
    "PluginError",
    "RawBotHandle",
    "Recipe",
    "SpawnEvent",
    "TimeState",
    "TradeOffer",
    "Vec3",
    "VillagerSession",
    "WhisperEvent",
    "WindowHandle",
]
