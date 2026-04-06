"""Raw access to the underlying mineflayer JS bot object.

.. warning::

    This module exposes the raw JSPyBridge proxy to the mineflayer bot.
    It is **not** type-safe, **not** version-stable, and intended only
    for advanced use cases that the typed API does not yet cover.
    Refer to the `mineflayer JS documentation
    <https://github.com/PrismarineJS/mineflayer/blob/master/docs/api.md>`_
    for available properties and methods.
"""

from typing import Any


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

    def __init__(self, js_bot: Any) -> None:
        self._js_bot = js_bot

    @property
    def js_bot(self) -> Any:
        """The raw JS mineflayer bot proxy.

        Warning:
            This is a JSPyBridge proxy. No type safety or stability
            is guaranteed. Use at your own risk.
        """
        return self._js_bot
