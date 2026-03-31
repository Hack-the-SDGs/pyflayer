"""Event subscription API."""

from collections.abc import Awaitable, Coroutine
from typing import Any, Callable, TypeVar, overload

from pyflayer._bridge.event_relay import EventRelay
from pyflayer.models.errors import PyflayerConnectionError

E = TypeVar("E")

_Handler = Callable[[E], Coroutine[Any, Any, None]]


class ObserveAPI:
    """Event subscription API.

    Supports decorator-style and method-style registration, plus
    one-shot ``wait_for`` and raw JS event access.
    """

    def __init__(self, relay: EventRelay) -> None:
        self._relay = relay
        self._bound_raw_events: set[str] = set()
        self._pending_raw_events: set[str] = set()
        self._js_bot: Any = None
        self._on_fn: Any = None

    def _bind_js(self, js_bot: Any, on_fn: Any) -> None:
        """Store JS references and bind any queued raw events."""
        self._js_bot = js_bot
        self._on_fn = on_fn
        # Bind raw events that were registered before connect()
        for event_name in self._pending_raw_events:
            self._relay.bind_raw_js_event(js_bot, on_fn, event_name)
            self._bound_raw_events.add(event_name)
        self._pending_raw_events.clear()

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
        """Wait for a single event occurrence.

        Raises:
            PyflayerConnectionError: If called before ``Bot.connect()``.
            asyncio.TimeoutError: If no event arrives within *timeout* seconds.
        """
        try:
            return await self._relay.wait_for(event_type, timeout=timeout)  # type: ignore[return-value]
        except RuntimeError as exc:
            raise PyflayerConnectionError(
                "Bot is not connected; call Bot.connect() before wait_for()."
            ) from exc

    @overload
    def on_raw(
        self, event_name: str
    ) -> Callable[
        [Callable[[dict], Awaitable[None]]], Callable[[dict], Awaitable[None]]
    ]: ...

    @overload
    def on_raw(
        self, event_name: str, handler: Callable[[dict], Awaitable[None]]
    ) -> None: ...

    def on_raw(
        self,
        event_name: str,
        handler: Callable[[dict], Awaitable[None]] | None = None,
    ) -> (
        Callable[
            [Callable[[dict], Awaitable[None]]], Callable[[dict], Awaitable[None]]
        ]
        | None
    ):
        """Subscribe to a raw JS event by name.

        This is an escape hatch for events not covered by the typed API.
        The handler receives a ``dict`` with an ``"args"`` key containing
        the raw JS callback arguments.

        Can be used as a decorator::

            @bot.observe.on_raw("entityMoved")
            async def on_entity_moved(data: dict):
                ...

        Or called directly::

            bot.observe.on_raw("entityMoved", handler)

        Warning:
            Raw event data is not typed or validated.
        """
        def _register(fn: Callable[[dict], Awaitable[None]]) -> None:
            if event_name not in self._bound_raw_events:
                if self._js_bot is not None and self._on_fn is not None:
                    self._relay.bind_raw_js_event(
                        self._js_bot, self._on_fn, event_name
                    )
                    self._bound_raw_events.add(event_name)
                else:
                    # Queue for binding once connect() provides JS refs
                    self._pending_raw_events.add(event_name)
            self._relay.add_raw_handler(event_name, fn)  # type: ignore[arg-type]

        if handler is not None:
            _register(handler)
            return None

        def decorator(
            fn: Callable[[dict], Awaitable[None]],
        ) -> Callable[[dict], Awaitable[None]]:
            _register(fn)
            return fn

        return decorator

    def off_raw(
        self, event_name: str, handler: Callable[[dict], Awaitable[None]]
    ) -> None:
        """Unsubscribe a raw event handler."""
        self._relay.remove_raw_handler(event_name, handler)  # type: ignore[arg-type]
