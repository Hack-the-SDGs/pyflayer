"""Web inventory viewer service (Type B plugin).

This service wraps ``mineflayer-web-inventory``, which exposes the bot's
inventory via a local web UI.  It is a **Type B** plugin -- initialised
by calling the module directly, not through ``bot.loadPlugin()``.

Ref: mineflayer-web-inventory/index.js
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from minethon._bridge._events import WebInvStartDoneEvent, WebInvStopDoneEvent
from minethon.models.errors import BridgeError

if TYPE_CHECKING:
    from minethon._bridge.event_relay import EventRelay
    from minethon._bridge.runtime import BridgeRuntime

_log = logging.getLogger(__name__)

_DEFAULT_PORT: int = 3008
_OPERATION_TIMEOUT: float = 10.0


class WebInventoryService:
    """Web inventory viewer service.

    Type B plugin -- port is fixed at initialisation time.
    Ref: mineflayer-web-inventory/index.js
    """

    def __init__(
        self,
        runtime: BridgeRuntime,
        js_bot: Any,
        relay: EventRelay,
    ) -> None:
        self._runtime = runtime
        self._js_bot = js_bot
        self._relay = relay
        self._helpers: Any | None = None  # loaded lazily
        self._initialized = False
        self._running = False
        self._port: int | None = None

    # -- Lifecycle --

    def _ensure_helpers(self) -> Any:
        """Lazy-load helpers.js and cache the reference."""
        if self._helpers is None:
            import pathlib

            helpers_path = pathlib.Path(__file__).parent.parent / "js" / "helpers.js"
            self._helpers = self._runtime.require(str(helpers_path))
        return self._helpers

    async def initialize(
        self,
        port: int = _DEFAULT_PORT,
        *,
        start_on_load: bool = True,
    ) -> None:
        """Require the npm module and attach it to the bot.

        Args:
            port: TCP port for the web inventory UI.  Fixed at
                initialisation; ``start()``/``stop()`` do not accept a
                port parameter.
            start_on_load: When ``True`` (default), the HTTP server is
                started automatically after initialisation.  Set to
                ``False`` to defer starting until :meth:`start` is
                called explicitly.

        Raises:
            BridgeError: If already initialised.

        Ref: mineflayer-web-inventory/index.js:5 --
             ``module.exports = function (bot, options = {})``
        """
        if self._initialized:
            raise BridgeError("WebInventoryService is already initialised.")

        mod = self._runtime.require("mineflayer-web-inventory")
        # Ref: index.js:11 -- port is fixed to options.port at init
        mod(self._js_bot, {"port": port, "startOnLoad": start_on_load})
        self._initialized = True
        self._port = port

        if start_on_load:
            self._running = True
            _log.info("Web inventory started on port %d (startOnLoad)", port)
        else:
            _log.info("Web inventory initialised on port %d (not started)", port)

    def _ensure_initialized(self) -> None:
        if not self._initialized:
            raise BridgeError(
                "WebInventoryService is not initialised. "
                "Call initialize() first."
            )

    async def start(self) -> None:
        """Start the web inventory HTTP server.

        Non-blocking -- delegates to ``helpers.js`` and awaits the
        ``_minethon:webInvStartDone`` event.

        Raises:
            BridgeError: If not initialised, already running, or the
                JS ``start()`` Promise rejects.

        Ref: mineflayer-web-inventory/index.js --
             ``bot.webInventory.start()``
        """
        self._ensure_initialized()
        if self._running:
            raise BridgeError("Web inventory is already running.")

        helpers = self._ensure_helpers()
        helpers.startWebInventory(self._js_bot)

        event: WebInvStartDoneEvent = await self._relay.wait_for(
            WebInvStartDoneEvent, timeout=_OPERATION_TIMEOUT
        )
        if event.error is not None:
            raise BridgeError(f"web-inventory start failed: {event.error}")

        self._running = True
        _log.info("Web inventory started on port %s", self._port)

    async def stop(self) -> None:
        """Stop the web inventory HTTP server.

        Non-blocking -- delegates to ``helpers.js`` and awaits the
        ``_minethon:webInvStopDone`` event.

        Raises:
            BridgeError: If not initialised, not running, or the
                JS ``stop()`` Promise rejects.

        Ref: mineflayer-web-inventory/index.js --
             ``bot.webInventory.stop()``
        """
        self._ensure_initialized()
        if not self._running:
            raise BridgeError("Web inventory is not running.")

        helpers = self._ensure_helpers()
        helpers.stopWebInventory(self._js_bot)

        event: WebInvStopDoneEvent = await self._relay.wait_for(
            WebInvStopDoneEvent, timeout=_OPERATION_TIMEOUT
        )
        if event.error is not None:
            raise BridgeError(f"web-inventory stop failed: {event.error}")

        self._running = False
        _log.info("Web inventory stopped")

    # -- Properties --

    @property
    def is_running(self) -> bool:
        """Whether the web inventory HTTP server is currently running.

        Backed by Python-side state tracking -- no live bridge I/O.
        """
        return self._running

    @property
    def is_initialized(self) -> bool:
        """Whether the service has been initialised."""
        return self._initialized

    @property
    def port(self) -> int | None:
        """The TCP port the service was initialised with, or ``None``."""
        return self._port
