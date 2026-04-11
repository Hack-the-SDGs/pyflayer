"""GUI plugin bridge (Type A — direct inject function).

Wraps ``mineflayer-gui`` which provides a chainable ``Query`` builder
for programmatic inventory / hotbar interactions.

Ref: mineflayer-gui/src/query.js — Query builder pattern
"""

from __future__ import annotations

import pathlib
from typing import Any

from minethon._bridge._util import extract_js_stack
from minethon._bridge.plugins._base import PluginBridge
from minethon.models.errors import BridgeError

_JS_HELPERS_PATH = pathlib.Path(__file__).resolve().parent.parent / "js" / "helpers.js"


class GuiBridge(PluginBridge):
    """Bridge for ``mineflayer-gui``.

    **Type A:** The module exports the inject function directly as
    ``module.exports``, loaded via ``bot.loadPlugin(mod)``.

    Ref: mineflayer-gui/src/index.js
    """

    NPM_NAME = "mineflayer-gui"

    def __init__(
        self,
        runtime: Any,
        js_bot: Any,
        relay: Any,
    ) -> None:
        super().__init__(runtime, js_bot, relay)
        self._helpers: Any = None

    def _ensure_helpers(self) -> Any:
        """Lazy-load helpers.js and cache the reference."""
        if self._helpers is None:
            self._helpers = self._runtime.require(str(_JS_HELPERS_PATH.as_posix()))
        return self._helpers

    def _do_load(self) -> None:
        """Load the GUI plugin into the JS bot.

        The module exports the inject function directly as
        ``module.exports``, so ``mod`` itself is passed to
        ``bot.loadPlugin()``.

        Ref: mineflayer-gui/src/index.js — ``module.exports = inject``
        """
        try:
            mod = self._runtime.require(self.NPM_NAME)
            self._js_bot.loadPlugin(mod)
            self._ensure_helpers()
        except Exception as exc:
            self._loaded = False
            raise BridgeError(
                f"load gui failed: {exc}",
                js_stack=extract_js_stack(exc),
            ) from exc

    def start_click_by_name(self, name: str, *, window: bool = False) -> None:
        """Start a click-by-name query without blocking.

        Comparators are built in JS to avoid crossing the bridge with
        Python callables.  Completion is signalled via the
        ``_minethon:guiQueryDone`` event.

        Args:
            name: Minecraft item name (e.g. ``"diamond_sword"``).
            window: If ``True``, use Window+Click; otherwise Hotbar+Equip.

        Ref: mineflayer-gui/src/query.js — Query.Hotbar, Query.Window,
             Query.Equip, Query.Click
        """
        if not self._loaded:
            raise BridgeError("start_click_by_name failed: gui has not been loaded")
        try:
            helpers = self._ensure_helpers()
            helpers.guiClickByName(self._js_bot, name, window)
        except Exception as exc:
            raise BridgeError(
                f"start_click_by_name failed: {exc}",
                js_stack=extract_js_stack(exc),
            ) from exc

    def start_drop_by_name(self, name: str, count: int) -> None:
        """Start a drop-by-name query without blocking.

        Comparators are built in JS to avoid crossing the bridge with
        Python callables.  Completion is signalled via the
        ``_minethon:guiDropDone`` event.

        Args:
            name: Minecraft item name (e.g. ``"cobblestone"``).
            count: Number of items to drop.

        Ref: mineflayer-gui/src/query.js — Query.Window, Query.Drop
        """
        if not self._loaded:
            raise BridgeError("start_drop_by_name failed: gui has not been loaded")
        try:
            helpers = self._ensure_helpers()
            helpers.guiDropByName(self._js_bot, name, count)
        except Exception as exc:
            raise BridgeError(
                f"start_drop_by_name failed: {exc}",
                js_stack=extract_js_stack(exc),
            ) from exc

    def create_query(self) -> Any:
        """Create a raw JS ``Query`` builder (escape hatch).

        Returns:
            A JS ``Query`` proxy from mineflayer-gui.

        Warning:
            This is a raw JSPyBridge proxy with no type safety or
            API stability guarantees.

        Ref: mineflayer-gui/src/query.js — ``new Query()``
        """
        if not self._loaded:
            raise BridgeError("create_query failed: gui has not been loaded")
        try:
            return self._js_bot.gui.Query()
        except Exception as exc:
            raise BridgeError(
                f"create_query failed: {exc}",
                js_stack=extract_js_stack(exc),
            ) from exc
