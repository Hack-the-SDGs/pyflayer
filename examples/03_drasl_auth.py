"""03_drasl_auth.py -- Connect via a custom Drasl auth server.

Run with:
    cp examples/.env.example examples/.env
    # Edit examples/.env with your credentials, then:
    uv run --env-file examples/.env examples/03_drasl_auth.py
"""

import asyncio
import os

from pyflayer import Bot


async def main() -> None:
    bot = Bot(
        host="localhost",
        port=25565,
        username=os.environ["MC_USERNAME"],
        password=os.environ["MC_PASSWORD"],
        auth="mojang",
        auth_server=os.environ["MC_AUTH_SERVER"],
        session_server=os.environ["MC_SESSION_SERVER"],
    )

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
