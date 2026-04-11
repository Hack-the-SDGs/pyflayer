"""Dashboard terminal UI API.

.. warning:: **Experimental.** ``@ssmidge/mineflayer-dashboard`` was
   developed against mineflayer ^2.28.1 (current: 4.37.0) and uses
   blessed terminal UI which may conflict with Python's stdout/stderr.

Ref: @ssmidge/mineflayer-dashboard/index.js — ``bot.dashboard``
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from minethon._bridge.plugins.dashboard import DashboardBridge


class DashboardAPI:
    """Dashboard terminal UI.

    Provides access to the blessed-based dashboard log and mode
    management.

    Example::

        await bot.plugins.load("@ssmidge/mineflayer-dashboard")
        bot.dashboard.log("Hello from minethon!")

    .. warning:: **Experimental.** The dashboard uses blessed terminal
       UI which may conflict with Python's stdout/stderr.

    Ref: @ssmidge/mineflayer-dashboard/index.js — ``bot.dashboard``
    """

    def __init__(self, bridge: DashboardBridge) -> None:
        self._bridge = bridge

    def log(self, *messages: str) -> None:
        """Write messages to the dashboard log box.

        Args:
            *messages: Strings to write to the dashboard log.

        Raises:
            BridgeError: If the plugin is not loaded.

        Ref: @ssmidge/mineflayer-dashboard/index.js — ``bot.dashboard.log()``
        """
        self._bridge.log(*messages)
