"""Typed window and villager session handles.

Pure Python domain models — no JSPyBridge dependency.  The live JS
proxy is held in ``Bot._window_registry`` (keyed by ``id``), not here.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from minethon.models.item import ItemStack


@dataclass(frozen=True, slots=True)
class WindowHandle:
    """A typed handle to an opened mineflayer window.

    The underlying JS proxy is managed by ``Bot._window_registry``.
    Use :meth:`Bot.close_window` to release it.
    """

    id: int
    title: str
    kind: str


@dataclass(frozen=True, slots=True)
class TradeOffer:
    """A villager trade offer snapshot."""

    first_input: ItemStack
    output: ItemStack
    secondary_input: ItemStack | None
    disabled: bool
    uses: int
    max_uses: int


@dataclass(frozen=True, slots=True)
class VillagerSession:
    """A typed villager trading session handle.

    The underlying JS proxy is managed by ``Bot._window_registry``.
    Use :meth:`Bot.close_window` to release it.
    """

    id: int
    title: str
    trades: tuple[TradeOffer, ...]
