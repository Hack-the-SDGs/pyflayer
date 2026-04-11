"""Unit tests for ArmorManagerBridge and ArmorAPI."""

import asyncio
from unittest.mock import MagicMock

import pytest

from minethon._bridge._events import ArmorEquipDoneEvent
from minethon._bridge.plugins.armor_manager import ArmorManagerBridge
from minethon.api.armor import ArmorAPI
from minethon.models.errors import BridgeError

# ---------------------------------------------------------------------------
# ArmorManagerBridge tests
# ---------------------------------------------------------------------------


def _make_bridge() -> tuple[ArmorManagerBridge, MagicMock, MagicMock]:
    """Create an unloaded ArmorManagerBridge with mocked dependencies."""
    runtime = MagicMock()
    js_bot = MagicMock()
    relay = MagicMock()
    armor_mod = MagicMock()
    helpers = MagicMock()
    # First require returns the armor-manager module,
    # second returns the helpers module.
    runtime.require.side_effect = [armor_mod, helpers]
    bridge = ArmorManagerBridge(runtime, js_bot, relay)
    return bridge, js_bot, runtime


def _loaded_bridge() -> tuple[ArmorManagerBridge, MagicMock, MagicMock]:
    """Create a loaded ArmorManagerBridge."""
    bridge, js_bot, runtime = _make_bridge()
    bridge.load()
    return bridge, js_bot, runtime


class TestArmorManagerBridgeLoad:
    """ArmorManagerBridge loading and idempotency."""

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
        bridge = ArmorManagerBridge(runtime, js_bot, relay)
        with pytest.raises(BridgeError, match="load armor-manager"):
            bridge.load()
        assert bridge.is_loaded is False


class TestArmorManagerBridgeEquipAll:
    """start_equip_all bridge method."""

    def test_start_equip_all_calls_helpers(self) -> None:
        bridge, _bot, _rt = _loaded_bridge()
        bridge.start_equip_all()
        bridge._helpers.startArmorEquipAll.assert_called_once()

    def test_start_equip_all_not_loaded_raises(self) -> None:
        runtime = MagicMock()
        js_bot = MagicMock()
        relay = MagicMock()
        bridge = ArmorManagerBridge(runtime, js_bot, relay)
        with pytest.raises(BridgeError, match="armor-manager has not been loaded"):
            bridge.start_equip_all()

    def test_start_equip_all_js_error_raises(self) -> None:
        bridge, _bot, _rt = _loaded_bridge()
        bridge._helpers.startArmorEquipAll.side_effect = Exception("boom")
        with pytest.raises(BridgeError, match="start_equip_all"):
            bridge.start_equip_all()


class TestArmorManagerBridgeTeardown:
    """Teardown is a no-op (armor-manager has no cleanup)."""

    def test_teardown_is_noop(self) -> None:
        bridge, _bot, _rt = _loaded_bridge()
        bridge.teardown()  # should not raise


# ---------------------------------------------------------------------------
# ArmorEquipDoneEvent tests
# ---------------------------------------------------------------------------


class TestArmorEquipDoneEvent:
    """ArmorEquipDoneEvent dataclass."""

    def test_success_event(self) -> None:
        event = ArmorEquipDoneEvent()
        assert event.error is None

    def test_error_event(self) -> None:
        event = ArmorEquipDoneEvent(error="something went wrong")
        assert event.error == "something went wrong"

    def test_frozen(self) -> None:
        event = ArmorEquipDoneEvent()
        with pytest.raises(AttributeError):
            event.error = "fail"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# ArmorAPI tests
# ---------------------------------------------------------------------------


class TestArmorAPI:
    """ArmorAPI async methods."""

    @pytest.mark.asyncio
    async def test_equip_best_success(self) -> None:
        bridge = MagicMock(spec=ArmorManagerBridge)
        relay = MagicMock()
        success_event = ArmorEquipDoneEvent(error=None)

        async def _wait_for(*_a: object, **_kw: object) -> ArmorEquipDoneEvent:
            return success_event

        relay.wait_for = _wait_for
        api = ArmorAPI(bridge, relay)
        await api.equip_best()
        bridge.start_equip_all.assert_called_once()

    @pytest.mark.asyncio
    async def test_equip_best_error_raises(self) -> None:
        bridge = MagicMock(spec=ArmorManagerBridge)
        relay = MagicMock()
        error_event = ArmorEquipDoneEvent(error="no armor found")

        async def _wait_for(*_a: object, **_kw: object) -> ArmorEquipDoneEvent:
            return error_event

        relay.wait_for = _wait_for
        api = ArmorAPI(bridge, relay)
        with pytest.raises(BridgeError, match="armor equip failed"):
            await api.equip_best()

    @pytest.mark.asyncio
    async def test_equip_best_timeout_raises(self) -> None:
        bridge = MagicMock(spec=ArmorManagerBridge)
        relay = MagicMock()

        async def _timeout(*_args: object, **_kwargs: object) -> None:
            raise TimeoutError("timed out")

        relay.wait_for = _timeout
        api = ArmorAPI(bridge, relay)
        with pytest.raises(BridgeError, match="armor equip timed out"):
            await api.equip_best()

    @pytest.mark.asyncio
    async def test_equip_best_serialized_by_lock(self) -> None:
        """Concurrent equip_best calls are serialized by the lock."""
        bridge = MagicMock(spec=ArmorManagerBridge)
        relay = MagicMock()
        call_count = 0

        async def _mock_wait_for(
            *_args: object, **_kwargs: object
        ) -> ArmorEquipDoneEvent:
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.01)
            return ArmorEquipDoneEvent(error=None)

        relay.wait_for = _mock_wait_for
        api = ArmorAPI(bridge, relay)
        await asyncio.gather(api.equip_best(), api.equip_best())
        assert bridge.start_equip_all.call_count == 2
