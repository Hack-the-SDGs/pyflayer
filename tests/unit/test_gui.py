"""Unit tests for the GUI plugin (mineflayer-gui) bridge and API."""

from unittest.mock import MagicMock

import pytest

from minethon._bridge._events import GuiDropDoneEvent, GuiQueryDoneEvent
from minethon._bridge.plugins.gui import GuiBridge
from minethon.api.gui import GuiAPI
from minethon.models.errors import BridgeError

# ---------------------------------------------------------------------------
# Event dataclass tests
# ---------------------------------------------------------------------------


class TestGuiQueryDoneEvent:
    def test_success(self) -> None:
        event = GuiQueryDoneEvent(result=True)
        assert event.error is None
        assert event.result is True

    def test_failure(self) -> None:
        event = GuiQueryDoneEvent(error="item not found")
        assert event.error == "item not found"
        assert event.result is False

    def test_defaults(self) -> None:
        event = GuiQueryDoneEvent()
        assert event.error is None
        assert event.result is False

    def test_frozen(self) -> None:
        event = GuiQueryDoneEvent()
        with pytest.raises(AttributeError):
            event.error = "x"  # type: ignore[misc]


class TestGuiDropDoneEvent:
    def test_success(self) -> None:
        event = GuiDropDoneEvent(result=True)
        assert event.error is None
        assert event.result is True

    def test_failure(self) -> None:
        event = GuiDropDoneEvent(error="cannot drop")
        assert event.error == "cannot drop"
        assert event.result is False

    def test_defaults(self) -> None:
        event = GuiDropDoneEvent()
        assert event.error is None
        assert event.result is False

    def test_frozen(self) -> None:
        event = GuiDropDoneEvent()
        with pytest.raises(AttributeError):
            event.result = True  # type: ignore[misc]


# ---------------------------------------------------------------------------
# GuiBridge tests
# ---------------------------------------------------------------------------


def _make_bridge() -> tuple[GuiBridge, MagicMock, MagicMock]:
    """Create an unloaded GuiBridge with mocked dependencies."""
    runtime = MagicMock()
    js_bot = MagicMock()
    relay = MagicMock()
    gui_mod = MagicMock()
    helpers = MagicMock()
    # First require: gui module, second: helpers.js
    runtime.require.side_effect = [gui_mod, helpers]
    bridge = GuiBridge(runtime, js_bot, relay)
    return bridge, js_bot, runtime


def _loaded_bridge() -> tuple[GuiBridge, MagicMock, MagicMock]:
    """Create a loaded GuiBridge."""
    bridge, js_bot, runtime = _make_bridge()
    bridge.load()
    return bridge, js_bot, runtime


class TestGuiBridgeLoad:
    """GuiBridge loading and idempotency."""

    def test_load(self) -> None:
        bridge, js_bot, _rt = _make_bridge()
        bridge.load()
        js_bot.loadPlugin.assert_called_once()
        assert bridge.is_loaded is True

    def test_load_idempotent(self) -> None:
        bridge, js_bot, _rt = _make_bridge()
        bridge.load()
        bridge.load()
        js_bot.loadPlugin.assert_called_once()

    def test_load_js_error_raises_bridge_error(self) -> None:
        runtime = MagicMock()
        js_bot = MagicMock()
        relay = MagicMock()
        runtime.require.side_effect = Exception("npm install failed")
        bridge = GuiBridge(runtime, js_bot, relay)
        with pytest.raises(BridgeError, match="load gui"):
            bridge.load()
        assert bridge.is_loaded is False


class TestGuiBridgeClickByName:
    """start_click_by_name bridge method."""

    def test_calls_helpers(self) -> None:
        bridge, js_bot, _rt = _loaded_bridge()
        bridge.start_click_by_name("diamond_sword", window=True)
        bridge._helpers.guiClickByName.assert_called_once_with(
            js_bot, "diamond_sword", True
        )

    def test_default_window_false(self) -> None:
        bridge, js_bot, _rt = _loaded_bridge()
        bridge.start_click_by_name("iron_pickaxe")
        bridge._helpers.guiClickByName.assert_called_once_with(
            js_bot, "iron_pickaxe", False
        )

    def test_not_loaded_raises(self) -> None:
        runtime = MagicMock()
        js_bot = MagicMock()
        relay = MagicMock()
        bridge = GuiBridge(runtime, js_bot, relay)
        with pytest.raises(BridgeError, match="gui has not been loaded"):
            bridge.start_click_by_name("diamond_sword")

    def test_js_error_raises(self) -> None:
        bridge, _bot, _rt = _loaded_bridge()
        bridge._helpers.guiClickByName.side_effect = Exception("boom")
        with pytest.raises(BridgeError, match="start_click_by_name"):
            bridge.start_click_by_name("diamond_sword")


class TestGuiBridgeDropByName:
    """start_drop_by_name bridge method."""

    def test_calls_helpers(self) -> None:
        bridge, js_bot, _rt = _loaded_bridge()
        bridge.start_drop_by_name("cobblestone", 32)
        bridge._helpers.guiDropByName.assert_called_once_with(js_bot, "cobblestone", 32)

    def test_not_loaded_raises(self) -> None:
        runtime = MagicMock()
        js_bot = MagicMock()
        relay = MagicMock()
        bridge = GuiBridge(runtime, js_bot, relay)
        with pytest.raises(BridgeError, match="gui has not been loaded"):
            bridge.start_drop_by_name("cobblestone", 1)

    def test_js_error_raises(self) -> None:
        bridge, _bot, _rt = _loaded_bridge()
        bridge._helpers.guiDropByName.side_effect = Exception("err")
        with pytest.raises(BridgeError, match="start_drop_by_name"):
            bridge.start_drop_by_name("cobblestone", 1)


class TestGuiBridgeCreateQuery:
    """create_query escape hatch."""

    def test_returns_query(self) -> None:
        bridge, js_bot, _rt = _loaded_bridge()
        query = MagicMock()
        js_bot.gui.Query.return_value = query
        result = bridge.create_query()
        assert result is query
        js_bot.gui.Query.assert_called_once()

    def test_not_loaded_raises(self) -> None:
        runtime = MagicMock()
        js_bot = MagicMock()
        relay = MagicMock()
        bridge = GuiBridge(runtime, js_bot, relay)
        with pytest.raises(BridgeError, match="gui has not been loaded"):
            bridge.create_query()

    def test_js_error_raises(self) -> None:
        bridge, js_bot, _rt = _loaded_bridge()
        js_bot.gui.Query.side_effect = Exception("failed")
        with pytest.raises(BridgeError, match="create_query"):
            bridge.create_query()


class TestGuiBridgeTeardown:
    """Teardown is a no-op (gui has no cleanup)."""

    def test_teardown_is_noop(self) -> None:
        bridge, _bot, _rt = _loaded_bridge()
        bridge.teardown()  # should not raise


# ---------------------------------------------------------------------------
# GuiAPI tests
# ---------------------------------------------------------------------------


class TestGuiAPI:
    """Public GuiAPI tests."""

    @pytest.mark.asyncio
    async def test_click_item_success(self) -> None:
        bridge = MagicMock(spec=GuiBridge)
        relay = MagicMock()
        success_event = GuiQueryDoneEvent(result=True)

        async def _wait_for(*_a: object, **_kw: object) -> GuiQueryDoneEvent:
            return success_event

        relay.wait_for = _wait_for
        api = GuiAPI(bridge, relay)
        result = await api.click_item("diamond_sword")
        assert result is True
        bridge.start_click_by_name.assert_called_once_with(
            "diamond_sword", window=False
        )

    @pytest.mark.asyncio
    async def test_click_item_with_window(self) -> None:
        bridge = MagicMock(spec=GuiBridge)
        relay = MagicMock()

        async def _wait_for(*_a: object, **_kw: object) -> GuiQueryDoneEvent:
            return GuiQueryDoneEvent(result=True)

        relay.wait_for = _wait_for
        api = GuiAPI(bridge, relay)
        await api.click_item("diamond_sword", window=True)
        bridge.start_click_by_name.assert_called_once_with("diamond_sword", window=True)

    @pytest.mark.asyncio
    async def test_click_item_error_raises(self) -> None:
        bridge = MagicMock(spec=GuiBridge)
        relay = MagicMock()

        async def _wait_for(*_a: object, **_kw: object) -> GuiQueryDoneEvent:
            return GuiQueryDoneEvent(error="not found")

        relay.wait_for = _wait_for
        api = GuiAPI(bridge, relay)
        with pytest.raises(BridgeError, match="click_item failed"):
            await api.click_item("missing_item")

    @pytest.mark.asyncio
    async def test_click_item_not_found_returns_false(self) -> None:
        bridge = MagicMock(spec=GuiBridge)
        relay = MagicMock()

        async def _wait_for(*_a: object, **_kw: object) -> GuiQueryDoneEvent:
            return GuiQueryDoneEvent(result=False)

        relay.wait_for = _wait_for
        api = GuiAPI(bridge, relay)
        result = await api.click_item("diamond_sword")
        assert result is False

    @pytest.mark.asyncio
    async def test_drop_item_success(self) -> None:
        bridge = MagicMock(spec=GuiBridge)
        relay = MagicMock()
        success_event = GuiDropDoneEvent(result=True)

        async def _wait_for(*_a: object, **_kw: object) -> GuiDropDoneEvent:
            return success_event

        relay.wait_for = _wait_for
        api = GuiAPI(bridge, relay)
        result = await api.drop_item("cobblestone", count=32)
        assert result is True
        bridge.start_drop_by_name.assert_called_once_with("cobblestone", 32)

    @pytest.mark.asyncio
    async def test_drop_item_error_raises(self) -> None:
        bridge = MagicMock(spec=GuiBridge)
        relay = MagicMock()

        async def _wait_for(*_a: object, **_kw: object) -> GuiDropDoneEvent:
            return GuiDropDoneEvent(error="cannot drop")

        relay.wait_for = _wait_for
        api = GuiAPI(bridge, relay)
        with pytest.raises(BridgeError, match="drop_item failed"):
            await api.drop_item("cobblestone")

    def test_raw_query_delegates_to_bridge(self) -> None:
        bridge = MagicMock(spec=GuiBridge)
        relay = MagicMock()
        query = MagicMock()
        bridge.create_query.return_value = query
        api = GuiAPI(bridge, relay)
        result = api.raw_query()
        assert result is query
        bridge.create_query.assert_called_once()


# ---------------------------------------------------------------------------
# PluginRegistry registration tests
# ---------------------------------------------------------------------------


class TestPluginRegistryGuiRegistration:
    """Verify GUI plugin is properly registered in PluginRegistry."""

    def test_gui_in_supported(self) -> None:
        from minethon._bridge.plugin_registry import PluginRegistry

        runtime = MagicMock()
        js_bot = MagicMock()
        relay = MagicMock()
        runtime.require.return_value = MagicMock()
        registry = PluginRegistry(runtime, js_bot, relay, MagicMock())
        assert "mineflayer-gui" in registry.supported

    def test_get_gui_returns_bridge(self) -> None:
        from minethon._bridge.plugin_registry import PluginRegistry

        runtime = MagicMock()
        js_bot = MagicMock()
        relay = MagicMock()
        runtime.require.return_value = MagicMock()
        registry = PluginRegistry(runtime, js_bot, relay, MagicMock())
        bridge = registry.get_gui()
        assert isinstance(bridge, GuiBridge)

    def test_load_gui(self) -> None:
        from minethon._bridge.plugin_registry import PluginRegistry

        runtime = MagicMock()
        js_bot = MagicMock()
        relay = MagicMock()
        runtime.require.return_value = MagicMock()
        registry = PluginRegistry(runtime, js_bot, relay, MagicMock())
        registry.load("mineflayer-gui")
        assert registry.is_loaded("mineflayer-gui") is True
