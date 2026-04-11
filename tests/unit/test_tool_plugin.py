"""Unit tests for ToolBridge and ToolAPI using mocked JS runtime."""

import asyncio
from unittest.mock import MagicMock

import pytest

from minethon._bridge._events import ToolEquipDoneEvent
from minethon._bridge.plugins.tool_plugin import ToolBridge
from minethon.api.tool import ToolAPI
from minethon.models.block import Block
from minethon.models.errors import BridgeError
from minethon.models.vec3 import Vec3

# ---------------------------------------------------------------------------
# ToolBridge helpers
# ---------------------------------------------------------------------------


def _make_bridge() -> tuple[ToolBridge, MagicMock, MagicMock, MagicMock, MagicMock]:
    """Create an unloaded ToolBridge with mocked dependencies."""
    runtime = MagicMock()
    js_bot = MagicMock()
    relay = MagicMock()
    controller = MagicMock()
    tool_mod = MagicMock()
    runtime.require.return_value = tool_mod
    bridge = ToolBridge(runtime, js_bot, relay, controller)
    return bridge, js_bot, tool_mod, controller, runtime


def _loaded_bridge() -> tuple[ToolBridge, MagicMock, MagicMock, MagicMock]:
    """Create a loaded ToolBridge with mocked dependencies."""
    bridge, js_bot, tool_mod, controller, _rt = _make_bridge()
    bridge.load()
    return bridge, js_bot, tool_mod, controller


# ---------------------------------------------------------------------------
# ToolBridge tests
# ---------------------------------------------------------------------------


class TestToolBridgeLoad:
    """ToolBridge loading and idempotency."""

    def test_load(self) -> None:
        bridge, js_bot, tool_mod, _ctrl, _rt = _make_bridge()
        bridge.load()
        js_bot.loadPlugin.assert_called_once_with(tool_mod.plugin)
        assert bridge.is_loaded is True

    def test_load_idempotent(self) -> None:
        bridge, js_bot, _mod, _ctrl, _rt = _make_bridge()
        bridge.load()
        bridge.load()
        js_bot.loadPlugin.assert_called_once()

    def test_load_js_error_raises_bridge_error(self) -> None:
        runtime = MagicMock()
        js_bot = MagicMock()
        relay = MagicMock()
        controller = MagicMock()
        runtime.require.side_effect = Exception("npm install failed")
        bridge = ToolBridge(runtime, js_bot, relay, controller)
        with pytest.raises(BridgeError, match="load tool"):
            bridge.load()
        assert bridge.is_loaded is False

    def test_npm_name(self) -> None:
        assert ToolBridge.NPM_NAME == "mineflayer-tool"

    def test_no_depends_on(self) -> None:
        assert ToolBridge.DEPENDS_ON == ()


class TestToolBridgeEquipForBlock:
    """start_equip_for_block — block lookup + helpers call."""

    def test_equip_for_block_success(self) -> None:
        bridge, _bot, _mod, ctrl = _loaded_bridge()
        js_block = MagicMock()
        ctrl.block_at.return_value = js_block
        bridge.start_equip_for_block((10, 64, 20))
        ctrl.block_at.assert_called_once_with(10, 64, 20)
        ctrl.start_tool_equip_for_block.assert_called_once_with(
            js_block,
            require_harvest=False,
        )

    def test_equip_for_block_with_require_harvest(self) -> None:
        bridge, _bot, _mod, ctrl = _loaded_bridge()
        js_block = MagicMock()
        ctrl.block_at.return_value = js_block
        bridge.start_equip_for_block((5, 32, 10), require_harvest=True)
        ctrl.start_tool_equip_for_block.assert_called_once_with(
            js_block,
            require_harvest=True,
        )

    def test_equip_for_block_default_no_harvest(self) -> None:
        bridge, _bot, _mod, ctrl = _loaded_bridge()
        js_block = MagicMock()
        ctrl.block_at.return_value = js_block
        bridge.start_equip_for_block((5, 32, 10))
        ctrl.start_tool_equip_for_block.assert_called_once_with(
            js_block,
            require_harvest=False,
        )

    def test_equip_for_block_not_loaded_raises(self) -> None:
        bridge, _bot, _mod, _ctrl, _rt = _make_bridge()
        with pytest.raises(BridgeError, match="tool plugin has not been loaded"):
            bridge.start_equip_for_block((0, 0, 0))

    def test_equip_for_block_no_block_raises(self) -> None:
        bridge, _bot, _mod, ctrl = _loaded_bridge()
        ctrl.block_at.return_value = None
        with pytest.raises(BridgeError, match="no block at"):
            bridge.start_equip_for_block((999, 999, 999))

    def test_equip_for_block_js_error_raises(self) -> None:
        bridge, _bot, _mod, ctrl = _loaded_bridge()
        js_block = MagicMock()
        ctrl.block_at.return_value = js_block
        ctrl.start_tool_equip_for_block.side_effect = BridgeError("JS boom")
        with pytest.raises(BridgeError, match="JS boom"):
            bridge.start_equip_for_block((0, 64, 0))


# ---------------------------------------------------------------------------
# ToolAPI tests
# ---------------------------------------------------------------------------

_SAMPLE_BLOCK = Block(
    name="stone",
    display_name="Stone",
    position=Vec3(10.0, 64.0, 20.0),
    hardness=1.5,
    is_solid=True,
    is_liquid=False,
    bounding_box="block",
)


class TestToolAPI:
    """ToolAPI.equip_for_block — async wrapper over bridge."""

    @pytest.mark.asyncio
    async def test_equip_for_block_success(self) -> None:
        bridge = MagicMock(spec=ToolBridge)
        relay = MagicMock()
        api = ToolAPI(bridge, relay)

        done_event = ToolEquipDoneEvent(error=None)
        fut: asyncio.Future[ToolEquipDoneEvent] = (
            asyncio.get_running_loop().create_future()
        )
        fut.set_result(done_event)
        relay.wait_for.return_value = fut

        await api.equip_for_block(_SAMPLE_BLOCK)

        bridge.start_equip_for_block.assert_called_once_with(
            (10, 64, 20),
            require_harvest=False,
        )
        relay.wait_for.assert_called_once()

    @pytest.mark.asyncio
    async def test_equip_for_block_with_require_harvest(self) -> None:
        bridge = MagicMock(spec=ToolBridge)
        relay = MagicMock()
        api = ToolAPI(bridge, relay)

        done_event = ToolEquipDoneEvent(error=None)
        fut: asyncio.Future[ToolEquipDoneEvent] = (
            asyncio.get_running_loop().create_future()
        )
        fut.set_result(done_event)
        relay.wait_for.return_value = fut

        await api.equip_for_block(_SAMPLE_BLOCK, require_harvest=True)

        bridge.start_equip_for_block.assert_called_once_with(
            (10, 64, 20),
            require_harvest=True,
        )

    @pytest.mark.asyncio
    async def test_equip_for_block_error_raises(self) -> None:
        bridge = MagicMock(spec=ToolBridge)
        relay = MagicMock()
        api = ToolAPI(bridge, relay)

        done_event = ToolEquipDoneEvent(error="no suitable tool")
        fut: asyncio.Future[ToolEquipDoneEvent] = (
            asyncio.get_running_loop().create_future()
        )
        fut.set_result(done_event)
        relay.wait_for.return_value = fut

        with pytest.raises(BridgeError, match="equip_for_block failed"):
            await api.equip_for_block(_SAMPLE_BLOCK)

    @pytest.mark.asyncio
    async def test_equip_for_block_converts_position_to_int(self) -> None:
        """Block positions with float coords are truncated to int."""
        bridge = MagicMock(spec=ToolBridge)
        relay = MagicMock()
        api = ToolAPI(bridge, relay)

        done_event = ToolEquipDoneEvent(error=None)
        fut: asyncio.Future[ToolEquipDoneEvent] = (
            asyncio.get_running_loop().create_future()
        )
        fut.set_result(done_event)
        relay.wait_for.return_value = fut

        block = Block(
            name="dirt",
            display_name="Dirt",
            position=Vec3(10.5, 64.9, 20.1),
            hardness=0.5,
            is_solid=True,
            is_liquid=False,
            bounding_box="block",
        )
        await api.equip_for_block(block)

        bridge.start_equip_for_block.assert_called_once_with(
            (10, 64, 20),
            require_harvest=False,
        )


# ---------------------------------------------------------------------------
# ToolEquipDoneEvent tests
# ---------------------------------------------------------------------------


class TestToolEquipDoneEvent:
    """ToolEquipDoneEvent dataclass."""

    def test_success_event(self) -> None:
        event = ToolEquipDoneEvent()
        assert event.error is None

    def test_error_event(self) -> None:
        event = ToolEquipDoneEvent(error="something went wrong")
        assert event.error == "something went wrong"

    def test_frozen(self) -> None:
        event = ToolEquipDoneEvent()
        with pytest.raises(AttributeError):
            event.error = "nope"  # type: ignore[misc]
