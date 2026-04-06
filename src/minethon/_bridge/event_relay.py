"""Bridge JS EventEmitter callbacks into asyncio dispatch."""

import asyncio
import logging
import time
from collections import defaultdict
from collections.abc import Coroutine
from typing import Any, Callable

from minethon._bridge._events import (
    DigDoneEvent,
    EquipDoneEvent,
    LookAtDoneEvent,
    PlaceDoneEvent,
)
from minethon.models.events import (
    ChatEvent,
    DeathEvent,
    EndEvent,
    GoalFailedEvent,
    GoalReachedEvent,
    HealthChangedEvent,
    KickedEvent,
    SpawnEvent,
    WhisperEvent,
)
from minethon.models.vec3 import Vec3

_log = logging.getLogger(__name__)

_HIGH_FREQ_EVENTS: frozenset[str] = frozenset({"physicsTick", "entityMoved"})
_SLOW_HANDLER_THRESHOLD: float = 0.5  # 500ms

# Static events always bound by register_js_events().
_STATIC_BRIDGED_EVENTS: frozenset[str] = frozenset({
    "spawn", "chat", "whisper", "health", "death",
    "kicked", "end", "goal_reached", "path_update", "path_stop",
    "_minethon:digDone", "_minethon:placeDone",
    "_minethon:equipDone", "_minethon:lookAtDone",
})


class EventRelay:
    """Receives JS events on the JSPyBridge callback thread and
    dispatches them to asyncio handlers via ``call_soon_threadsafe``.
    """

    def __init__(
        self, event_throttle_ms: dict[str, int] | None = None
    ) -> None:
        self._loop: asyncio.AbstractEventLoop | None = None
        self._handlers: dict[type, list[Callable[..., Coroutine[Any, Any, None]]]] = (
            defaultdict(list)
        )
        self._waiters: dict[type, list[asyncio.Future[Any]]] = defaultdict(list)
        # Raw event handlers keyed by JS event name
        self._raw_handlers: dict[
            str, list[Callable[..., Coroutine[Any, Any, None]]]
        ] = defaultdict(list)
        # Strong refs to prevent GC (JSPyBridge uses WeakValueDictionary)
        self._js_handler_refs: list[Any] = []
        # Per-event throttle: event_name -> interval in seconds
        throttle_cfg = event_throttle_ms if event_throttle_ms is not None else {"move": 50}
        self._throttle_intervals: dict[str, float] = {
            name: ms / 1000.0 for name, ms in throttle_cfg.items()
        }
        self._throttle_last_post: dict[str, float] = {}
        # Events actually registered by register_js_events(); used by
        # bind_raw_js_event() to avoid duplicate JS listeners.
        self._registered_events: set[str] = set(_STATIC_BRIDGED_EVENTS)
        # Suppress GoalFailedEvent from path_stop after a successful goal_reached
        self._goal_just_reached: bool = False

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Bind to the running asyncio event loop."""
        self._loop = loop

    def reset(self) -> None:
        """Clean up JS handler references, pending waiters, and loop binding.

        Call on disconnect so that a subsequent ``connect()`` starts
        with a clean slate.  Clearing ``_loop`` ensures that
        ``wait_for()`` raises ``RuntimeError`` (surfaced as
        ``MinethonConnectionError`` by ``ObserveAPI``) when the bot
        is not connected, rather than silently timing out.
        """
        self._js_handler_refs.clear()
        # Cancel all pending waiters
        for waiter_list in self._waiters.values():
            for fut in waiter_list:
                if not fut.done():
                    fut.cancel()
        self._waiters.clear()
        self._throttle_last_post.clear()
        self._goal_just_reached = False
        self._loop = None

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

        @on_fn(js_bot, "whisper")
        def _on_whisper(*args: Any) -> None:
            if len(args) < 2:
                return
            username = str(args[0])
            message = str(args[1])
            event = WhisperEvent(
                sender=username,
                message=message,
                timestamp=time.time(),
            )
            self._post(WhisperEvent, event)

        @on_fn(js_bot, "health")
        def _on_health(*_args: Any) -> None:
            try:
                event = HealthChangedEvent(
                    health=float(js_bot.health),
                    food=float(js_bot.food),
                    saturation=float(js_bot.foodSaturation),
                )
                self._post(HealthChangedEvent, event)
            except (AttributeError, TypeError):
                _log.debug("Failed to read health data", exc_info=True)

        @on_fn(js_bot, "death")
        def _on_death(*_args: Any) -> None:
            self._post(DeathEvent, DeathEvent(reason=None))

        @on_fn(js_bot, "kicked")
        def _on_kicked(*args: Any) -> None:
            reason = str(args[0]) if len(args) > 0 else "unknown"
            logged_in = bool(args[1]) if len(args) > 1 else False
            self._post(KickedEvent, KickedEvent(reason=reason, logged_in=logged_in))

        @on_fn(js_bot, "goal_reached")
        def _on_goal_reached(*_args: Any) -> None:
            self._goal_just_reached = True
            try:
                pos = js_bot.entity.position
                event = GoalReachedEvent(
                    position=Vec3(float(pos.x), float(pos.y), float(pos.z))
                )
                self._post(GoalReachedEvent, event)
            except (AttributeError, TypeError):
                self._post(
                    GoalReachedEvent,
                    GoalReachedEvent(position=Vec3(0.0, 0.0, 0.0)),
                )

        @on_fn(js_bot, "path_update")
        def _on_path_update(*args: Any) -> None:
            if not args:
                return
            result = args[0]
            status = getattr(result, "status", None)
            if status is not None and str(status) == "noPath":
                self._post(
                    GoalFailedEvent,
                    GoalFailedEvent(reason="noPath"),
                )

        @on_fn(js_bot, "path_stop")
        def _on_path_stop(*_args: Any) -> None:
            if not self._goal_just_reached:
                self._post(
                    GoalFailedEvent,
                    GoalFailedEvent(reason="stopped"),
                )
            self._goal_just_reached = False

        @on_fn(js_bot, "end")
        def _on_end(*args: Any) -> None:
            reason = str(args[0]) if len(args) > 0 else "unknown"
            self._post(EndEvent, EndEvent(reason=reason))

        # -- Internal async-operation completion events --

        @on_fn(js_bot, "_minethon:digDone")
        def _on_dig_done(*args: Any) -> None:
            error = str(args[0]) if args and args[0] is not None else None
            self._post(DigDoneEvent, DigDoneEvent(error=error))

        @on_fn(js_bot, "_minethon:placeDone")
        def _on_place_done(*args: Any) -> None:
            error = str(args[0]) if args and args[0] is not None else None
            self._post(PlaceDoneEvent, PlaceDoneEvent(error=error))

        @on_fn(js_bot, "_minethon:equipDone")
        def _on_equip_done(*args: Any) -> None:
            error = str(args[0]) if args and args[0] is not None else None
            self._post(EquipDoneEvent, EquipDoneEvent(error=error))

        @on_fn(js_bot, "_minethon:lookAtDone")
        def _on_look_at_done(*args: Any) -> None:
            error = str(args[0]) if args and args[0] is not None else None
            self._post(LookAtDoneEvent, LookAtDoneEvent(error=error))

        # -- Throttled high-frequency events --

        throttled_handlers: list[object] = []
        for event_name in self._throttle_intervals:
            interval = self._throttle_intervals[event_name]
            # Capture event_name and interval per-iteration
            def _make_throttled(
                evt: str, intv: float
            ) -> Callable[..., None]:
                def _handler(*_args: Any) -> None:
                    now = time.monotonic()
                    last = self._throttle_last_post.get(evt, 0.0)
                    if now - last < intv:
                        return
                    self._throttle_last_post[evt] = now
                    self._post_raw(evt, {"args": list(_args)})
                return _handler

            handler = _make_throttled(event_name, interval)
            on_fn(js_bot, event_name)(handler)
            throttled_handlers.append(handler)
            self._registered_events.add(event_name)

        self._js_handler_refs.extend([
            _on_spawn,
            _on_chat,
            _on_whisper,
            _on_health,
            _on_death,
            _on_kicked,
            _on_end,
            _on_goal_reached,
            _on_path_update,
            _on_path_stop,
            _on_dig_done,
            _on_place_done,
            _on_equip_done,
            _on_look_at_done,
            *throttled_handlers,
        ])

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

    def add_raw_handler(
        self, event_name: str, handler: Callable[..., Coroutine[Any, Any, None]]
    ) -> None:
        """Register an async handler for a raw JS event name."""
        self._raw_handlers[event_name].append(handler)

    def remove_raw_handler(
        self, event_name: str, handler: Callable[..., Coroutine[Any, Any, None]]
    ) -> None:
        """Unregister a raw event handler."""
        self._raw_handlers[event_name].remove(handler)

    def bind_raw_js_event(
        self, js_bot: Any, on_fn: Any, event_name: str
    ) -> None:
        """Dynamically bind a raw JS event for ``on_raw()`` subscribers.

        Events already handled by :meth:`register_js_events` are
        skipped to avoid attaching a duplicate (unthrottled) listener.

        Args:
            js_bot: The JS bot proxy.
            on_fn: The ``On`` decorator from JSPyBridge.
            event_name: The JS event name to listen for.
        """
        if event_name in self._registered_events:
            return

        if event_name in _HIGH_FREQ_EVENTS:
            _log.warning(
                "Subscribing to high-frequency event '%s'. "
                "This may impact performance. Consider throttling "
                "in your handler.",
                event_name,
            )

        @on_fn(js_bot, event_name)
        def _on_raw(*args: Any) -> None:
            data: dict[str, Any] = {"args": list(args)}
            self._post_raw(event_name, data)

        self._js_handler_refs.append(_on_raw)

    async def wait_for(self, event_type: type, *, timeout: float = 30.0) -> Any:
        """Wait for a single event of the given type."""
        if self._loop is None:
            raise RuntimeError(
                "EventRelay has no bound event loop. "
                "Call Bot.connect() before waiting for events."
            )
        fut: asyncio.Future[Any] = self._loop.create_future()
        self._waiters[event_type].append(fut)
        try:
            return await asyncio.wait_for(fut, timeout=timeout)
        finally:
            waiters = self._waiters.get(event_type, [])
            if fut in waiters:
                waiters.remove(fut)

    # -- Internal dispatch --

    def _post(self, event_type: type, event: object) -> None:
        """Thread-safe post from JSPyBridge callback thread."""
        if self._loop is not None and self._loop.is_running():
            try:
                self._loop.call_soon_threadsafe(self._dispatch, event_type, event)
            except RuntimeError:
                pass  # Event loop closed during shutdown

    def _post_raw(self, event_name: str, data: dict[str, Any]) -> None:
        """Thread-safe post for raw events."""
        if self._loop is not None and self._loop.is_running():
            try:
                self._loop.call_soon_threadsafe(
                    self._dispatch_raw, event_name, data
                )
            except RuntimeError:
                pass

    @staticmethod
    async def _timed(
        coro: Coroutine[Any, Any, None], name: str
    ) -> None:
        """Run a handler coroutine with execution-time monitoring."""
        t0 = time.monotonic()
        try:
            await coro
        except Exception as exc:
            _log.exception(
                "Unhandled exception in event handler %s",
                name,
                exc_info=exc,
            )
        finally:
            elapsed = time.monotonic() - t0
            if elapsed > _SLOW_HANDLER_THRESHOLD:
                _log.warning(
                    "Event handler '%s' took %.1fms (threshold: %.0fms)",
                    name,
                    elapsed * 1000,
                    _SLOW_HANDLER_THRESHOLD * 1000,
                )

    def _dispatch(self, event_type: type, event: object) -> None:
        """Runs on the asyncio event loop thread."""
        for fut in self._waiters.pop(event_type, []):
            if not fut.done():
                fut.set_result(event)
        if self._loop is not None:
            for handler in self._handlers.get(event_type, []):
                self._loop.create_task(
                    self._timed(
                        handler(event),
                        getattr(handler, "__qualname__", repr(handler)),
                    )
                )

    def _dispatch_raw(self, event_name: str, data: dict[str, Any]) -> None:
        """Dispatch raw events on the asyncio event loop thread."""
        if self._loop is not None:
            for handler in self._raw_handlers.get(event_name, []):
                self._loop.create_task(
                    self._timed(
                        handler(data),
                        getattr(handler, "__qualname__", repr(handler)),
                    )
                )
