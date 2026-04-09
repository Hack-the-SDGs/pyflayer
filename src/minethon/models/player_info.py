"""Player information snapshot."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PlayerInfo:
    """Online player information.

    Attributes:
        username: Player username.
        uuid: Player UUID string.
        ping: Network latency in milliseconds.
        game_mode: Numeric game mode (0=survival, 1=creative,
            2=adventure, 3=spectator).
        display_name: Custom display name, or ``None``.
    """

    username: str
    uuid: str
    ping: int
    game_mode: int
    display_name: str | None = None
