"""HawkEye plugin bridge.

Ref: minecrafthawkeye/dist/index.js — ``exports.default = inject``
"""

from __future__ import annotations

import pathlib
from typing import TYPE_CHECKING, Any

from minethon._bridge._util import extract_js_stack
from minethon._bridge.plugins._base import PluginBridge
from minethon.models.errors import BridgeError

if TYPE_CHECKING:
    from minethon._bridge.js_bot import JSBotController

_JS_HELPERS_PATH = pathlib.Path(__file__).resolve().parent.parent / "js" / "helpers.js"


class HawkEyeBridge(PluginBridge):
    """Bridge for ``minecrafthawkeye``.

    Manages loading the hawkeye plugin and providing projectile
    combat operations (auto-attack, one-shot, simply-shot).

    Entity lookup happens here in the bridge layer so that the
    public API layer never touches ``_js_bot``.

    Ref: minecrafthawkeye/dist/hawkEye.js
    """

    NPM_NAME = "minecrafthawkeye"

    def __init__(
        self,
        runtime: Any,
        js_bot: Any,
        relay: Any,
        controller: JSBotController,
    ) -> None:
        super().__init__(runtime, js_bot, relay)
        self._controller = controller
        self._helpers: Any = None

    def _do_load(self) -> None:
        """Load the hawkeye plugin into the JS bot.

        The module exports ``exports.default = inject`` where
        ``inject`` is a ``(bot) => void`` function.

        Ref: minecrafthawkeye/dist/index.js:28-44
        """
        try:
            mod = self._runtime.require(self.NPM_NAME)
            inject = getattr(mod, "default", mod)
            self._js_bot.loadPlugin(inject)
            self._helpers = self._runtime.require(str(_JS_HELPERS_PATH.as_posix()))
        except Exception as exc:
            self._loaded = False
            raise BridgeError(
                f"load hawkeye failed: {exc}",
                js_stack=extract_js_stack(exc),
            ) from exc

    def auto_attack(self, entity_id: int, weapon_value: str) -> bool:
        """Start auto-attacking a target entity.

        Looks up the JS entity by ID in the bridge layer, then calls
        ``bot.hawkEye.autoAttack(entity, weapon)``.

        Args:
            entity_id: Numeric entity ID to attack.
            weapon_value: Weapon string value (e.g. ``"bow"``).

        Returns:
            True if the attack was started successfully.

        Raises:
            BridgeError: If the plugin is not loaded, entity not found,
                or the JS call fails.

        Ref: minecrafthawkeye/dist/hawkEye.js — ``autoAttack(target, weapon)``
        """
        if not self._loaded:
            raise BridgeError("auto_attack failed: hawkeye has not been loaded")
        js_entity = self._controller.get_entity_by_id(entity_id)
        if js_entity is None:
            raise BridgeError(f"Entity with id {entity_id} not found")
        try:
            return bool(self._js_bot.hawkEye.autoAttack(js_entity, weapon_value))
        except Exception as exc:
            raise BridgeError(
                f"auto_attack failed: {exc}",
                js_stack=extract_js_stack(exc),
            ) from exc

    def one_shot(self, entity_id: int, weapon_value: str) -> bool:
        """Fire a single shot at a target entity.

        Looks up the JS entity by ID in the bridge layer, then calls
        ``bot.hawkEye.oneShot(entity, weapon)``.

        Args:
            entity_id: Numeric entity ID to shoot.
            weapon_value: Weapon string value (e.g. ``"bow"``).

        Returns:
            True if the shot was started successfully.

        Raises:
            BridgeError: If the plugin is not loaded, entity not found,
                or the JS call fails.

        Ref: minecrafthawkeye/dist/hawkEye.js — ``oneShot(target, weapon)``
        """
        if not self._loaded:
            raise BridgeError("one_shot failed: hawkeye has not been loaded")
        js_entity = self._controller.get_entity_by_id(entity_id)
        if js_entity is None:
            raise BridgeError(f"Entity with id {entity_id} not found")
        try:
            return bool(self._js_bot.hawkEye.oneShot(js_entity, weapon_value))
        except Exception as exc:
            raise BridgeError(
                f"one_shot failed: {exc}",
                js_stack=extract_js_stack(exc),
            ) from exc

    def stop(self) -> None:
        """Stop hawkeye auto-attacking.

        Silently returns when the plugin is not loaded or the bot is
        mid-shutdown.

        Ref: minecrafthawkeye/dist/hawkEye.js — ``stop()``
        """
        if not self._loaded:
            return
        try:
            hawk_eye = getattr(self._js_bot, "hawkEye", None)
            if hawk_eye is None:
                return
            hawk_eye.stop()
        except AttributeError, TypeError:
            return

    def start_simply_shot(self, yaw: float, pitch: float) -> None:
        """Fire a directional shot via hawkEye.simplyShot (async JS).

        Completion is signalled by ``_minethon:simplyShotDone``.

        Args:
            yaw: Horizontal look angle in radians.
            pitch: Vertical look angle in radians.

        Raises:
            BridgeError: If the plugin is not loaded or the JS call fails.

        Ref: minecrafthawkeye/dist/hawkEye.js — ``simplyShot(yaw, pitch)``
        """
        if not self._loaded:
            raise BridgeError("start_simply_shot failed: hawkeye has not been loaded")
        try:
            self._helpers.startSimplyShot(self._js_bot, yaw, pitch)
        except Exception as exc:
            raise BridgeError(
                f"start_simply_shot failed: {exc}",
                js_stack=extract_js_stack(exc),
            ) from exc

    def teardown(self) -> None:
        """Stop auto-attacking on disconnect."""
        self.stop()
