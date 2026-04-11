"""Typed public API for the mineflayer-tool plugin."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from minethon._bridge._events import ToolEquipDoneEvent
from minethon.models.errors import BridgeError

if TYPE_CHECKING:
    from minethon._bridge.event_relay import EventRelay
    from minethon._bridge.plugins.tool_plugin import ToolBridge
    from minethon.models.block import Block


class ToolAPI:
    """Equip the best tool for mining a given block.

    Wraps ``mineflayer-tool`` through the bridge layer.  The public
    API never touches ``_js_bot`` directly.

    Example::

        await bot.tool.equip_for_block(block)
        await bot.tool.equip_for_block(block, require_harvest=True)

    Ref: mineflayer-tool/lib/Tool.js — ``equipForBlock``
    """

    def __init__(self, bridge: ToolBridge, relay: EventRelay) -> None:
        self._bridge = bridge
        self._relay = relay
        self._equip_lock = asyncio.Lock()

    async def equip_for_block(
        self,
        block: Block,
        *,
        require_harvest: bool = False,
        timeout: float = 10.0,
    ) -> None:
        """Equip the best tool for mining a block.

        Selects and equips the most efficient tool from the bot's
        inventory for the target block.  If ``require_harvest`` is
        ``True``, only tools that can actually harvest the block's
        drops will be considered.

        Args:
            block: The :class:`~minethon.models.block.Block` to equip
                tools for.
            require_harvest: If ``True``, only equip tools that can
                harvest the block.  Defaults to ``False``.
            timeout: Maximum seconds to wait for the equip operation.

        Raises:
            BridgeError: If the equip operation fails or times out.

        Ref: mineflayer-tool/lib/Tool.js — ``equipForBlock``
        """
        position = (
            int(block.position.x),
            int(block.position.y),
            int(block.position.z),
        )
        async with self._equip_lock:
            self._bridge.start_equip_for_block(
                position,
                require_harvest=require_harvest,
            )
            event = await self._relay.wait_for(
                ToolEquipDoneEvent,
                timeout=timeout,
            )
            if event.error is not None:
                raise BridgeError(f"equip_for_block failed: {event.error}")
