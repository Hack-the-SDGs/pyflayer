"""Exception hierarchy for minethon."""


class MinethonError(Exception):
    """Base exception for all minethon errors."""


class MinethonConnectionError(MinethonError):
    """Connection failed or disconnected."""


class NotSpawnedError(MinethonError):
    """Bot has not spawned yet."""


class NavigationError(MinethonError):
    """Navigation failed."""


class InventoryError(MinethonError):
    """Inventory operation failed."""


class PluginError(MinethonError):
    """Plugin loading or invocation failed."""


class BridgeError(MinethonError):
    """Bridge communication error."""

    def __init__(self, message: str, js_stack: str | None = None) -> None:
        super().__init__(message)
        self.js_stack = js_stack

    def __str__(self) -> str:
        base = super().__str__()
        if self.js_stack:
            return f"{base}\n--- JS Stack ---\n{self.js_stack}"
        return base
