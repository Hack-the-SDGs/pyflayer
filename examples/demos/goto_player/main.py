"""goto_player -- Navigate to and follow players on command."""

import asyncio

from minethon import Bot
from minethon.models.events import ChatEvent


async def main() -> None:
    bot = Bot(host="localhost", port=25565, username="follower")

    @bot.observe.on(ChatEvent)
    async def on_chat(event: ChatEvent) -> None:
        if event.sender == bot.username:
            return

        parts = event.message.split()
        cmd = parts[0] if parts else ""

        if cmd == "come":
            await bot.chat(f"Walking to you, {event.sender}!")
            try:
                entity = await bot.find_entity(name=event.sender)
                if entity is None:
                    await bot.chat("I can't see you!")
                    return
                pos = entity.position
                await bot.goto(pos.x, pos.y, pos.z)
                await bot.chat("I'm here!")
            except Exception as exc:
                await bot.chat(f"Navigation failed: {exc}")

        elif cmd == "follow":
            try:
                await bot.navigation.follow(event.sender, distance=2.0)
                await bot.chat(f"Following {event.sender}!")
            except Exception as exc:
                await bot.chat(f"Can't follow: {exc}")

        elif cmd == "stop":
            await bot.navigation.stop()
            await bot.chat("Stopped!")

    await bot.connect()
    await bot.wait_until_spawned()
    print(f"Bot spawned at {bot.position}")
    await bot.chat("Commands: 'come', 'follow', 'stop'")

    try:
        while bot.is_connected:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        await bot.disconnect()


asyncio.run(main())
