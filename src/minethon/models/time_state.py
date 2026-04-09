"""Time state snapshot."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TimeState:
    """World time state.

    Attributes:
        time_of_day: Time within the current day (0-24000).
        day: Current day number.
        is_day: Whether it is daytime (time_of_day in 0..13000).
        moon_phase: Current moon phase (0-7).
        age: World age in ticks.
        do_daylight_cycle: Whether the daylight cycle is active.
    """

    time_of_day: int
    day: int
    is_day: bool
    moon_phase: int
    age: int
    do_daylight_cycle: bool
