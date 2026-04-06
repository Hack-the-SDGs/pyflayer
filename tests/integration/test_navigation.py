"""Integration test: navigation."""

import pytest

from minethon import Bot


@pytest.mark.integration
async def test_goto_nearby() -> None:
    """Bot can navigate to a nearby position."""
    bot = Bot(host="localhost", port=25565, username="nav_bot")
    await bot.connect()
    try:
        await bot.wait_until_spawned()
        pos = bot.position
        # Move 5 blocks in the X direction
        await bot.goto(pos.x + 5, pos.y, pos.z, radius=2.0)
        new_pos = bot.position
        assert abs(new_pos.x - (pos.x + 5)) < 3.0
    finally:
        await bot.disconnect()


@pytest.mark.integration
async def test_look_at() -> None:
    """Bot can look at a position."""
    bot = Bot(host="localhost", port=25565, username="look_bot")
    await bot.connect()
    try:
        await bot.wait_until_spawned()
        await bot.look_at(0.0, 64.0, 0.0)
    finally:
        await bot.disconnect()
