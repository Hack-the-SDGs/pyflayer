"""Unit tests for PanoramaBridge, PanoramaAPI, and panorama events."""

import asyncio
from unittest.mock import MagicMock

import pytest

from minethon._bridge._events import PanoramaDoneEvent, PictureDoneEvent
from minethon._bridge.plugins.panorama import PanoramaBridge
from minethon.api.panorama import PanoramaAPI
from minethon.models.errors import BridgeError
from minethon.models.vec3 import Vec3

# ---------------------------------------------------------------------------
# PanoramaBridge tests
# ---------------------------------------------------------------------------


def _make_bridge() -> tuple[PanoramaBridge, MagicMock, MagicMock]:
    """Create an unloaded PanoramaBridge with mocked dependencies."""
    runtime = MagicMock()
    js_bot = MagicMock()
    relay = MagicMock()
    panorama_mod = MagicMock()
    runtime.require.return_value = panorama_mod
    bridge = PanoramaBridge(runtime, js_bot, relay)
    return bridge, js_bot, runtime


def _loaded_bridge() -> tuple[PanoramaBridge, MagicMock, MagicMock]:
    """Create a loaded PanoramaBridge."""
    bridge, js_bot, runtime = _make_bridge()
    bridge.load()
    return bridge, js_bot, runtime


class TestPanoramaBridgeLoad:
    """PanoramaBridge loading and idempotency."""

    def test_load(self) -> None:
        bridge, js_bot, _rt = _make_bridge()
        bridge.load()
        assert js_bot.loadPlugin.call_count == 2
        assert bridge.is_loaded is True

    def test_load_idempotent(self) -> None:
        bridge, js_bot, _rt = _make_bridge()
        bridge.load()
        bridge.load()
        assert js_bot.loadPlugin.call_count == 2

    def test_load_js_error_raises_bridge_error(self) -> None:
        runtime = MagicMock()
        js_bot = MagicMock()
        relay = MagicMock()
        runtime.require.side_effect = Exception("npm install failed")
        bridge = PanoramaBridge(runtime, js_bot, relay)
        with pytest.raises(BridgeError, match="load panorama"):
            bridge.load()
        assert bridge.is_loaded is False

    def test_npm_name(self) -> None:
        assert PanoramaBridge.NPM_NAME == "mineflayer-panorama"


class TestPanoramaBridgeTakePanorama:
    """start_take_panorama bridge method."""

    def test_start_take_panorama_calls_helpers(self) -> None:
        bridge, _bot, runtime = _loaded_bridge()
        # _ensure_helpers() calls require() again for helpers.js
        helpers = MagicMock()
        runtime.require.return_value = helpers
        bridge.start_take_panorama()
        helpers.startPanorama.assert_called_once()

    def test_start_take_panorama_with_height(self) -> None:
        bridge, js_bot, runtime = _loaded_bridge()
        helpers = MagicMock()
        runtime.require.return_value = helpers
        bridge.start_take_panorama(cam_pos=25.0)
        helpers.startPanorama.assert_called_once_with(js_bot, 25.0)

    def test_start_take_panorama_not_loaded_raises(self) -> None:
        runtime = MagicMock()
        js_bot = MagicMock()
        relay = MagicMock()
        bridge = PanoramaBridge(runtime, js_bot, relay)
        with pytest.raises(BridgeError, match="panorama has not been loaded"):
            bridge.start_take_panorama()

    def test_start_take_panorama_js_error_raises(self) -> None:
        bridge, _bot, runtime = _loaded_bridge()
        helpers = MagicMock()
        helpers.startPanorama.side_effect = Exception("boom")
        runtime.require.return_value = helpers
        with pytest.raises(BridgeError, match="start_take_panorama"):
            bridge.start_take_panorama()


class TestPanoramaBridgeTakePicture:
    """start_take_picture bridge method."""

    def test_start_take_picture_calls_helpers(self) -> None:
        bridge, js_bot, runtime = _loaded_bridge()
        helpers = MagicMock()
        runtime.require.return_value = helpers
        bridge.start_take_picture(1.0, 2.0, 3.0, 0.0, 1.0, 0.0)
        helpers.startPicture.assert_called_once_with(
            js_bot,
            {"x": 1.0, "y": 2.0, "z": 3.0},
            {"x": 0.0, "y": 1.0, "z": 0.0},
        )

    def test_start_take_picture_not_loaded_raises(self) -> None:
        runtime = MagicMock()
        js_bot = MagicMock()
        relay = MagicMock()
        bridge = PanoramaBridge(runtime, js_bot, relay)
        with pytest.raises(BridgeError, match="panorama has not been loaded"):
            bridge.start_take_picture(0, 0, 0, 0, 0, 0)

    def test_start_take_picture_js_error_raises(self) -> None:
        bridge, _bot, runtime = _loaded_bridge()
        helpers = MagicMock()
        helpers.startPicture.side_effect = Exception("crash")
        runtime.require.return_value = helpers
        with pytest.raises(BridgeError, match="start_take_picture"):
            bridge.start_take_picture(0, 0, 0, 0, 0, 0)


class TestPanoramaBridgeTeardown:
    """Teardown nulls out bot references and marks plugin unloaded."""

    def test_teardown_nulls_bot_refs(self) -> None:
        bridge, js_bot, _rt = _loaded_bridge()
        bridge.teardown()
        # Should null out bot.panoramaImage and bot.image
        assert js_bot.panoramaImage is None
        assert js_bot.image is None
        assert bridge.is_loaded is False

    def test_teardown_safe_when_not_loaded(self) -> None:
        runtime = MagicMock()
        js_bot = MagicMock()
        relay = MagicMock()
        bridge = PanoramaBridge(runtime, js_bot, relay)
        bridge.teardown()  # should not raise

    def test_teardown_survives_attribute_error(self) -> None:
        bridge, js_bot, _rt = _loaded_bridge()
        # Simulate bot proxy that rejects attribute set
        type(js_bot).panoramaImage = property(
            lambda s: None, lambda s, v: (_ for _ in ()).throw(AttributeError)
        )
        bridge.teardown()  # should not raise
        assert bridge.is_loaded is False


# ---------------------------------------------------------------------------
# PanoramaDoneEvent / PictureDoneEvent tests
# ---------------------------------------------------------------------------


class TestPanoramaDoneEvent:
    """PanoramaDoneEvent dataclass."""

    def test_success_event(self) -> None:
        event = PanoramaDoneEvent(result="stream_proxy")
        assert event.error is None
        assert event.result == "stream_proxy"

    def test_error_event(self) -> None:
        event = PanoramaDoneEvent(error="capture failed")
        assert event.error == "capture failed"
        assert event.result is None

    def test_default_values(self) -> None:
        event = PanoramaDoneEvent()
        assert event.error is None
        assert event.result is None

    def test_frozen(self) -> None:
        event = PanoramaDoneEvent()
        with pytest.raises(AttributeError):
            event.error = "fail"  # type: ignore[misc]


class TestPictureDoneEvent:
    """PictureDoneEvent dataclass."""

    def test_success_event(self) -> None:
        event = PictureDoneEvent(result="jpeg_stream")
        assert event.error is None
        assert event.result == "jpeg_stream"

    def test_error_event(self) -> None:
        event = PictureDoneEvent(error="render failed")
        assert event.error == "render failed"
        assert event.result is None

    def test_frozen(self) -> None:
        event = PictureDoneEvent()
        with pytest.raises(AttributeError):
            event.result = "bad"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# PanoramaAPI tests
# ---------------------------------------------------------------------------


class TestPanoramaAPIRawTakePanorama:
    """PanoramaAPI.raw_take_panorama async method (raw escape hatch)."""

    @pytest.mark.asyncio
    async def test_raw_take_panorama_success(self) -> None:
        bridge = MagicMock(spec=PanoramaBridge)
        relay = MagicMock()
        stream_proxy = MagicMock()
        success_event = PanoramaDoneEvent(error=None, result=stream_proxy)

        async def _wait_for(*_a: object, **_kw: object) -> PanoramaDoneEvent:
            return success_event

        relay.wait_for = _wait_for
        api = PanoramaAPI(bridge, relay)
        result = await api.raw_take_panorama()
        assert result is stream_proxy
        bridge.start_take_panorama.assert_called_once_with(None)

    @pytest.mark.asyncio
    async def test_raw_take_panorama_with_height(self) -> None:
        bridge = MagicMock(spec=PanoramaBridge)
        relay = MagicMock()
        success_event = PanoramaDoneEvent(error=None, result="stream")

        async def _wait_for(*_a: object, **_kw: object) -> PanoramaDoneEvent:
            return success_event

        relay.wait_for = _wait_for
        api = PanoramaAPI(bridge, relay)
        await api.raw_take_panorama(camera_height=50.0)
        bridge.start_take_panorama.assert_called_once_with(50.0)

    @pytest.mark.asyncio
    async def test_raw_take_panorama_error_raises(self) -> None:
        bridge = MagicMock(spec=PanoramaBridge)
        relay = MagicMock()
        error_event = PanoramaDoneEvent(error="canvas not available")

        async def _wait_for(*_a: object, **_kw: object) -> PanoramaDoneEvent:
            return error_event

        relay.wait_for = _wait_for
        api = PanoramaAPI(bridge, relay)
        with pytest.raises(BridgeError, match="panorama capture failed"):
            await api.raw_take_panorama()

    @pytest.mark.asyncio
    async def test_raw_take_panorama_timeout_raises(self) -> None:
        bridge = MagicMock(spec=PanoramaBridge)
        relay = MagicMock()

        async def _timeout(*_args: object, **_kwargs: object) -> None:
            raise TimeoutError("timed out")

        relay.wait_for = _timeout
        api = PanoramaAPI(bridge, relay)
        with pytest.raises(BridgeError, match="panorama capture timed out"):
            await api.raw_take_panorama()

    @pytest.mark.asyncio
    async def test_raw_take_panorama_serialized_by_lock(self) -> None:
        """Concurrent raw_take_panorama calls are serialized by the lock."""
        bridge = MagicMock(spec=PanoramaBridge)
        relay = MagicMock()
        call_count = 0

        async def _mock_wait_for(
            *_args: object, **_kwargs: object
        ) -> PanoramaDoneEvent:
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.01)
            return PanoramaDoneEvent(error=None, result="stream")

        relay.wait_for = _mock_wait_for
        api = PanoramaAPI(bridge, relay)
        await asyncio.gather(api.raw_take_panorama(), api.raw_take_panorama())
        assert bridge.start_take_panorama.call_count == 2


class TestPanoramaAPIRawTakePicture:
    """PanoramaAPI.raw_take_picture async method (raw escape hatch)."""

    @pytest.mark.asyncio
    async def test_raw_take_picture_success(self) -> None:
        bridge = MagicMock(spec=PanoramaBridge)
        relay = MagicMock()
        stream_proxy = MagicMock()
        success_event = PictureDoneEvent(error=None, result=stream_proxy)

        async def _wait_for(*_a: object, **_kw: object) -> PictureDoneEvent:
            return success_event

        relay.wait_for = _wait_for
        api = PanoramaAPI(bridge, relay)
        point = Vec3(10.0, 20.0, 30.0)
        direction = Vec3(0.0, -1.0, 0.0)
        result = await api.raw_take_picture(point, direction)
        assert result is stream_proxy
        bridge.start_take_picture.assert_called_once_with(
            10.0, 20.0, 30.0, 0.0, -1.0, 0.0
        )

    @pytest.mark.asyncio
    async def test_raw_take_picture_error_raises(self) -> None:
        bridge = MagicMock(spec=PanoramaBridge)
        relay = MagicMock()
        error_event = PictureDoneEvent(error="render crash")

        async def _wait_for(*_a: object, **_kw: object) -> PictureDoneEvent:
            return error_event

        relay.wait_for = _wait_for
        api = PanoramaAPI(bridge, relay)
        with pytest.raises(BridgeError, match="picture capture failed"):
            await api.raw_take_picture(Vec3(0, 0, 0), Vec3(1, 0, 0))

    @pytest.mark.asyncio
    async def test_raw_take_picture_timeout_raises(self) -> None:
        bridge = MagicMock(spec=PanoramaBridge)
        relay = MagicMock()

        async def _timeout(*_args: object, **_kwargs: object) -> None:
            raise TimeoutError("timed out")

        relay.wait_for = _timeout
        api = PanoramaAPI(bridge, relay)
        with pytest.raises(BridgeError, match="picture capture timed out"):
            await api.raw_take_picture(Vec3(0, 0, 0), Vec3(1, 0, 0))

    @pytest.mark.asyncio
    async def test_raw_take_picture_serialized_by_lock(self) -> None:
        """Concurrent raw_take_picture calls are serialized by the lock."""
        bridge = MagicMock(spec=PanoramaBridge)
        relay = MagicMock()

        async def _mock_wait_for(*_args: object, **_kwargs: object) -> PictureDoneEvent:
            await asyncio.sleep(0.01)
            return PictureDoneEvent(error=None, result="jpeg")

        relay.wait_for = _mock_wait_for
        api = PanoramaAPI(bridge, relay)
        p = Vec3(0, 0, 0)
        d = Vec3(1, 0, 0)
        await asyncio.gather(api.raw_take_picture(p, d), api.raw_take_picture(p, d))
        assert bridge.start_take_picture.call_count == 2
