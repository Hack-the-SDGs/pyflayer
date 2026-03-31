"""01_hello_bot.py -- Basic pyflayer bot."""

import asyncio

from pyflayer import Bot
from pyflayer.models.events import ChatEvent


async def main() -> None:
    bot = Bot(host="192.168.10.101", port=50213, username="pybot")

    @bot.observe.on(ChatEvent)
    async def on_chat(event: ChatEvent) -> None:
        if event.sender != bot.username:
            await bot.chat(f"You said: {event.message}")

    await bot.connect()
    await bot.wait_until_spawned()
    print(f"Bot spawned at {bot.position}")
    await bot.chat("Hello from pyflayer!")

    try:
        while bot.is_connected:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        await bot.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
