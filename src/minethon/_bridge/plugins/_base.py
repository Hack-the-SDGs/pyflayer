"""Base class for Type A / Type D plugin bridges."""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, ClassVar

if TYPE_CHECKING:
    from minethon._bridge.event_relay import EventRelay
    from minethon._bridge.runtime import BridgeRuntime


class PluginBridge(ABC):
    """Base class for ``bot.loadPlugin()``-style plugin bridges.

    Subclasses represent Type A (direct inject function) and Type D
    (higher-order function) mineflayer plugins.  Type B (services) and
    Type C (class libraries) do **not** inherit from this class.

    Ref: docs/architecture/plugin-expansion-plan.md §3
    """

    NPM_NAME: ClassVar[str]
    """npm package name used by ``BridgeRuntime.require()``."""

    DEPENDS_ON: ClassVar[tuple[str, ...]] = ()
    """NPM names of plugins that must be loaded first."""

    def __init__(
        self,
        runtime: BridgeRuntime,
        js_bot: Any,
        relay: EventRelay,
    ) -> None:
        self._runtime = runtime
        self._js_bot = js_bot
        self._relay = relay
        self._loaded = False

    @property
    def is_loaded(self) -> bool:
        """Whether this plugin has been loaded into the JS bot."""
        return self._loaded

    @abstractmethod
    def _do_load(self) -> None:
        """Perform the actual JS plugin loading.

        Called exactly once by :meth:`load`.  Implementations should
        ``require()`` the npm module and call ``js_bot.loadPlugin()``.
        """

    def load(self) -> None:
        """Load the plugin.  Idempotent — second calls are no-ops."""
        if self._loaded:
            return
        self._do_load()
        self._loaded = True

    def teardown(self) -> None:  # noqa: B027
        """Clean up on disconnect.  Override for plugin-specific cleanup."""
