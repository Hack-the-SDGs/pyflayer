"""Importable public type shells for annotations and IDE completion."""

from __future__ import annotations

from minethon import _type_shells
from minethon._events import BotEvent as BotEvent
from minethon.errors import (
    MinethonError as MinethonError,
)
from minethon.errors import (
    NotSpawnedError as NotSpawnedError,
)
from minethon.errors import (
    PlayerNotFoundError as PlayerNotFoundError,
)
from minethon.errors import (
    PluginNotInstalledError as PluginNotInstalledError,
)
from minethon.errors import (
    VersionPinRequiredError as VersionPinRequiredError,
)

globals().update(
    {name: getattr(_type_shells, name) for name in _type_shells.TYPE_SHELL_NAMES}
)
