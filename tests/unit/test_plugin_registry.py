"""Unit tests for PluginRegistry."""

from unittest.mock import MagicMock

import pytest

from minethon._bridge.plugin_registry import PluginRegistry
from minethon._bridge.plugins.pathfinder import PathfinderBridge
from minethon.models.errors import BridgeError, PluginError


class TestPluginRegistryBasics:
    """Registration, supported list, load, is_loaded."""

    def _make_registry(self) -> tuple[PluginRegistry, MagicMock, MagicMock]:
        runtime = MagicMock()
        js_bot = MagicMock()
        relay = MagicMock()
        pf_mod = MagicMock()
        runtime.require.return_value = pf_mod
        registry = PluginRegistry(runtime, js_bot, relay)
        return registry, runtime, js_bot

    def test_supported_includes_pathfinder(self) -> None:
        registry, _rt, _bot = self._make_registry()
        assert "mineflayer-pathfinder" in registry.supported

    def test_load_pathfinder(self) -> None:
        registry, _rt, js_bot = self._make_registry()
        registry.load("mineflayer-pathfinder")
        assert registry.is_loaded("mineflayer-pathfinder") is True
        js_bot.loadPlugin.assert_called_once()

    def test_load_unknown_raises_plugin_error(self) -> None:
        registry, _rt, _bot = self._make_registry()
        with pytest.raises(PluginError, match="Unsupported plugin"):
            registry.load("mineflayer-nonexistent")

    def test_is_loaded_false_for_unknown(self) -> None:
        registry, _rt, _bot = self._make_registry()
        assert registry.is_loaded("mineflayer-nonexistent") is False

    def test_is_loaded_false_before_load(self) -> None:
        registry, _rt, _bot = self._make_registry()
        assert registry.is_loaded("mineflayer-pathfinder") is False

    def test_load_idempotent(self) -> None:
        registry, _rt, js_bot = self._make_registry()
        registry.load("mineflayer-pathfinder")
        registry.load("mineflayer-pathfinder")
        js_bot.loadPlugin.assert_called_once()


class TestPluginRegistryGetPathfinder:
    """get_pathfinder convenience."""

    def test_returns_pathfinder_bridge(self) -> None:
        runtime = MagicMock()
        js_bot = MagicMock()
        relay = MagicMock()
        runtime.require.return_value = MagicMock()
        registry = PluginRegistry(runtime, js_bot, relay)
        pf = registry.get_pathfinder()
        assert isinstance(pf, PathfinderBridge)

    def test_get_returns_bridge(self) -> None:
        runtime = MagicMock()
        js_bot = MagicMock()
        relay = MagicMock()
        runtime.require.return_value = MagicMock()
        registry = PluginRegistry(runtime, js_bot, relay)
        bridge = registry.get("mineflayer-pathfinder")
        assert isinstance(bridge, PathfinderBridge)

    def test_get_unknown_returns_none(self) -> None:
        runtime = MagicMock()
        js_bot = MagicMock()
        relay = MagicMock()
        runtime.require.return_value = MagicMock()
        registry = PluginRegistry(runtime, js_bot, relay)
        assert registry.get("nonexistent") is None


class TestPluginRegistryTeardown:
    """teardown_all best-effort cleanup."""

    def test_teardown_all_calls_loaded_bridges(self) -> None:
        runtime = MagicMock()
        js_bot = MagicMock()
        relay = MagicMock()
        runtime.require.return_value = MagicMock()
        registry = PluginRegistry(runtime, js_bot, relay)
        registry.load("mineflayer-pathfinder")
        registry.teardown_all()
        # pathfinder.stop() sets goal to None
        js_bot.pathfinder.setGoal.assert_called_with(None)

    def test_teardown_all_skips_unloaded(self) -> None:
        runtime = MagicMock()
        js_bot = MagicMock()
        relay = MagicMock()
        runtime.require.return_value = MagicMock()
        registry = PluginRegistry(runtime, js_bot, relay)
        # not loaded — should not raise
        registry.teardown_all()
        js_bot.pathfinder.setGoal.assert_not_called()

    def test_teardown_all_swallows_exceptions(self) -> None:
        runtime = MagicMock()
        js_bot = MagicMock()
        relay = MagicMock()
        runtime.require.return_value = MagicMock()
        registry = PluginRegistry(runtime, js_bot, relay)
        registry.load("mineflayer-pathfinder")
        js_bot.pathfinder.setGoal.side_effect = RuntimeError("boom")
        # should not raise
        registry.teardown_all()


class TestPluginRegistryRawRequire:
    """raw_require escape hatch."""

    def test_raw_require_returns_module(self) -> None:
        runtime = MagicMock()
        js_bot = MagicMock()
        relay = MagicMock()
        fake_mod = MagicMock()
        runtime.require.return_value = fake_mod
        registry = PluginRegistry(runtime, js_bot, relay)
        result = registry.raw_require("some-npm-package")
        runtime.require.assert_called_with("some-npm-package")
        assert result is fake_mod

    def test_raw_require_error_raises_bridge_error(self) -> None:
        runtime = MagicMock()
        js_bot = MagicMock()
        relay = MagicMock()
        runtime.require.side_effect = Exception("npm error")
        registry = PluginRegistry(runtime, js_bot, relay)
        with pytest.raises(BridgeError, match="raw_require"):
            registry.raw_require("bad-package")
