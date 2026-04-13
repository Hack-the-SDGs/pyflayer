"""Bot — public entry point for minethon.

Runtime behavior lives here. A sibling `bot.pyi` (generated from
mineflayer's `index.d.ts`) supplies the typed overloads that IDEs
use for completion of event names, callback signatures, and
properties like `bot.health`, `bot.entity.position`, etc.

Pure synchronous callback model — no asyncio. Long-running JS work
(dig, goto, ...) reports completion via handlers registered with
`@bot.on(BotEvent.X)` or `@bot.on_x`.
"""

from __future__ import annotations

import inspect
import threading
from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar

from javascript import On, Once, require

from minethon import _type_shells
from minethon._bridge import BUNDLED_VERSIONS, get_mineflayer
from minethon._events import EVENT_ATTRIBUTE_MAP, BotEvent
from minethon._handlers import BotHandlers
from minethon.errors import PluginNotInstalledError, VersionPinRequiredError

F = TypeVar("F", bound=Callable[..., Any])

globals().update(
    {name: getattr(_type_shells, name) for name in _type_shells.TYPE_SHELL_NAMES}
)


def _require_event(method: str, event: object) -> BotEvent:
    if isinstance(event, BotEvent):
        return event
    msg = (
        f"bot.{method}(...) 只接受 BotEvent。"
        "請改用 @bot.on_<event> / @bot.once_<event>，"
        "或傳入 BotEvent.CHAT 這種 enum 成員。"
    )
    raise TypeError(msg)


def _normalize_handler(
    func: Callable[..., Any], *, emitter: Any | None = None
) -> Callable[..., Any]:
    """Adapt a user handler to mineflayer's loose event-arity conventions.

    Mineflayer's TypeScript typings sometimes declare trailing callback
    parameters that the JS runtime never actually emits (the ``chat`` event's
    ``matches: string[] | null`` is the canonical example — the type
    advertises 5 args but ``lib/plugins/chat.js`` only emits 4). A handler
    written against the declared signature would otherwise crash with
    ``TypeError: missing positional argument``.

    This wrapper:

    * drops the leading emitter arg when JSPyBridge injects it
    * pads missing trailing positional args with ``None``
    * truncates any excess positional args JS emits

    Ref: mineflayer/lib/plugins/chat.js:85 — chat event emit arity
    Ref: javascript/__init__.py:78 — optional emitter injection in `On` / `Once`
    """
    params = list(inspect.signature(func).parameters.values())
    accepts_varargs = any(p.kind is inspect.Parameter.VAR_POSITIONAL for p in params)
    slots = sum(
        1
        for p in params
        if p.kind
        in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
    )

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        if emitter is not None and args and args[0] is emitter:
            args = args[1:]
        if accepts_varargs:
            return func(*args, **kwargs)
        if len(args) < slots:
            args = (*args, *([None] * (slots - len(args))))
        return func(*args[:slots], **kwargs)

    return wrapper


# npm package → attribute on the required module that holds the plugin
# installer function. Most plugins export the installer as the default,
# but a few (pathfinder) expose it on a named property.
_PLUGIN_EXPORT_KEY: dict[str, str] = {
    "mineflayer-pathfinder": "pathfinder",
}


class Bot:
    """Pythonic façade over a mineflayer Bot proxy.

    Prefer `create_bot(...)` over direct construction. Unknown attribute
    reads fall through to the underlying JS proxy, so every documented
    mineflayer property or method works transparently.

    Ref: mineflayer/index.d.ts — Bot interface
    """

    _js: Any

    def __init__(self, js_bot: Any) -> None:
        """Wrap an existing mineflayer JS bot proxy."""
        object.__setattr__(self, "_js", js_bot)

    def __getattr__(self, name: str) -> Any:
        """Forward attribute reads to the underlying JS bot.

        Private names (leading underscore) are not forwarded — they should
        be set via `object.__setattr__` in this class or raise AttributeError.

        Ref: mineflayer/index.d.ts — all fields on the Bot interface
        """
        if name.startswith("_"):
            raise AttributeError(name)
        if name.startswith("on_"):
            event = EVENT_ATTRIBUTE_MAP.get(name[3:])
            if event is not None:
                return self.on(event)
        if name.startswith("once_"):
            event = EVENT_ATTRIBUTE_MAP.get(name[5:])
            if event is not None:
                return self.once(event)
        try:
            return getattr(self._js, name)
        except AttributeError as exc:
            if name == "pathfinder":
                msg = (
                    "pathfinder 尚未載入。先呼叫 "
                    "bot.load_plugin('mineflayer-pathfinder')。"
                )
                raise PluginNotInstalledError(msg) from exc
            raise

    def on(self, event: BotEvent) -> Callable[[F], F]:
        """Register a handler for a mineflayer event.

        Per-event typed overloads live in `bot.pyi`; at runtime this is a
        generic dispatcher. Handlers run on the JSPyBridge event thread —
        do not block them with long Python work.

        Handler arity is auto-normalized: mineflayer occasionally types
        more callback params than it emits (the ``chat`` event is the
        classic case), so missing trailing args are padded with ``None``.

        Ref: mineflayer/index.d.ts — Bot extends EventEmitter, see `on()`
        """
        js_bot = self._js
        event_name = _require_event("on", event).value

        def decorator(func: F) -> F:
            On(js_bot, event_name)(_normalize_handler(func, emitter=js_bot))
            return func

        return decorator

    def once(self, event: BotEvent) -> Callable[[F], F]:
        """Register a one-shot event handler.

        Same arity-normalization rules apply as ``on()``.

        Ref: mineflayer/index.d.ts — Bot.once (from EventEmitter)
        """
        js_bot = self._js
        event_name = _require_event("once", event).value

        def decorator(func: F) -> F:
            Once(js_bot, event_name)(_normalize_handler(func, emitter=js_bot))
            return func

        return decorator

    def load_plugin(
        self,
        name: str,
        version: str | None = None,
        *,
        export_key: str | None = None,
        **options: Any,
    ) -> Any:
        """Install a Type A mineflayer plugin in one line.

        Args:
            name: npm package name (e.g. ``"mineflayer-pathfinder"``).
            version: pinned version string. Bundled plugins may omit this and
                use minethon's pinned default; all other packages must pass an
                explicit version so npm resolution stays reproducible.
            export_key: which attribute of the loaded module holds the
                plugin installer function. Pass this for packages whose
                installer is a named export (e.g. pathfinder's ``pathfinder``).
                Overrides the built-in defaults in ``_PLUGIN_EXPORT_KEY``.
            **options: collected into a Python dict and forwarded as a
                single JS options-object to higher-order plugin factories
                (e.g. ``dashboard({port: 25566})`` → ``bot.load_plugin(
                "@ssmidge/mineflayer-dashboard", port=25566)``). This
                matches the standard JS ``factory(opts)`` convention and
                is required because JSPyBridge's ``Proxy.__call__`` only
                accepts positional args — Python ``**kwargs`` expansion
                would raise ``TypeError`` at the bridge boundary.
                Regular plugins ignore this.

        Returns:
            The raw JS module — use the result to access classes/constants
            the plugin exports, e.g. ``pf.goals.GoalNear(x, y, z, 1)``.

        Ref: mineflayer/index.d.ts — Bot.loadPlugin (expects a ``(bot, options) => void`` function)
        """
        resolved_version = _resolve_package_version(name, version)
        module = require(name, resolved_version)
        key = export_key or _PLUGIN_EXPORT_KEY.get(name)
        plugin_fn = getattr(module, key) if key else module
        if options:
            # Pass as a single JS object — JSPyBridge marshals the Python
            # dict to a JS object literal. `plugin_fn(**options)` would fail
            # because the bridge's Proxy.__call__ rejects keyword args.
            plugin_fn = plugin_fn(options)
        self._js.loadPlugin(plugin_fn)
        return module

    @staticmethod
    def require(name: str, version: str | None = None) -> Any:
        """Raw escape hatch — load a JS module and return its proxy.

        Use for Type B/C/D plugins (prismarine-viewer, web-inventory,
        mineflayer-statemachine, etc.) that don't fit the single-call
        ``bot.loadPlugin`` pattern. You get the raw module back; initialize
        it yourself following the package's README.

        Args:
            name: npm package name.
            version: pinned version. Pass this unless the package is one of
                minethon's bundled defaults.

        Returns:
            The raw JS module proxy — everything on it is untyped.

        Ref: javascript.require (JSPyBridge)
        """
        resolved_version = _resolve_package_version(name, version)
        return require(name, resolved_version)

    def bind(self, handlers: BotHandlers) -> BotHandlers:
        """Register every overridden ``on_<event>`` on a `BotHandlers` instance.

        Walks :class:`BotHandlers`' generated method set, finds entries
        overridden on the concrete subclass, and wires each one to the
        matching :class:`BotEvent` via :meth:`on`. Handler arity is still
        normalized by ``_normalize_handler``, so short signatures like
        ``def on_chat(self, username, message)`` work.

        Returns the handlers instance so calls can chain.

        Example::

            class My(BotHandlers):
                def on_chat(self, username, message, *_): ...

            bot.bind(My())
        """
        for attr, event in EVENT_ATTRIBUTE_MAP.items():
            method_name = f"on_{attr}"
            impl = getattr(type(handlers), method_name, None)
            base_impl = getattr(BotHandlers, method_name, None)
            if impl is None or impl is base_impl:
                continue
            self.on(event)(getattr(handlers, method_name))
        return handlers

    def run_forever(self) -> None:
        """Block the calling thread until the bot disconnects.

        Intended as the last line of a student script — keeps the main
        Python thread alive while JSPyBridge's event thread drives the
        bot. Exits cleanly on `end` event or Ctrl-C.

        Uses `Once` so repeated calls don't accumulate listeners on the
        underlying JS EventEmitter.

        Ref: mineflayer/index.d.ts — Bot.on('end', reason)
        """
        done = threading.Event()

        def _on_end(*_a: Any, **_kw: Any) -> None:
            done.set()

        Once(self._js, BotEvent.END.value)(
            _normalize_handler(_on_end, emitter=self._js)
        )
        # Race guard: if `end` fired between create_bot() returning and the
        # Once(...) above, no listener was installed and done.wait() would
        # block forever. Seed `done` from the protocol client's `ended` flag
        # (minecraft-protocol sets it synchronously in end()/disconnect()).
        client = getattr(self._js, "_client", None)
        if client is not None and bool(getattr(client, "ended", False)):
            done.set()
        try:
            done.wait()
        except KeyboardInterrupt:
            pass


def create_bot(**options: Any) -> Bot:
    """Create and connect a mineflayer bot.

    Keyword options mirror `mineflayer.createBot()` with snake_case:
    `auth_server` → `authServer`, `session_server` → `sessionServer`, etc.
    Typed overloads live in `bot.pyi`.

    Returns immediately; the bot connects on the JS side. Register a
    `spawn` handler to know when you can send chat, move, etc.

    Ref: mineflayer/lib/loader.js — `createBot(options)`
    """
    js_options = {_to_camel(key): value for key, value in options.items()}
    mineflayer = get_mineflayer()
    js_bot = mineflayer.createBot(js_options)
    return Bot(js_bot)


def _to_camel(snake: str) -> str:
    """snake_case → camelCase (auth_server → authServer)."""
    head, *tail = snake.split("_")
    return head + "".join(part.capitalize() for part in tail)


def _resolve_package_version(name: str, version: str | None) -> str:
    if version is not None:
        return version
    default = BUNDLED_VERSIONS.get(name)
    if default is not None:
        return default
    msg = (
        f"`{name}` 需要顯式版本號。請改成 "
        f"`bot.require({name!r}, 'x.y.z')` 或 "
        f"`bot.load_plugin({name!r}, 'x.y.z')`。"
    )
    raise VersionPinRequiredError(msg)
