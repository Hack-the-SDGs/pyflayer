"""Raw access to the underlying mineflayer JS bot object.

.. warning::

    This module exposes the raw JSPyBridge proxy to the mineflayer bot.
    It is **not** type-safe, **not** version-stable, and intended only
    for advanced use cases that the typed API does not yet cover.
    Refer to the `mineflayer JS documentation
    <https://github.com/PrismarineJS/mineflayer/blob/master/docs/api.md>`_
    for available properties and methods.
"""

from collections.abc import Awaitable, Callable
from typing import Any

_RawHandler = Callable[[dict[str, Any]], Awaitable[None]]


class RawBotHandle:
    """Thin wrapper providing raw access to the JS mineflayer bot.

    Obtain via ``bot.raw``::

        handle = bot.raw
        # Direct JS proxy access
        handle.js_bot.chat("hello from raw")

    Warning:
        - The ``js_bot`` property returns a JSPyBridge proxy object.
        - No type safety or API stability is guaranteed.
        - Calling JS methods incorrectly may crash the Node.js process.
        - All JSPyBridge calls **must** run on the event-loop thread
          (the same thread that called ``Bot.connect()``).
    """

    def __init__(
        self,
        js_bot: Any,
        *,
        raw_subscribe: Callable[[str, _RawHandler], None] | None = None,
        raw_unsubscribe: Callable[[str, _RawHandler], None] | None = None,
        plugin_loader: Callable[[str], Any] | None = None,
    ) -> None:
        self._js_bot = js_bot
        self._raw_subscribe = raw_subscribe
        self._raw_unsubscribe = raw_unsubscribe
        self._plugin_loader = plugin_loader

    @property
    def js_bot(self) -> Any:
        """The raw JS mineflayer bot proxy.

        Warning:
            This is a JSPyBridge proxy. No type safety or stability
            is guaranteed. Use at your own risk.
        """
        return self._js_bot

    def on(self, event_name: str, handler: _RawHandler) -> None:
        """Subscribe to a raw JS event by name."""
        if self._raw_subscribe is None:
            raise RuntimeError("Raw event binding is not available on this handle.")
        self._raw_subscribe(event_name, handler)

    def off(self, event_name: str, handler: _RawHandler) -> None:
        """Unsubscribe a raw JS event handler."""
        if self._raw_unsubscribe is None:
            raise RuntimeError("Raw event binding is not available on this handle.")
        self._raw_unsubscribe(event_name, handler)

    def plugin(self, name: str) -> Any:
        """Load and return a raw JS plugin module."""
        if self._plugin_loader is None:
            raise RuntimeError("Raw plugin loading is not available on this handle.")
        return self._plugin_loader(name)
