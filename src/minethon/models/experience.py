"""Experience state snapshot."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Experience:
    """Bot experience state.

    Attributes:
        level: Current experience level.
        points: Total experience points.
        progress: Progress to next level (0.0 to 1.0).
    """

    level: int
    points: int
    progress: float
