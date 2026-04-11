"""Projectile combat control via minecrafthawkeye."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from minethon._bridge._events import SimplyShotDoneEvent
from minethon.models.errors import BridgeError
from minethon.models.weapon import Weapon

if TYPE_CHECKING:
    from minethon._bridge.event_relay import EventRelay
    from minethon._bridge.plugins.hawkeye import HawkEyeBridge
    from minethon.models.entity import Entity


class CombatAPI:
    """Projectile combat control using ``minecrafthawkeye``.

    Provides auto-attack, one-shot, and directional-shot capabilities
    for bows, crossbows, tridents, and throwable items.

    Example::

        zombie = await bot.nearest_entity(name="zombie")
        started = bot.combat.auto_attack(zombie)
        bot.combat.stop()

    Ref: minecrafthawkeye/dist/hawkEye.js
    """

    def __init__(
        self,
        bridge: HawkEyeBridge,
        relay: EventRelay,
    ) -> None:
        self._bridge = bridge
        self._relay = relay
        self._simply_shot_lock = asyncio.Lock()

    def auto_attack(self, entity: Entity, weapon: Weapon = Weapon.BOW) -> bool:
        """Start auto-attacking a target entity.

        The bot will continuously track and fire at the target until
        :meth:`stop` is called or the target dies.

        Args:
            entity: The target entity to attack.
            weapon: Projectile weapon type. Defaults to bow.

        Returns:
            True if the attack was started successfully.

        Raises:
            BridgeError: If the entity is not found or the JS call fails.

        Ref: minecrafthawkeye/dist/hawkEye.js — ``autoAttack``
        """
        return self._bridge.auto_attack(entity.id, weapon.value)

    def shoot(self, entity: Entity, weapon: Weapon = Weapon.BOW) -> bool:
        """Fire a single shot at a target entity.

        Args:
            entity: The target entity to shoot.
            weapon: Projectile weapon type. Defaults to bow.

        Returns:
            True if the shot was started successfully.

        Raises:
            BridgeError: If the entity is not found or the JS call fails.

        Ref: minecrafthawkeye/dist/hawkEye.js — ``oneShot``
        """
        return self._bridge.one_shot(entity.id, weapon.value)

    def stop(self) -> None:
        """Stop auto-attacking.

        Safe to call even when not attacking.

        Ref: minecrafthawkeye/dist/hawkEye.js — ``stop``
        """
        self._bridge.stop()

    async def simply_shot(self, yaw: float, pitch: float) -> None:
        """Fire in a direction (look + activate + deactivate).

        This is an async operation that completes when the shot
        sequence (look, activate, wait ~1200ms, deactivate) finishes.

        Args:
            yaw: Horizontal look angle in radians.
            pitch: Vertical look angle in radians.

        Raises:
            BridgeError: If the JS call fails.

        Ref: minecrafthawkeye/dist/hawkEye.js — ``simplyShot``
        """
        async with self._simply_shot_lock:
            self._bridge.start_simply_shot(yaw, pitch)
            result = await self._relay.wait_for(SimplyShotDoneEvent, timeout=10.0)
            if result.error is not None:
                raise BridgeError(f"simply_shot failed: {result.error}")
