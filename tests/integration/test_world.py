"""Integration test: world queries."""

import pytest

from pyflayer import Bot


@pytest.mark.integration
async def test_block_at() -> None:
    """Bot can query block at a known position."""
    bot = Bot(host="localhost", port=25565, username="world_bot")
    await bot.connect()
    try:
        await bot.wait_until_spawned()
        pos = bot.position
        block = await bot.block_at(int(pos.x), int(pos.y) - 1, int(pos.z))
        assert block is not None
        assert block.name  # Should have a name
    finally:
        await bot.disconnect()


@pytest.mark.integration
async def test_find_block() -> None:
    """Bot can search for blocks by name."""
    bot = Bot(host="localhost", port=25565, username="finder_bot")
    await bot.connect()
    try:
        await bot.wait_until_spawned()
        # Stone should exist in most worlds
        blocks = await bot.find_block("stone", max_distance=32, count=1)
        # May or may not find any, but should not raise
        assert isinstance(blocks, list)
    finally:
        await bot.disconnect()
