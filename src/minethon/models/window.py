"""Typed window and villager session handles."""

from dataclasses import dataclass, field

from minethon.models.item import ItemStack


@dataclass(frozen=True, slots=True)
class WindowHandle:
    """A typed handle to an opened mineflayer window.

    Warning:
        ``_raw`` is a live JSPyBridge proxy. It is only valid while the
        underlying window remains open. Accessing it after the window is
        closed may fail unpredictably or crash the Node.js bridge.
    """

    id: int
    title: str
    kind: str
    _raw: object = field(repr=False, compare=False, hash=False)


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

    Warning:
        ``_raw`` is a live JSPyBridge proxy. It is only valid while the
        villager trading window remains open. Accessing it after the
        session closes may fail unpredictably or crash the Node.js bridge.
    """

    id: int
    title: str
    trades: tuple[TradeOffer, ...]
    _raw: object = field(repr=False, compare=False, hash=False)
