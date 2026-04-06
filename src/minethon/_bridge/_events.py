"""Internal bridge events for async JS operations.

These are private to the bridge layer — never import from public API.
Each event signals completion of a non-blocking JS action started by
the helpers in ``_bridge/js/helpers.js``.
"""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DigDoneEvent:
    """Dig operation finished (success if error is None)."""

    error: str | None = None


@dataclass(frozen=True, slots=True)
class PlaceDoneEvent:
    """Place operation finished."""

    error: str | None = None


@dataclass(frozen=True, slots=True)
class EquipDoneEvent:
    """Equip operation finished."""

    error: str | None = None


@dataclass(frozen=True, slots=True)
class LookAtDoneEvent:
    """LookAt operation finished."""

    error: str | None = None
