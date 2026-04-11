"""Armor Manager plugin bridge.

Ref: mineflayer-armor-manager/dist/index.js — ``initializeBot``
"""

from __future__ import annotations

import pathlib
from typing import Any

from minethon._bridge._util import extract_js_stack
from minethon._bridge.plugins._base import PluginBridge
from minethon.models.errors import BridgeError

_JS_HELPERS_PATH = pathlib.Path(__file__).resolve().parent.parent / "js" / "helpers.js"


class ArmorManagerBridge(PluginBridge):
    """Bridge for ``mineflayer-armor-manager``.

    Manages loading the armor-manager plugin and triggering
    ``equipAll()`` through the helpers.js async wrapper.

    Ref: mineflayer-armor-manager/dist/index.js — ``initializeBot``
    """

    NPM_NAME = "mineflayer-armor-manager"

    def __init__(
        self,
        runtime: Any,
        js_bot: Any,
        relay: Any,
    ) -> None:
        super().__init__(runtime, js_bot, relay)
        self._helpers: Any = None

    def _do_load(self) -> None:
        """Load the armor-manager plugin into the JS bot.

        The module exports ``initializeBot`` directly as
        ``module.exports``, so ``mod`` itself is the inject function.

        Ref: mineflayer-armor-manager/dist/index.js:13-35 — ``module.exports = initializeBot``
        """
        try:
            mod = self._runtime.require(self.NPM_NAME)
            self._js_bot.loadPlugin(mod)
            self._helpers = self._runtime.require(str(_JS_HELPERS_PATH.as_posix()))
        except Exception as exc:
            self._loaded = False
            raise BridgeError(
                f"load armor-manager failed: {exc}",
                js_stack=extract_js_stack(exc),
            ) from exc

    def start_equip_all(self) -> None:
        """Start equipping best armor without blocking.

        Completion is signalled via ``_minethon:armorEquipDone`` event.

        Ref: mineflayer-armor-manager/dist/index.js — ``bot.armorManager.equipAll()``
        """
        if not self._loaded:
            raise BridgeError(
                "start_equip_all failed: armor-manager has not been loaded"
            )
        try:
            self._helpers.startArmorEquipAll(self._js_bot)
        except Exception as exc:
            raise BridgeError(
                f"start_equip_all failed: {exc}",
                js_stack=extract_js_stack(exc),
            ) from exc
