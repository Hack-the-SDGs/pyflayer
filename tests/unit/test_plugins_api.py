"""Unit tests for the public PluginAPI."""

from unittest.mock import MagicMock

import pytest

from minethon.api.plugins import PluginAPI
from minethon.models.errors import PluginError


class TestPluginAPI:
    @pytest.mark.asyncio
    async def test_load_pathfinder(self) -> None:
        host = MagicMock()
        api = PluginAPI(host)

        await api.load("mineflayer-pathfinder")

        host.load_pathfinder.assert_called_once_with()

    @pytest.mark.asyncio
    async def test_load_unknown_plugin_raises(self) -> None:
        host = MagicMock()
        api = PluginAPI(host)

        with pytest.raises(PluginError, match="Unsupported plugin"):
            await api.load("mineflayer-web-inventory")

    def test_is_loaded_returns_host_state_for_supported_plugin(self) -> None:
        host = MagicMock()
        host.is_pathfinder_loaded.return_value = True
        api = PluginAPI(host)

        assert api.is_loaded("mineflayer-pathfinder") is True

    def test_is_loaded_returns_false_for_unknown_plugin(self) -> None:
        host = MagicMock()
        api = PluginAPI(host)

        assert api.is_loaded("mineflayer-web-inventory") is False
