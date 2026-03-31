"""Bot configuration."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class BotConfig:
    """Configuration for creating a Bot."""

    host: str
    port: int = 25565
    username: str = "pyflayer"
    version: str | None = None
    auth: str | None = None
    hide_errors: bool = False
