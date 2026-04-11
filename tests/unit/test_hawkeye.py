"""Unit tests for the hawkeye (minecrafthawkeye) plugin integration."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from minethon._bridge._events import SimplyShotDoneEvent
from minethon._bridge.plugins.hawkeye import HawkEyeBridge
from minethon.api.combat import CombatAPI
from minethon.models.entity import Entity, EntityKind
from minethon.models.errors import BridgeError
from minethon.models.events import AutoShotStoppedEvent
from minethon.models.vec3 import Vec3
from minethon.models.weapon import Weapon

# -- Weapon model tests --


class TestWeaponEnum:
    """Weapon enum values match minecrafthawkeye JS strings."""

    def test_weapon_values(self) -> None:
        assert Weapon.BOW.value == "bow"
        assert Weapon.CROSSBOW.value == "crossbow"
        assert Weapon.TRIDENT.value == "trident"
        assert Weapon.ENDER_PEARL.value == "ender_pearl"
        assert Weapon.SNOWBALL.value == "snowball"
        assert Weapon.EGG.value == "egg"
        assert Weapon.SPLASH_POTION.value == "splash_potion"

    def test_weapon_count(self) -> None:
        assert len(Weapon) == 7


# -- HawkEyeBridge tests --


def _make_bridge() -> tuple[HawkEyeBridge, MagicMock, MagicMock, MagicMock]:
    runtime = MagicMock()
    js_bot = MagicMock()
    relay = MagicMock()
    controller = MagicMock()
    bridge = HawkEyeBridge(runtime, js_bot, relay, controller)
    return bridge, runtime, js_bot, controller


def _load_bridge(
    bridge: HawkEyeBridge,
    runtime: MagicMock,
) -> None:
    mod = MagicMock()
    mod.default = MagicMock()
    runtime.require.return_value = mod
    bridge.load()


class TestHawkEyeBridgeLoad:
    """Loading the hawkeye plugin via HawkEyeBridge."""

    def test_load_hawkeye(self) -> None:
        bridge, runtime, js_bot, _ctrl = _make_bridge()
        mod = MagicMock()
        inject_fn = MagicMock()
        mod.default = inject_fn
        runtime.require.return_value = mod

        bridge.load()

        assert runtime.require.call_count == 2
        runtime.require.assert_any_call("minecrafthawkeye")
        js_bot.loadPlugin.assert_called_once_with(inject_fn)
        assert bridge.is_loaded is True

    def test_load_hawkeye_idempotent(self) -> None:
        bridge, runtime, js_bot, _ctrl = _make_bridge()
        mod = MagicMock()
        mod.default = MagicMock()
        runtime.require.return_value = mod

        bridge.load()
        bridge.load()

        js_bot.loadPlugin.assert_called_once()

    def test_load_hawkeye_no_default_fallback(self) -> None:
        """When exports.default is absent, use module itself."""
        bridge, runtime, js_bot, _ctrl = _make_bridge()
        mod = MagicMock(spec=[])  # no 'default' attribute
        runtime.require.return_value = mod

        bridge.load()

        js_bot.loadPlugin.assert_called_once_with(mod)

    def test_load_hawkeye_error_raises(self) -> None:
        bridge, runtime, _js_bot, _ctrl = _make_bridge()
        runtime.require.side_effect = Exception("npm install failed")

        with pytest.raises(BridgeError, match="load hawkeye"):
            bridge.load()
        assert bridge.is_loaded is False


class TestHawkEyeBridgeAutoAttack:
    """HawkEyeBridge.auto_attack."""

    def test_auto_attack_success(self) -> None:
        bridge, runtime, js_bot, ctrl = _make_bridge()
        _load_bridge(bridge, runtime)

        js_entity = MagicMock()
        ctrl.get_entity_by_id.return_value = js_entity
        js_bot.hawkEye.autoAttack.return_value = True

        result = bridge.auto_attack(42, "bow")

        ctrl.get_entity_by_id.assert_called_once_with(42)
        js_bot.hawkEye.autoAttack.assert_called_once_with(js_entity, "bow")
        assert result is True

    def test_auto_attack_returns_false(self) -> None:
        bridge, runtime, js_bot, ctrl = _make_bridge()
        _load_bridge(bridge, runtime)

        ctrl.get_entity_by_id.return_value = MagicMock()
        js_bot.hawkEye.autoAttack.return_value = False
        result = bridge.auto_attack(42, "crossbow")
        assert result is False

    def test_auto_attack_not_loaded_raises(self) -> None:
        bridge, _rt, _bot, _ctrl = _make_bridge()
        with pytest.raises(BridgeError, match="hawkeye has not been loaded"):
            bridge.auto_attack(42, "bow")

    def test_auto_attack_entity_not_found_raises(self) -> None:
        bridge, runtime, _js_bot, ctrl = _make_bridge()
        _load_bridge(bridge, runtime)

        ctrl.get_entity_by_id.return_value = None
        with pytest.raises(BridgeError, match="Entity with id 42 not found"):
            bridge.auto_attack(42, "bow")

    def test_auto_attack_js_error_raises(self) -> None:
        bridge, runtime, js_bot, ctrl = _make_bridge()
        _load_bridge(bridge, runtime)

        ctrl.get_entity_by_id.return_value = MagicMock()
        js_bot.hawkEye.autoAttack.side_effect = Exception("target lost")
        with pytest.raises(BridgeError, match="auto_attack"):
            bridge.auto_attack(42, "bow")


class TestHawkEyeBridgeOneShot:
    """HawkEyeBridge.one_shot."""

    def test_one_shot_success(self) -> None:
        bridge, runtime, js_bot, ctrl = _make_bridge()
        _load_bridge(bridge, runtime)

        js_entity = MagicMock()
        ctrl.get_entity_by_id.return_value = js_entity
        js_bot.hawkEye.oneShot.return_value = True

        result = bridge.one_shot(99, "trident")

        ctrl.get_entity_by_id.assert_called_once_with(99)
        js_bot.hawkEye.oneShot.assert_called_once_with(js_entity, "trident")
        assert result is True

    def test_one_shot_not_loaded_raises(self) -> None:
        bridge, _rt, _bot, _ctrl = _make_bridge()
        with pytest.raises(BridgeError, match="hawkeye has not been loaded"):
            bridge.one_shot(42, "bow")


class TestHawkEyeBridgeStop:
    """HawkEyeBridge.stop."""

    def test_stop(self) -> None:
        bridge, runtime, js_bot, _ctrl = _make_bridge()
        _load_bridge(bridge, runtime)

        bridge.stop()

        js_bot.hawkEye.stop.assert_called_once()

    def test_stop_not_loaded_is_noop(self) -> None:
        bridge, _rt, js_bot, _ctrl = _make_bridge()
        bridge.stop()  # should not raise
        js_bot.hawkEye.stop.assert_not_called()

    def test_stop_swallows_attribute_error(self) -> None:
        bridge, runtime, js_bot, _ctrl = _make_bridge()
        _load_bridge(bridge, runtime)

        js_bot.hawkEye.stop.side_effect = AttributeError("gone")
        bridge.stop()  # should not raise

    def test_stop_swallows_type_error(self) -> None:
        bridge, runtime, js_bot, _ctrl = _make_bridge()
        _load_bridge(bridge, runtime)

        js_bot.hawkEye.stop.side_effect = TypeError("gone")
        bridge.stop()  # should not raise


class TestHawkEyeBridgeSimplyShot:
    """HawkEyeBridge.start_simply_shot."""

    def test_start_simply_shot_not_loaded_raises(self) -> None:
        bridge, _rt, _bot, _ctrl = _make_bridge()
        with pytest.raises(BridgeError, match="hawkeye has not been loaded"):
            bridge.start_simply_shot(1.0, -0.5)


class TestHawkEyeBridgeTeardown:
    """HawkEyeBridge.teardown."""

    def test_teardown_stops(self) -> None:
        bridge, runtime, js_bot, _ctrl = _make_bridge()
        _load_bridge(bridge, runtime)

        bridge.teardown()

        js_bot.hawkEye.stop.assert_called_once()


# -- CombatAPI tests --


def _make_entity(entity_id: int = 42, name: str = "zombie") -> Entity:
    return Entity(
        id=entity_id,
        name=name,
        kind=EntityKind.HOSTILE,
        position=Vec3(10.0, 64.0, 20.0),
    )


def _make_combat_api() -> tuple[CombatAPI, MagicMock, AsyncMock]:
    bridge = MagicMock(spec=HawkEyeBridge)
    relay = AsyncMock()
    api = CombatAPI(bridge, relay)
    return api, bridge, relay


class TestCombatAPIAutoAttack:
    """CombatAPI.auto_attack."""

    def test_auto_attack_delegates_to_bridge(self) -> None:
        api, bridge, _relay = _make_combat_api()
        entity = _make_entity()
        bridge.auto_attack.return_value = True

        result = api.auto_attack(entity, Weapon.BOW)

        bridge.auto_attack.assert_called_once_with(42, "bow")
        assert result is True

    def test_auto_attack_default_weapon(self) -> None:
        api, bridge, _relay = _make_combat_api()
        entity = _make_entity()
        bridge.auto_attack.return_value = True

        api.auto_attack(entity)

        bridge.auto_attack.assert_called_once_with(42, "bow")

    def test_auto_attack_with_crossbow(self) -> None:
        api, bridge, _relay = _make_combat_api()
        entity = _make_entity()
        bridge.auto_attack.return_value = True

        api.auto_attack(entity, Weapon.CROSSBOW)

        bridge.auto_attack.assert_called_once_with(42, "crossbow")


class TestCombatAPIShoot:
    """CombatAPI.shoot."""

    def test_shoot_delegates_to_bridge(self) -> None:
        api, bridge, _relay = _make_combat_api()
        entity = _make_entity()
        bridge.one_shot.return_value = True

        result = api.shoot(entity, Weapon.TRIDENT)

        bridge.one_shot.assert_called_once_with(42, "trident")
        assert result is True

    def test_shoot_default_weapon(self) -> None:
        api, bridge, _relay = _make_combat_api()
        entity = _make_entity()
        bridge.one_shot.return_value = True

        api.shoot(entity)

        bridge.one_shot.assert_called_once_with(42, "bow")


class TestCombatAPIStop:
    """CombatAPI.stop."""

    def test_stop_delegates_to_bridge(self) -> None:
        api, bridge, _relay = _make_combat_api()
        api.stop()
        bridge.stop.assert_called_once()


class TestCombatAPISimplyShot:
    """CombatAPI.simply_shot."""

    @pytest.mark.asyncio
    async def test_simply_shot_success(self) -> None:
        api, bridge, relay = _make_combat_api()

        done_event = SimplyShotDoneEvent(error=None)
        relay.wait_for.return_value = done_event

        await api.simply_shot(1.5, -0.3)

        bridge.start_simply_shot.assert_called_once_with(1.5, -0.3)
        relay.wait_for.assert_called_once_with(SimplyShotDoneEvent, timeout=10.0)

    @pytest.mark.asyncio
    async def test_simply_shot_error_raises(self) -> None:
        api, _bridge, relay = _make_combat_api()

        done_event = SimplyShotDoneEvent(error="failed to activate")
        relay.wait_for.return_value = done_event

        with pytest.raises(BridgeError, match="simply_shot failed"):
            await api.simply_shot(0.0, 0.0)


# -- Event model tests --


class TestAutoShotStoppedEvent:
    """AutoShotStoppedEvent dataclass."""

    def test_default_target_none(self) -> None:
        event = AutoShotStoppedEvent()
        assert event.target is None

    def test_with_target(self) -> None:
        entity = _make_entity()
        event = AutoShotStoppedEvent(target=entity)
        assert event.target is entity
        assert event.target.name == "zombie"

    def test_frozen(self) -> None:
        event = AutoShotStoppedEvent()
        with pytest.raises(AttributeError):
            event.target = _make_entity()  # type: ignore[misc]


class TestSimplyShotDoneEvent:
    """SimplyShotDoneEvent internal event."""

    def test_success(self) -> None:
        event = SimplyShotDoneEvent()
        assert event.error is None

    def test_with_error(self) -> None:
        event = SimplyShotDoneEvent(error="timeout")
        assert event.error == "timeout"
