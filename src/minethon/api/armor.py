"""Armor management API.

Ref: mineflayer-armor-manager/dist/index.js — ``initializeBot``
"""

import asyncio
from typing import TYPE_CHECKING

from minethon._bridge._events import ArmorEquipDoneEvent
from minethon.models.errors import BridgeError

if TYPE_CHECKING:
    from minethon._bridge.event_relay import EventRelay
    from minethon._bridge.plugins.armor_manager import ArmorManagerBridge


class ArmorAPI:
    """Automatic armor equipping through ``mineflayer-armor-manager``.

    Example::

        await bot.armor.equip_best()

    Ref: mineflayer-armor-manager/dist/index.js — ``bot.armorManager``
    """

    def __init__(
        self,
        bridge: ArmorManagerBridge,
        relay: EventRelay,
    ) -> None:
        self._bridge = bridge
        self._relay = relay
        self._equip_lock = asyncio.Lock()

    async def equip_best(self) -> None:
        """Equip the best available armor pieces from inventory.

        Scans the bot's inventory and equips the highest-tier armor
        in each slot (head, chest, legs, feet).

        Raises:
            BridgeError: If the equip operation fails or times out.

        Ref: mineflayer-armor-manager/dist/index.js — ``bot.armorManager.equipAll()``
        """
        async with self._equip_lock:
            self._bridge.start_equip_all()
            try:
                event = await self._relay.wait_for(ArmorEquipDoneEvent, timeout=30.0)
            except TimeoutError as exc:
                raise BridgeError("armor equip timed out") from exc
            if event.error is not None:
                raise BridgeError(f"armor equip failed: {event.error}")
