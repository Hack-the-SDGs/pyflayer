"""Bridge JS EventEmitter callbacks into asyncio dispatch."""

import asyncio
import logging
import time
from collections import defaultdict
from collections.abc import Coroutine
from typing import Any, Callable

from pyflayer._bridge._events import (
    _DigDoneEvent,
    _EquipDoneEvent,
    _LookAtDoneEvent,
    _PlaceDoneEvent,
)
from pyflayer.models.events import (
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
from pyflayer.models.vec3 import Vec3

_log = logging.getLogger(__name__)


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
        # Raw event handlers keyed by JS event name
        self._raw_handlers: dict[
            str, list[Callable[..., Coroutine[Any, Any, None]]]
        ] = defaultdict(list)
        # Strong refs to prevent GC (JSPyBridge uses WeakValueDictionary)
        self._js_handler_refs: list[Any] = []

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Bind to the running asyncio event loop."""
        self._loop = loop

    def reset(self) -> None:
        """Clean up JS handler references, pending waiters, and loop binding.

        Call on disconnect so that a subsequent ``connect()`` starts
        with a clean slate.  Clearing ``_loop`` ensures that
        ``wait_for()`` raises ``RuntimeError`` (surfaced as
        ``PyflayerConnectionError`` by ``ObserveAPI``) when the bot
        is not connected, rather than silently timing out.
        """
        self._js_handler_refs.clear()
        # Cancel all pending waiters
        for waiter_list in self._waiters.values():
            for fut in waiter_list:
                if not fut.done():
                    fut.cancel()
        self._waiters.clear()
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
            self._post(
                GoalFailedEvent,
                GoalFailedEvent(reason="stopped"),
            )

        @on_fn(js_bot, "end")
        def _on_end(*args: Any) -> None:
            reason = str(args[0]) if len(args) > 0 else "unknown"
            self._post(EndEvent, EndEvent(reason=reason))

        # -- Internal async-operation completion events --

        @on_fn(js_bot, "_pyflayer:digDone")
        def _on_dig_done(*args: Any) -> None:
            error = str(args[0]) if args and args[0] is not None else None
            self._post(_DigDoneEvent, _DigDoneEvent(error=error))

        @on_fn(js_bot, "_pyflayer:placeDone")
        def _on_place_done(*args: Any) -> None:
            error = str(args[0]) if args and args[0] is not None else None
            self._post(_PlaceDoneEvent, _PlaceDoneEvent(error=error))

        @on_fn(js_bot, "_pyflayer:equipDone")
        def _on_equip_done(*args: Any) -> None:
            error = str(args[0]) if args and args[0] is not None else None
            self._post(_EquipDoneEvent, _EquipDoneEvent(error=error))

        @on_fn(js_bot, "_pyflayer:lookAtDone")
        def _on_look_at_done(*args: Any) -> None:
            error = str(args[0]) if args and args[0] is not None else None
            self._post(_LookAtDoneEvent, _LookAtDoneEvent(error=error))

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

        Args:
            js_bot: The JS bot proxy.
            on_fn: The ``On`` decorator from JSPyBridge.
            event_name: The JS event name to listen for.
        """

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
    def _on_handler_done(task: asyncio.Task[None]) -> None:
        """Log exceptions from user event handlers."""
        if task.cancelled():
            return
        exc = task.exception()
        if exc is not None:
            _log.exception(
                "Unhandled exception in event handler %s",
                task.get_name(),
                exc_info=exc,
            )

    def _dispatch(self, event_type: type, event: object) -> None:
        """Runs on the asyncio event loop thread."""
        for fut in self._waiters.pop(event_type, []):
            if not fut.done():
                fut.set_result(event)
        if self._loop is not None:
            for handler in self._handlers.get(event_type, []):
                task = self._loop.create_task(handler(event))
                task.add_done_callback(self._on_handler_done)

    def _dispatch_raw(self, event_name: str, data: dict[str, Any]) -> None:
        """Dispatch raw events on the asyncio event loop thread."""
        if self._loop is not None:
            for handler in self._raw_handlers.get(event_name, []):
                task = self._loop.create_task(handler(data))
                task.add_done_callback(self._on_handler_done)
