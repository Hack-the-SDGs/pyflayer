"""Typed public plugin-management API."""

from minethon._bridge.plugin_host import PluginHost
from minethon.models.errors import PluginError


class PluginAPI:
    """Manage supported mineflayer plugins through a stable Python API."""

    _SUPPORTED_PLUGINS: tuple[str, ...] = ("mineflayer-pathfinder",)

    def __init__(self, host: PluginHost) -> None:
        self._host = host

    @property
    def supported(self) -> tuple[str, ...]:
        """Plugin package names that minethon currently wraps."""
        return self._SUPPORTED_PLUGINS

    async def load(self, name: str) -> None:
        """Load a supported plugin by package name.

        This method stays on the bridge owner thread because JSPyBridge
        calls are thread-affine. The first load may still take a while if
        Node.js needs to resolve or install the package.
        """
        if name == "mineflayer-pathfinder":
            self._host.load_pathfinder()
            return
        raise PluginError(
            f"Unsupported plugin '{name}'. Supported plugins: {', '.join(self.supported)}"
        )

    def is_loaded(self, name: str) -> bool:
        """Whether a supported plugin is already active.

        Returns ``False`` for plugin names not in :attr:`supported`.
        """
        if name == "mineflayer-pathfinder":
            return self._host.is_pathfinder_loaded()
        return False
