"""Central registry for Type A / Type D mineflayer plugins.

Type B (services) and Type C (class libraries) are **not** managed here.
They use ``bot.<service>`` lazy properties instead.

Ref: docs/architecture/plugin-expansion-plan.md §3
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from minethon._bridge._util import extract_js_stack
from minethon._bridge.plugins.pathfinder import PathfinderBridge
from minethon.models.errors import BridgeError, PluginError

if TYPE_CHECKING:
    from minethon._bridge.event_relay import EventRelay
    from minethon._bridge.plugins._base import PluginBridge
    from minethon._bridge.runtime import BridgeRuntime


class PluginRegistry:
    """Manages loading, lookup and lifecycle of plugin bridges.

    Each supported plugin has a :class:`PluginBridge` subclass registered
    by npm name.  :meth:`load` resolves dependencies via
    ``PluginBridge.DEPENDS_ON`` before calling ``bridge.load()``.
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
        self._bridges: dict[str, PluginBridge] = {}
        self._register_builtins()

    def _register_builtins(self) -> None:
        """Register all built-in plugin bridges."""
        self._register(PathfinderBridge)

    def _register(self, bridge_cls: type[PluginBridge]) -> None:
        """Register a plugin bridge class by its NPM_NAME."""
        name = bridge_cls.NPM_NAME
        bridge = bridge_cls(self._runtime, self._js_bot, self._relay)
        self._bridges[name] = bridge

    @property
    def supported(self) -> tuple[str, ...]:
        """NPM names of all registered plugins."""
        return tuple(sorted(self._bridges))

    def load(self, name: str) -> None:
        """Load a plugin by npm name.  Resolves dependencies first.

        Args:
            name: npm package name (e.g. ``"mineflayer-pathfinder"``).

        Raises:
            PluginError: If the plugin is not registered.
            BridgeError: If loading the JS module fails.
        """
        bridge = self._bridges.get(name)
        if bridge is None:
            raise PluginError(
                f"Unsupported plugin '{name}'. "
                f"Supported: {', '.join(self.supported)}"
            )
        for dep in bridge.DEPENDS_ON:
            self.load(dep)
        bridge.load()

    def is_loaded(self, name: str) -> bool:
        """Whether a registered plugin is currently loaded."""
        bridge = self._bridges.get(name)
        return bridge.is_loaded if bridge is not None else False

    def get(self, name: str) -> PluginBridge | None:
        """Return the bridge instance for a registered plugin, or None."""
        return self._bridges.get(name)

    def get_pathfinder(self) -> PathfinderBridge | None:
        """Convenience: return the PathfinderBridge if registered."""
        bridge = self._bridges.get(PathfinderBridge.NPM_NAME)
        if isinstance(bridge, PathfinderBridge):
            return bridge
        return None

    def teardown_all(self) -> None:
        """Call teardown() on every loaded plugin.  Best-effort."""
        for bridge in self._bridges.values():
            if bridge.is_loaded:
                try:
                    bridge.teardown()
                except Exception:  # noqa: S110
                    pass  # Best-effort: don't mask the original error

    def raw_require(self, name: str) -> Any:
        """Escape hatch: load any npm module via ``require()``.

        This replaces the old ``PluginHost.raw_plugin()`` path and
        is used by ``bot.raw.plugin()``.

        Args:
            name: npm package name.

        Returns:
            The raw JS module proxy.

        Warning:
            No type safety or stability guarantees.
        """
        try:
            return self._runtime.require(name)
        except Exception as exc:
            raise BridgeError(
                f"raw_require '{name}' failed: {exc}",
                js_stack=extract_js_stack(exc),
            ) from exc
