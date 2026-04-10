"""Event subscription API."""

from collections.abc import Awaitable, Callable, Coroutine
from typing import Any, TypeVar, overload

from minethon._bridge.event_relay import EventRelay
from minethon.models.errors import MinethonConnectionError

E = TypeVar("E")

_Handler = Callable[[E], Coroutine[Any, Any, None]]

_RawHandler = Callable[[dict[str, Any]], Awaitable[None]]


class ObserveAPI:
    """Event subscription API.

    Supports decorator-style and method-style registration plus
    one-shot ``wait_for`` for typed events.
    """

    def __init__(self, relay: EventRelay) -> None:
        self._relay = relay
        self._bound_raw_events: set[str] = set()
        self._pending_raw_events: set[str] = set()
        self._js_bot: Any = None
        self._on_fn: Any = None

    def _reset_state(self) -> None:
        """Clear JS binding state so the next ``_bind_js()`` starts clean.

        Called by ``Bot.disconnect()``. User-registered handlers are
        preserved across reconnect.
        """
        self._js_bot = None
        self._on_fn = None
        # Move bound events back to pending so they get rebound on reconnect
        self._pending_raw_events.update(self._bound_raw_events)
        self._bound_raw_events.clear()

    def _bind_js(self, js_bot: Any, on_fn: Any) -> None:
        """Store JS references and bind any queued or previously bound raw events.

        On initial connect only events queued before ``Bot.connect()``
        (``_pending_raw_events``) need binding.  On reconnect the
        underlying JS handlers have been cleared by
        ``EventRelay.reset()``, so all previously bound events must be
        re-bound to the new JS context as well.
        """
        new_context = self._js_bot is not js_bot or self._on_fn is not on_fn
        self._js_bot = js_bot
        self._on_fn = on_fn

        if new_context and self._bound_raw_events:
            # Re-bind all previously bound events to the new JS context
            all_events = self._bound_raw_events | self._pending_raw_events
            for event_name in all_events:
                self._relay.bind_raw_js_event(js_bot, on_fn, event_name)
            self._bound_raw_events = all_events
            self._pending_raw_events.clear()
        else:
            # Initial connect: bind only queued events
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
            MinethonConnectionError: If called before ``Bot.connect()``.
            asyncio.TimeoutError: If no event arrives within *timeout* seconds.
        """
        try:
            return await self._relay.wait_for(event_type, timeout=timeout)  # type: ignore[return-value]
        except RuntimeError as exc:
            raise MinethonConnectionError(
                "Bot is not connected; call Bot.connect() before wait_for()."
            ) from exc

    def _on_raw(
        self,
        event_name: str,
        handler: _RawHandler,
    ) -> None:
        """Subscribe to a raw JS event by name for ``bot.raw``."""
        if event_name not in self._bound_raw_events:
            if self._js_bot is not None and self._on_fn is not None:
                self._relay.bind_raw_js_event(
                    self._js_bot, self._on_fn, event_name
                )
                self._bound_raw_events.add(event_name)
            else:
                self._pending_raw_events.add(event_name)
        self._relay.add_raw_handler(event_name, handler)  # type: ignore[arg-type]

    def _off_raw(self, event_name: str, handler: _RawHandler) -> None:
        """Unsubscribe a raw event handler for ``bot.raw``."""
        self._relay.remove_raw_handler(event_name, handler)  # type: ignore[arg-type]
