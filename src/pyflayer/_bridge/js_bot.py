"""Encapsulates all operations on the JS mineflayer bot object."""

from typing import Any

from pyflayer._bridge.runtime import BridgeRuntime
from pyflayer.config import BotConfig


class JSBotController:
    """The sole holder of the JS bot proxy.

    All methods are **synchronous** (they block on JSPyBridge IPC).
    The public :class:`~pyflayer.bot.Bot` wraps them with
    ``asyncio.to_thread``.
    """

    def __init__(self, runtime: BridgeRuntime, config: BotConfig) -> None:
        self._runtime = runtime
        self._config = config
        self._js_bot: Any = None

    def create_bot(self) -> None:
        """Call ``mineflayer.createBot()`` — starts connecting immediately."""
        mineflayer = self._runtime.require("mineflayer")
        options: dict[str, Any] = {
            "host": self._config.host,
            "port": self._config.port,
            "username": self._config.username,
            "hideErrors": self._config.hide_errors,
        }
        if self._config.version is not None:
            options["version"] = self._config.version
        if self._config.auth is not None:
            options["auth"] = self._config.auth
        self._js_bot = mineflayer.createBot(options)

    @property
    def js_bot(self) -> Any:
        """Raw JS bot proxy (for event binding)."""
        return self._js_bot

    def chat(self, message: str) -> None:
        """Send a chat message. Blocking."""
        self._js_bot.chat(message)

    def get_position(self) -> dict[str, float]:
        """Read bot position as ``{x, y, z}`` dict."""
        pos = self._js_bot.entity.position
        return {"x": float(pos.x), "y": float(pos.y), "z": float(pos.z)}

    def get_health(self) -> float:
        """Read bot health (0-20)."""
        return float(self._js_bot.health)

    def get_food(self) -> float:
        """Read bot food level (0-20)."""
        return float(self._js_bot.food)

    def get_username(self) -> str:
        """Read bot username."""
        return str(self._js_bot.username)

    def quit(self) -> None:
        """Graceful disconnect. Blocking."""
        if self._js_bot is not None:
            self._js_bot.quit()
