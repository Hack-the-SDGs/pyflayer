"""Typed public plugin-management API."""

from typing import TYPE_CHECKING

from minethon.models.errors import PluginError

if TYPE_CHECKING:
    from minethon._bridge.plugin_registry import PluginRegistry


class PluginAPI:
    """Manage supported mineflayer plugins through a stable Python API."""

    def __init__(self, registry: PluginRegistry) -> None:
        self._registry = registry

    @property
    def supported(self) -> tuple[str, ...]:
        """Plugin package names that minethon currently wraps."""
        return self._registry.supported

    async def load(self, name: str) -> None:
        """Load a supported plugin by package name.

        This method stays on the bridge owner thread because JSPyBridge
        calls are thread-affine.  The first load may take a while if
        Node.js needs to resolve or install the package.

        Raises:
            PluginError: If the plugin is not registered.
            BridgeError: If loading the JS module fails.
        """
        if name not in self._registry.supported:
            raise PluginError(
                f"Unsupported plugin '{name}'. "
                f"Supported plugins: {', '.join(self.supported)}"
            )
        self._registry.load(name)

    def is_loaded(self, name: str) -> bool:
        """Whether a supported plugin is already active.

        Returns ``False`` for plugin names not in :attr:`supported`.
        """
        return self._registry.is_loaded(name)
