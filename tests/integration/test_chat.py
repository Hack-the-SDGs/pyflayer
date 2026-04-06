"""Integration test: chat functionality."""

import asyncio

import pytest

from minethon import Bot
from minethon.models.events import ChatEvent


@pytest.mark.integration
async def test_send_chat() -> None:
    """Bot can send a chat message without error."""
    bot = Bot(host="localhost", port=25565, username="chat_bot")
    await bot.connect()
    try:
        await bot.wait_until_spawned()
        await bot.chat("integration test message")
    finally:
        await bot.disconnect()


@pytest.mark.integration
async def test_receive_chat_event() -> None:
    """Bot receives chat events (requires another player or bot)."""
    bot = Bot(host="localhost", port=25565, username="listener_bot")
    received: list[ChatEvent] = []

    @bot.observe.on(ChatEvent)
    async def on_chat(event: ChatEvent) -> None:
        received.append(event)

    await bot.connect()
    try:
        await bot.wait_until_spawned()
        await bot.chat("hello from test")
        await asyncio.sleep(1.0)
        # We should at least see our own message
        assert any(e.message == "hello from test" for e in received)
    finally:
        await bot.disconnect()
