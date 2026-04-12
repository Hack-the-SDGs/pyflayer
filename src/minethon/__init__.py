"""minethon — a Python-first Mineflayer SDK.

Typical usage::

    from minethon import BotEvent, create_bot

    bot = create_bot(
        host="mc.example.com",
        port=25565,
        username="my_bot",
    )

    @bot.on_spawn
    def on_spawn() -> None:
        bot.chat("Hello from minethon!")

    @bot.on(BotEvent.CHAT)
    def on_chat(username: str, message: str, *_: object) -> None:
        if message == "quit":
            bot.quit("bye")

    bot.run_forever()
"""

from __future__ import annotations

from minethon._events import BotEvent
from minethon.bot import Bot, create_bot
from minethon.errors import (
    MinethonError,
    NotSpawnedError,
    PlayerNotFoundError,
    PluginNotInstalledError,
    VersionPinRequiredError,
)

__all__ = [
    "Bot",
    "BotEvent",
    "MinethonError",
    "NotSpawnedError",
    "PlayerNotFoundError",
    "PluginNotInstalledError",
    "VersionPinRequiredError",
    "create_bot",
]
