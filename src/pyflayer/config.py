"""Bot configuration."""

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class BotConfig:
    """Configuration for creating a Bot.

    Args:
        host: Server hostname or IP.
        port: Server port.
        username: Bot username.
        password: Account password (for authenticated servers).
        version: Minecraft version string (e.g. ``"1.20.1"``).
            Auto-detected when ``None``.
        auth: Authentication mode (``"microsoft"``, ``"mojang"``,
            ``"offline"``, or ``None`` for default).
        auth_server: Custom authentication server URL
            (e.g. ``"https://drasl.example.com/auth"``).
        session_server: Custom session server URL
            (e.g. ``"https://drasl.example.com/session"``).
        hide_errors: Suppress internal error logging from mineflayer.
            ``None`` uses mineflayer's default (currently ``False``).
        log_errors: Log errors to the console.
            ``None`` uses mineflayer's default.
        disable_chat_signing: Disable chat message signing (1.19.1+).
            ``None`` uses mineflayer's default (currently ``False``).
        check_timeout_interval: Milliseconds between keep-alive checks.
            Set to ``0`` to disable. ``None`` uses mineflayer's default
            (currently ``30_000``).
        keep_alive: Send keep-alive packets.
            ``None`` uses mineflayer's default.
        respawn: Auto-respawn after death.
            ``None`` uses mineflayer's default.
        chat_length_limit: Maximum chat message length.
            ``None`` uses mineflayer's default.
        view_distance: Client-side view distance
            (``"tiny"``, ``"short"``, ``"normal"``, ``"far"``).
            ``None`` uses mineflayer's default.
        default_chat_patterns: Enable default chat pattern parsing.
            ``None`` uses mineflayer's default.
        physics_enabled: Enable client-side physics simulation.
            ``None`` uses mineflayer's default.
        brand: Custom client brand string.
            ``None`` uses mineflayer's default.
        skip_validation: Skip account validation on login.
            ``None`` uses mineflayer's default.
        profiles_folder: Path to the folder containing auth profiles.
            ``None`` uses mineflayer's default.
        load_internal_plugins: Load mineflayer's built-in plugins.
            ``None`` uses mineflayer's default.
        event_throttle_ms: Per-event throttle intervals in milliseconds.
            Keys are JS event names, values are minimum intervals between
            dispatches. Events arriving faster than the interval are
            silently dropped.  Default: ``{"move": 50}`` (aligned with
            Minecraft's 20 TPS = 50 ms/tick).
    """

    host: str
    port: int = 25565
    username: str = "pyflayer"
    password: str | None = field(default=None, repr=False)
    version: str | None = None
    auth: str | None = None
    auth_server: str | None = None
    session_server: str | None = None
    hide_errors: bool | None = None
    log_errors: bool | None = None
    disable_chat_signing: bool | None = None
    check_timeout_interval: int | None = None
    keep_alive: bool | None = None
    respawn: bool | None = None
    chat_length_limit: int | None = None
    view_distance: str | None = None
    default_chat_patterns: bool | None = None
    physics_enabled: bool | None = None
    brand: str | None = None
    skip_validation: bool | None = None
    profiles_folder: str | None = None
    load_internal_plugins: bool | None = None
    event_throttle_ms: dict[str, int] = field(
        default_factory=lambda: {"move": 50}
    )
