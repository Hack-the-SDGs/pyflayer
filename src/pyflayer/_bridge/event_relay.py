"""Bridge JS EventEmitter callbacks into asyncio dispatch."""

import asyncio
import time
from collections import defaultdict
from collections.abc import Coroutine
from typing import Any, Callable

from pyflayer.models.events import ChatEvent, SpawnEvent


class EventRelay:
    """Receives JS events on the JSPyBridge callback thread and
    dispatches them to asyncio handlers via ``call_soon_threadsafe``.
    """

    def __init__(self) -> None:
        self._loop: asyncio.AbstractEventLoop | None = None
        self._handlers: dict[type, list[Callable[..., Coroutine[Any, Any, None]]]] = (
            defaultdict(list)
        )
        self._waiters: dict[type, list[asyncio.Future[Any]]] = defaultdict(list)
        # Strong refs to prevent GC (JSPyBridge uses WeakValueDictionary)
        self._js_handler_refs: list[Any] = []

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Bind to the running asyncio event loop."""
        self._loop = loop

    def register_js_events(self, js_bot: Any, on_fn: Any) -> None:
        """Register ``@On`` handlers for core mineflayer events.

        Args:
            js_bot: The JS bot proxy from JSBotController.
            on_fn: The ``On`` decorator from JSPyBridge.
        """

        @on_fn(js_bot, "spawn")
        def _on_spawn(*_args: Any) -> None:
            self._post(SpawnEvent, SpawnEvent())

        @on_fn(js_bot, "chat")
        def _on_chat(*args: Any) -> None:
            # When node_emitter_patches is off (Node 16+): args = (username, message, ...)
            # When on (legacy Node): args = (emitter, username, message, ...)
            # We accept both by using *args and extracting the first two strings.
            if len(args) < 2:
                return
            username = str(args[0])
            message = str(args[1])
            event = ChatEvent(
                sender=username,
                message=message,
                timestamp=time.time(),
            )
            self._post(ChatEvent, event)

        # CRITICAL: prevent garbage collection of callback references
        self._js_handler_refs.extend([_on_spawn, _on_chat])

    # -- Handler management (called from ObserveAPI) --

    def add_handler(
        self, event_type: type, handler: Callable[..., Coroutine[Any, Any, None]]
    ) -> None:
        """Register an async handler for an event type."""
        self._handlers[event_type].append(handler)

    def remove_handler(
        self, event_type: type, handler: Callable[..., Coroutine[Any, Any, None]]
    ) -> None:
        """Unregister an async handler."""
        self._handlers[event_type].remove(handler)

    async def wait_for(self, event_type: type, *, timeout: float = 30.0) -> Any:
        """Wait for a single event of the given type."""
        assert self._loop is not None
        fut: asyncio.Future[Any] = self._loop.create_future()
        self._waiters[event_type].append(fut)
        try:
            return await asyncio.wait_for(fut, timeout=timeout)
        except asyncio.TimeoutError:
            waiters = self._waiters.get(event_type, [])
            if fut in waiters:
                waiters.remove(fut)
            raise

    # -- Internal dispatch --

    def _post(self, event_type: type, event: object) -> None:
        """Thread-safe post from JSPyBridge callback thread."""
        if self._loop is not None and self._loop.is_running():
            try:
                self._loop.call_soon_threadsafe(self._dispatch, event_type, event)
            except RuntimeError:
                pass  # Event loop closed during shutdown

    def _dispatch(self, event_type: type, event: object) -> None:
        """Runs on the asyncio event loop thread."""
        # Resolve waiters
        for fut in self._waiters.pop(event_type, []):
            if not fut.done():
                fut.set_result(event)
        # Call registered handlers
        if self._loop is not None:
            for handler in self._handlers.get(event_type, []):
                self._loop.create_task(handler(event))
