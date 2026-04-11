"""GUI item management via mineflayer-gui plugin.

Ref: mineflayer-gui/src/query.js — Query builder pattern
"""

import asyncio
from typing import TYPE_CHECKING, Any

from minethon._bridge._events import GuiDropDoneEvent, GuiQueryDoneEvent
from minethon.models.errors import BridgeError

if TYPE_CHECKING:
    from minethon._bridge.event_relay import EventRelay
    from minethon._bridge.plugins.gui import GuiBridge


class GuiAPI:
    """High-level GUI item operations powered by mineflayer-gui.

    Provides convenience methods for common item interactions
    (click, drop) without exposing the JS Query builder directly.
    Advanced users can access the raw Query builder via
    :meth:`raw_query`.

    Example::

        await bot.gui.click_item("diamond_sword")
        await bot.gui.drop_item("cobblestone", count=32)

    Ref: mineflayer-gui/src/query.js — Query builder pattern
    """

    def __init__(self, bridge: GuiBridge, relay: EventRelay) -> None:
        self._bridge = bridge
        self._relay = relay
        self._click_lock = asyncio.Lock()
        self._drop_lock = asyncio.Lock()

    async def click_item(self, name: str, *, window: bool = False) -> bool:
        """Click first item matching *name* in hotbar or window.

        When *window* is ``False`` (default), searches the hotbar and
        equips the matching item.  When ``True``, opens the inventory
        window and clicks the item.

        Args:
            name: Minecraft item name (e.g. ``"diamond_sword"``).
            window: If ``True``, use Window+Click instead of Hotbar+Equip.

        Returns:
            ``True`` if the query found and acted on the item.

        Raises:
            BridgeError: If the underlying JS call fails.

        Ref: mineflayer-gui/src/query.js — Query.Hotbar, Query.Window,
             Query.Equip, Query.Click
        """
        async with self._click_lock:
            self._bridge.start_click_by_name(name, window=window)
            event: GuiQueryDoneEvent = await self._relay.wait_for(
                GuiQueryDoneEvent, timeout=30.0
            )
            if event.error is not None:
                raise BridgeError(f"click_item failed: {event.error}")
            return event.result

    async def drop_item(self, name: str, count: int = 1) -> bool:
        """Drop item matching *name* from window.

        Opens the inventory window, finds the item, and drops the
        specified number of items.

        Args:
            name: Minecraft item name (e.g. ``"cobblestone"``).
            count: Number of items to drop.

        Returns:
            ``True`` if the query found and dropped the item.

        Raises:
            BridgeError: If the underlying JS call fails.

        Ref: mineflayer-gui/src/query.js — Query.Window, Query.Drop
        """
        async with self._drop_lock:
            self._bridge.start_drop_by_name(name, count)
            event: GuiDropDoneEvent = await self._relay.wait_for(
                GuiDropDoneEvent, timeout=30.0
            )
            if event.error is not None:
                raise BridgeError(f"drop_item failed: {event.error}")
            return event.result

    def raw_query(self) -> Any:
        """Get raw JS Query builder for advanced operations.

        Returns the JS ``Query`` proxy from mineflayer-gui, giving
        full access to the chainable builder API.

        Warning:
            This is an **escape hatch** for power users.  The returned
            object is a raw JSPyBridge proxy with no type safety or
            API stability guarantees.  Refer to the mineflayer-gui
            documentation for the Query builder API.

        Returns:
            A JS ``Query`` proxy.

        Raises:
            BridgeError: If the JS call fails.

        Ref: mineflayer-gui/src/query.js — new Query()
        """
        return self._bridge.create_query()
