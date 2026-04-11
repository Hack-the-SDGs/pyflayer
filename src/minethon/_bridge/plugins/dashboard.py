"""Dashboard plugin bridge (Type D — Higher-Order Function).

.. warning:: **Experimental.** ``@ssmidge/mineflayer-dashboard`` was
   developed against mineflayer ^2.28.1 (current: 4.37.0) and uses
   blessed terminal UI which may conflict with Python's stdout/stderr.

Ref: @ssmidge/mineflayer-dashboard/index.js
"""

from __future__ import annotations

from typing import Any

from minethon._bridge._util import extract_js_stack
from minethon._bridge.plugins._base import PluginBridge
from minethon.models.errors import BridgeError


class DashboardBridge(PluginBridge):
    """Bridge for ``@ssmidge/mineflayer-dashboard``.

    **Type D (HOF):** The module exports
    ``function(options) { return function(bot) {} }``.
    Loading is ``bot.loadPlugin(mod(options))``.

    .. warning:: **Experimental.** This plugin targets mineflayer
       ^2.28.1 and uses blessed terminal UI.

    Ref: @ssmidge/mineflayer-dashboard/index.js
    """

    NPM_NAME = "@ssmidge/mineflayer-dashboard"

    def __init__(
        self,
        runtime: Any,
        js_bot: Any,
        relay: Any,
    ) -> None:
        super().__init__(runtime, js_bot, relay)
        self._chat_pattern: str | None = None

    def configure(self, *, chat_pattern: str | None = None) -> None:
        """Set options before loading.

        Must be called **before** :meth:`load`.  Calling after load
        has no effect.

        Args:
            chat_pattern: A JS ``RegExp`` pattern string used to
                filter chat messages shown in the dashboard.
        """
        if self._loaded:
            return
        self._chat_pattern = chat_pattern

    def _do_load(self) -> None:
        """Load the dashboard plugin via HOF pattern.

        Ref: @ssmidge/mineflayer-dashboard/index.js:18-168
        """
        try:
            mod = self._runtime.require(self.NPM_NAME)
            options: dict[str, Any] = {}
            if self._chat_pattern is not None:
                options["chatPattern"] = self._chat_pattern
            plugin_fn = mod(options)  # HOF: mod(options) -> (bot) => void
            self._js_bot.loadPlugin(plugin_fn)
        except Exception as exc:
            self._loaded = False
            raise BridgeError(
                f"load dashboard failed: {exc}",
                js_stack=extract_js_stack(exc),
            ) from exc

    def teardown(self) -> None:
        """Best-effort cleanup of blessed terminal resources.

        The upstream dashboard creates a module-scope blessed ``screen``
        (``src/ui.js:3``) and input listeners.  There is no upstream
        ``destroy()`` API, so we try to call ``screen.destroy()``
        directly and null out ``bot.dashboard`` to prevent further use.

        Ref: @ssmidge/mineflayer-dashboard/src/ui.js:3 — module-scope screen
        Ref: @ssmidge/mineflayer-dashboard/index.js:125 — bot.once('end')
        """
        if not self._loaded:
            return
        try:
            ui_mod = self._runtime.require("@ssmidge/mineflayer-dashboard/src/ui")
            ui_mod.screen.destroy()
        except Exception:
            pass  # Best-effort: upstream may not expose screen
        try:
            self._js_bot.dashboard._ended = True
        except Exception:
            pass
        self._loaded = False

    def log(self, *messages: str) -> None:
        """Write messages to the dashboard log box.

        All arguments are forwarded to ``bot.dashboard.log()``.

        Raises:
            BridgeError: If the plugin is not loaded.

        Ref: @ssmidge/mineflayer-dashboard/index.js — ``bot.dashboard.log()``
        """
        if not self._loaded:
            raise BridgeError("log failed: dashboard has not been loaded")
        try:
            self._js_bot.dashboard.log(*messages)
        except Exception as exc:
            raise BridgeError(
                f"dashboard log failed: {exc}",
                js_stack=extract_js_stack(exc),
            ) from exc
