"""Panorama plugin bridge.

.. warning:: **Experimental.** Requires native ``node-canvas-webgl``
   build. Version 0.0.1 — API may be unstable.

Ref: mineflayer-panorama/index.js — ``{ panoramaImage, image }``
"""

from __future__ import annotations

import pathlib
from typing import Any

from minethon._bridge._util import extract_js_stack
from minethon._bridge.plugins._base import PluginBridge
from minethon.models.errors import BridgeError

_JS_HELPERS_PATH = pathlib.Path(__file__).resolve().parent.parent / "js" / "helpers.js"


class PanoramaBridge(PluginBridge):
    """Bridge for ``mineflayer-panorama``.

    .. warning:: **Experimental.** Requires native ``node-canvas-webgl``
       build. Version 0.0.1 — API may be unstable.

    Ref: mineflayer-panorama/index.js
    """

    NPM_NAME = "mineflayer-panorama"

    def __init__(
        self,
        runtime: Any,
        js_bot: Any,
        relay: Any,
    ) -> None:
        super().__init__(runtime, js_bot, relay)
        self._helpers: Any = None
        self._faulted: bool = False

    def _ensure_helpers(self) -> Any:
        """Lazy-load helpers.js and cache the reference."""
        if self._helpers is None:
            self._helpers = self._runtime.require(str(_JS_HELPERS_PATH.as_posix()))
        return self._helpers

    def _do_load(self) -> None:
        """Load the panorama plugin into the JS bot.

        The module exports ``{ panoramaImage, image }`` — two independent
        inject functions that must both be loaded.

        Ref: mineflayer-panorama/index.js:23-26 — ``module.exports = { panoramaImage, image }``
        """
        if self._faulted:
            raise BridgeError(
                "panorama bridge is permanently faulted from a prior partial load failure"
            )
        try:
            mod = self._runtime.require(self.NPM_NAME)
            self._js_bot.loadPlugin(mod.panoramaImage)
            self._js_bot.loadPlugin(mod.image)
        except Exception as exc:
            self._faulted = True
            raise BridgeError(
                f"load panorama failed: {exc}",
                js_stack=extract_js_stack(exc),
            ) from exc

    def teardown(self) -> None:
        """Best-effort cleanup of panorama native resources.

        Each ``panoramaImage`` / ``image`` inject function creates a
        ``Camera`` instance inside a closure that allocates a
        ``node-canvas-webgl`` canvas, ``THREE.WebGLRenderer``, and
        ``Viewer``.  These are **not** reachable from outside the
        closure, so we can only null out the bot-level references to
        release the JS-side GC roots.

        Ref: mineflayer-panorama/index.js:3-21 — closure-captured Camera
        Ref: mineflayer-panorama/lib/camera.js:19-21 — canvas/renderer/viewer
        """
        if not self._loaded:
            return
        try:
            self._js_bot.panoramaImage = None
        except Exception:  # noqa: S110 — best-effort teardown
            pass
        try:
            self._js_bot.image = None
        except Exception:  # noqa: S110 — best-effort teardown
            pass
        self._helpers = None
        self._loaded = False

    def start_take_panorama(self, cam_pos: float | None = None) -> None:
        """Start panorama capture without blocking.

        Completion is signalled via ``_minethon:panoramaDone`` event.

        Args:
            cam_pos: Camera height. ``None`` for default (bot position,
                height 10), or a float for custom height.

        Ref: mineflayer-panorama/lib/camera.js:51-56 — camPos handling
        """
        if not self._loaded:
            raise BridgeError(
                "start_take_panorama failed: panorama has not been loaded"
            )
        try:
            helpers = self._ensure_helpers()
            helpers.startPanorama(self._js_bot, cam_pos)
        except Exception as exc:
            raise BridgeError(
                f"start_take_panorama failed: {exc}",
                js_stack=extract_js_stack(exc),
            ) from exc

    def start_take_picture(
        self,
        point_x: float,
        point_y: float,
        point_z: float,
        dir_x: float,
        dir_y: float,
        dir_z: float,
    ) -> None:
        """Start single picture capture without blocking.

        Completion is signalled via ``_minethon:pictureDone`` event.

        Args:
            point_x: Camera position X.
            point_y: Camera position Y.
            point_z: Camera position Z.
            dir_x: Look direction X.
            dir_y: Look direction Y.
            dir_z: Look direction Z.

        Ref: mineflayer-panorama/lib/camera.js — ``takePicture(point, direction)``
        """
        if not self._loaded:
            raise BridgeError("start_take_picture failed: panorama has not been loaded")
        try:
            helpers = self._ensure_helpers()
            helpers.startPicture(
                self._js_bot,
                {"x": point_x, "y": point_y, "z": point_z},
                {"x": dir_x, "y": dir_y, "z": dir_z},
            )
        except Exception as exc:
            raise BridgeError(
                f"start_take_picture failed: {exc}",
                js_stack=extract_js_stack(exc),
            ) from exc
