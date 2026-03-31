"""Exception hierarchy for pyflayer."""


class PyflayerError(Exception):
    """Base exception for all pyflayer errors."""


class ConnectionError(PyflayerError):
    """Connection failed or disconnected."""


class NotSpawnedError(PyflayerError):
    """Bot has not spawned yet."""


class NavigationError(PyflayerError):
    """Navigation failed."""


class InventoryError(PyflayerError):
    """Inventory operation failed."""


class PluginError(PyflayerError):
    """Plugin loading or invocation failed."""


class BridgeError(PyflayerError):
    """Bridge communication error."""

    def __init__(self, message: str, js_stack: str | None = None) -> None:
        super().__init__(message)
        self.js_stack = js_stack
