"""Integration test: basic connection lifecycle."""

import pytest

from minethon import Bot


@pytest.mark.integration
async def test_connect_and_disconnect() -> None:
    """Bot can connect to a local server and cleanly disconnect."""
    bot = Bot(host="localhost", port=25565, username="test_bot")
    await bot.connect()
    assert bot.is_connected
    await bot.disconnect()
    assert not bot.is_connected


@pytest.mark.integration
async def test_spawn_and_position() -> None:
    """Bot spawns and reports a valid position."""
    bot = Bot(host="localhost", port=25565, username="test_bot")
    await bot.connect()
    try:
        await bot.wait_until_spawned(timeout=30.0)
        pos = bot.position
        assert pos.x is not None
        assert bot.health > 0
    finally:
        await bot.disconnect()
