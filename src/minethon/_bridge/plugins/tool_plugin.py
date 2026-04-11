"""Tool plugin bridge.

Ref: mineflayer-tool — ``lib/index.js``, ``lib/Tool.js``
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from minethon._bridge._util import extract_js_stack
from minethon._bridge.plugins._base import PluginBridge
from minethon.models.errors import BridgeError

if TYPE_CHECKING:
    from minethon._bridge.js_bot import JSBotController


class ToolBridge(PluginBridge):
    """Bridge for ``mineflayer-tool``.

    Manages loading the tool plugin and equipping the best tool
    for mining a given block.

    The tool plugin internally ``setTimeout``-loads pathfinder, so
    ``DEPENDS_ON`` is intentionally empty.

    Ref: mineflayer-tool/lib/index.js — ``exports.plugin``
    """

    NPM_NAME = "mineflayer-tool"

    def __init__(
        self,
        runtime: Any,
        js_bot: Any,
        relay: Any,
        controller: JSBotController,
    ) -> None:
        super().__init__(runtime, js_bot, relay)
        self._controller = controller

    def _do_load(self) -> None:
        """Load the tool plugin into the JS bot.

        Ref: mineflayer-tool/lib/index.js — ``exports.plugin = plugin``
        """
        try:
            mod = self._runtime.require(self.NPM_NAME)
            self._js_bot.loadPlugin(mod.plugin)
        except Exception as exc:
            self._loaded = False
            raise BridgeError(
                f"load tool failed: {exc}",
                js_stack=extract_js_stack(exc),
            ) from exc

    def start_equip_for_block(
        self,
        block_position: tuple[int, int, int],
        *,
        require_harvest: bool = False,
    ) -> None:
        """Start equipping the best tool for a block without blocking.

        Resolves the JS block from the position, then calls the
        ``startToolEquipForBlock`` helper.  Completion is signalled via
        the ``_minethon:toolEquipDone`` event.

        Args:
            block_position: ``(x, y, z)`` coordinates of the target block.
            require_harvest: If ``True``, only equip tools that can
                actually harvest the block's drops.

        Raises:
            BridgeError: If the plugin is not loaded, the block cannot
                be found, or the JS call fails.

        Ref: mineflayer-tool/lib/Tool.js — ``equipForBlock``
        """
        if not self._loaded:
            raise BridgeError(
                "start_equip_for_block failed: tool plugin has not been loaded"
            )
        x, y, z = block_position
        js_block = self._controller.block_at(x, y, z)
        if js_block is None:
            raise BridgeError(
                f"start_equip_for_block failed: no block at ({x}, {y}, {z})"
            )
        try:
            options = {"requireHarvest": require_harvest}
            self._controller._helpers.startToolEquipForBlock(
                self._js_bot, js_block, options,
            )
        except Exception as exc:
            raise BridgeError(
                f"start_equip_for_block failed: {exc}",
                js_stack=extract_js_stack(exc),
            ) from exc
