"""Game state snapshot."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class GameState:
    """Server game state.

    Attributes:
        game_mode: Current game mode (``"survival"``, ``"creative"``,
            ``"adventure"``, ``"spectator"``).
        dimension: Current dimension (``"overworld"``, ``"the_nether"``,
            ``"the_end"``).
        difficulty: Server difficulty (``"peaceful"``, ``"easy"``,
            ``"normal"``, ``"hard"``).
        hardcore: Whether the server is in hardcore mode.
        max_players: Maximum number of players.
        server_brand: Server brand string (e.g. ``"vanilla"``).
        min_y: Minimum Y coordinate for the current dimension.
        height: World height for the current dimension.
    """

    game_mode: str
    dimension: str
    difficulty: str
    hardcore: bool
    max_players: int
    server_brand: str
    min_y: int
    height: int
