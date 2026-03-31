"""Bot -- the public entry point for pyflayer."""

import asyncio
from collections.abc import Coroutine
from typing import Any, Callable, TypeVar, overload

from pyflayer._bridge.event_relay import EventRelay
from pyflayer._bridge.js_bot import JSBotController
from pyflayer._bridge.runtime import BridgeRuntime
from pyflayer.config import BotConfig
from pyflayer.models.errors import NotSpawnedError
from pyflayer.models.events import SpawnEvent
from pyflayer.models.vec3 import Vec3

E = TypeVar("E")

_Handler = Callable[[E], Coroutine[Any, Any, None]]


class ObserveAPI:
    """Event subscription API (minimal M0 version).

    Supports decorator-style and method-style registration, plus
    one-shot ``wait_for``.
    """

    def __init__(self, relay: EventRelay) -> None:
        self._relay = relay

    @overload
    def on(self, event_type: type[E]) -> Callable[[_Handler[E]], _Handler[E]]: ...

    @overload
    def on(self, event_type: type[E], handler: _Handler[E]) -> None: ...

    def on(
        self,
        event_type: type[E],
        handler: _Handler[E] | None = None,
    ) -> Callable[[_Handler[E]], _Handler[E]] | None:
        """Subscribe to an event type.

        Can be used as a decorator::

            @bot.observe.on(ChatEvent)
            async def on_chat(event: ChatEvent):
                ...

        Or called directly::

            bot.observe.on(ChatEvent, handle_chat)
        """
        if handler is not None:
            self._relay.add_handler(event_type, handler)  # type: ignore[arg-type]
            return None

        def decorator(fn: _Handler[E]) -> _Handler[E]:
            self._relay.add_handler(event_type, fn)  # type: ignore[arg-type]
            return fn

        return decorator

    def off(self, event_type: type[E], handler: _Handler[E]) -> None:
        """Unsubscribe a handler."""
        self._relay.remove_handler(event_type, handler)  # type: ignore[arg-type]

    async def wait_for(self, event_type: type[E], *, timeout: float = 30.0) -> E:
        """Wait for a single event occurrence."""
        return await self._relay.wait_for(event_type, timeout=timeout)  # type: ignore[return-value]


class Bot:
    """pyflayer entry point.

    Example::

        async def main():
            bot = Bot(host="localhost", username="Steve")
            await bot.connect()
            await bot.wait_until_spawned()
            await bot.chat("Hello!")
            await bot.disconnect()
    """

    def __init__(
        self,
        host: str,
        port: int = 25565,
        username: str = "pyflayer",
        version: str | None = None,
        auth: str | None = None,
        hide_errors: bool = False,
    ) -> None:
        self._config = BotConfig(
            host=host,
            port=port,
            username=username,
            version=version,
            auth=auth,
            hide_errors=hide_errors,
        )
        self._relay = EventRelay()
        self._observe = ObserveAPI(self._relay)
        self._runtime: BridgeRuntime | None = None
        self._controller: JSBotController | None = None
        self._connected = False
        self._spawned = False

    # -- Lifecycle --

    async def connect(self) -> None:
        """Connect to the Minecraft server.

        Initializes the JSPyBridge runtime and calls
        ``mineflayer.createBot()``.
        """
        if self._connected:
            return
        loop = asyncio.get_running_loop()
        self._relay.set_loop(loop)

        self._runtime = BridgeRuntime()
        self._runtime.start()

        self._controller = JSBotController(self._runtime, self._config)
        # JSPyBridge calls must happen on the thread that initialized the
        # runtime.  createBot() is fast (it only sends an IPC message) so
        # running it synchronously on the event-loop thread is acceptable.
        self._controller.create_bot()

        self._relay.register_js_events(
            self._controller.js_bot,
            self._runtime.js_module.On,
        )
        self._connected = True

    async def disconnect(self) -> None:
        """Disconnect from the server and clean up."""
        if not self._connected:
            return
        if self._controller is not None:
            self._controller.quit()
        if self._runtime is not None:
            self._runtime.shutdown()
        self._connected = False
        self._spawned = False

    async def wait_until_spawned(self, timeout: float = 30.0) -> None:
        """Block until the bot has spawned in the world."""
        if self._spawned:
            return
        await self._observe.wait_for(SpawnEvent, timeout=timeout)
        self._spawned = True

    # -- State properties --

    @property
    def is_connected(self) -> bool:
        """Whether the bot is currently connected."""
        return self._connected

    @property
    def position(self) -> Vec3:
        """Current bot position."""
        if self._controller is None:
            raise NotSpawnedError("Bot is not connected.")
        data = self._controller.get_position()
        return Vec3(x=data["x"], y=data["y"], z=data["z"])

    @property
    def username(self) -> str:
        """Bot username."""
        return self._config.username

    # -- Chat --

    async def chat(self, message: str) -> None:
        """Send a chat message."""
        if self._controller is None:
            raise NotSpawnedError("Bot is not connected.")
        self._controller.chat(message)

    # -- Sub-APIs --

    @property
    def observe(self) -> ObserveAPI:
        """Event subscription API."""
        return self._observe
