"""Opaque recipe handle returned by mineflayer recipe queries."""

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class Recipe:
    """A typed handle to a mineflayer recipe.

    This model intentionally exposes no raw JSPyBridge types. Treat it
    as an opaque capability token returned by ``Bot.recipes_for()`` or
    ``Bot.recipes_all()`` and pass it back into ``Bot.craft()``.
    """

    _raw: object = field(repr=False, compare=False, hash=False)
