"""Unit tests for DashboardBridge and DashboardAPI."""

from unittest.mock import MagicMock

import pytest

from minethon._bridge.plugins.dashboard import DashboardBridge
from minethon.api.dashboard import DashboardAPI
from minethon.models.errors import BridgeError

# ---------------------------------------------------------------------------
# DashboardBridge tests
# ---------------------------------------------------------------------------


def _make_bridge() -> tuple[DashboardBridge, MagicMock, MagicMock]:
    """Create an unloaded DashboardBridge with mocked dependencies."""
    runtime = MagicMock()
    js_bot = MagicMock()
    relay = MagicMock()
    dashboard_mod = MagicMock()
    plugin_fn = MagicMock()
    dashboard_mod.return_value = plugin_fn  # HOF: mod(options) -> plugin_fn
    runtime.require.return_value = dashboard_mod
    bridge = DashboardBridge(runtime, js_bot, relay)
    return bridge, js_bot, runtime


def _loaded_bridge() -> tuple[DashboardBridge, MagicMock, MagicMock]:
    """Create a loaded DashboardBridge."""
    bridge, js_bot, runtime = _make_bridge()
    bridge.load()
    return bridge, js_bot, runtime


class TestDashboardBridgeLoad:
    """DashboardBridge loading and idempotency."""

    def test_load(self) -> None:
        bridge, js_bot, runtime = _make_bridge()
        bridge.load()
        # require called for the module
        runtime.require.assert_called_once_with("@ssmidge/mineflayer-dashboard")
        # HOF called with empty options
        mod = runtime.require.return_value
        mod.assert_called_once_with({})
        # loadPlugin called with the result of HOF
        js_bot.loadPlugin.assert_called_once_with(mod.return_value)
        assert bridge.is_loaded is True

    def test_load_idempotent(self) -> None:
        bridge, js_bot, _rt = _make_bridge()
        bridge.load()
        bridge.load()
        js_bot.loadPlugin.assert_called_once()

    def test_load_with_chat_pattern(self) -> None:
        bridge, _bot, runtime = _make_bridge()
        bridge.configure(chat_pattern="<.*>")
        bridge.load()
        mod = runtime.require.return_value
        mod.assert_called_once_with({"chatPattern": "<.*>"})

    def test_load_js_error_raises_bridge_error(self) -> None:
        runtime = MagicMock()
        js_bot = MagicMock()
        relay = MagicMock()
        runtime.require.side_effect = Exception("npm install failed")
        bridge = DashboardBridge(runtime, js_bot, relay)
        with pytest.raises(BridgeError, match="load dashboard"):
            bridge.load()
        assert bridge.is_loaded is False


class TestDashboardBridgeConfigure:
    """configure() sets options before load."""

    def test_configure_before_load(self) -> None:
        bridge, _bot, runtime = _make_bridge()
        bridge.configure(chat_pattern="test.*")
        bridge.load()
        mod = runtime.require.return_value
        mod.assert_called_once_with({"chatPattern": "test.*"})

    def test_configure_after_load_is_noop(self) -> None:
        bridge, _bot, _runtime = _make_bridge()
        bridge.load()
        bridge.configure(chat_pattern="ignored")
        # chat_pattern should still be None since configure was after load
        assert bridge._chat_pattern is None

    def test_configure_none_chat_pattern(self) -> None:
        bridge, _bot, runtime = _make_bridge()
        bridge.configure(chat_pattern=None)
        bridge.load()
        mod = runtime.require.return_value
        mod.assert_called_once_with({})


class TestDashboardBridgeLog:
    """log() bridge method."""

    def test_log_calls_js_dashboard(self) -> None:
        bridge, js_bot, _rt = _loaded_bridge()
        bridge.log("hello", "world")
        js_bot.dashboard.log.assert_called_once_with("hello", "world")

    def test_log_single_message(self) -> None:
        bridge, js_bot, _rt = _loaded_bridge()
        bridge.log("single message")
        js_bot.dashboard.log.assert_called_once_with("single message")

    def test_log_not_loaded_raises(self) -> None:
        bridge, _bot, _rt = _make_bridge()
        with pytest.raises(BridgeError, match="dashboard has not been loaded"):
            bridge.log("test")

    def test_log_js_error_raises(self) -> None:
        bridge, js_bot, _rt = _loaded_bridge()
        js_bot.dashboard.log.side_effect = Exception("blessed crash")
        with pytest.raises(BridgeError, match="dashboard log failed"):
            bridge.log("test")


class TestDashboardBridgeTeardown:
    """Teardown is a no-op (dashboard has no cleanup)."""

    def test_teardown_is_noop(self) -> None:
        bridge, _bot, _rt = _loaded_bridge()
        bridge.teardown()  # should not raise


# ---------------------------------------------------------------------------
# DashboardAPI tests
# ---------------------------------------------------------------------------


class TestDashboardAPI:
    """DashboardAPI sync methods."""

    def test_log_delegates_to_bridge(self) -> None:
        bridge = MagicMock(spec=DashboardBridge)
        api = DashboardAPI(bridge)
        api.log("hello", "world")
        bridge.log.assert_called_once_with("hello", "world")

    def test_log_single_message(self) -> None:
        bridge = MagicMock(spec=DashboardBridge)
        api = DashboardAPI(bridge)
        api.log("single")
        bridge.log.assert_called_once_with("single")

    def test_log_no_messages(self) -> None:
        bridge = MagicMock(spec=DashboardBridge)
        api = DashboardAPI(bridge)
        api.log()
        bridge.log.assert_called_once_with()

    def test_log_propagates_bridge_error(self) -> None:
        bridge = MagicMock(spec=DashboardBridge)
        bridge.log.side_effect = BridgeError("not loaded")
        api = DashboardAPI(bridge)
        with pytest.raises(BridgeError, match="not loaded"):
            api.log("test")
