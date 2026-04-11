"""Unit tests for the public PluginAPI."""

from unittest.mock import MagicMock

import pytest

from minethon.api.plugins import PluginAPI
from minethon.models.errors import PluginError


class TestPluginAPI:
    @pytest.mark.asyncio
    async def test_load_pathfinder(self) -> None:
        registry = MagicMock()
        registry.supported = ("mineflayer-pathfinder",)
        api = PluginAPI(registry)

        await api.load("mineflayer-pathfinder")

        registry.load.assert_called_once_with("mineflayer-pathfinder")

    @pytest.mark.asyncio
    async def test_load_unknown_plugin_raises(self) -> None:
        registry = MagicMock()
        registry.supported = ("mineflayer-pathfinder",)
        api = PluginAPI(registry)

        with pytest.raises(PluginError, match="Unsupported plugin"):
            await api.load("mineflayer-web-inventory")

    def test_is_loaded_returns_registry_state(self) -> None:
        registry = MagicMock()
        registry.is_loaded.return_value = True
        api = PluginAPI(registry)

        assert api.is_loaded("mineflayer-pathfinder") is True
        registry.is_loaded.assert_called_once_with("mineflayer-pathfinder")

    def test_is_loaded_returns_false_for_unknown(self) -> None:
        registry = MagicMock()
        registry.is_loaded.return_value = False
        api = PluginAPI(registry)

        assert api.is_loaded("mineflayer-nonexistent") is False

    def test_supported_delegates_to_registry(self) -> None:
        registry = MagicMock()
        registry.supported = ("mineflayer-pathfinder",)
        api = PluginAPI(registry)

        assert api.supported == ("mineflayer-pathfinder",)
