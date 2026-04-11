"""Internal bridge events for async JS operations.

These are private to the bridge layer — never import from public API.
Each event signals completion of a non-blocking JS action started by
the helpers in ``_bridge/js/helpers.js``.
"""

from dataclasses import dataclass
from typing import Any

# -- Existing events --


@dataclass(frozen=True, slots=True)
class DigDoneEvent:
    """Dig operation finished (success if error is None)."""

    error: str | None = None


@dataclass(frozen=True, slots=True)
class PlaceDoneEvent:
    """Place operation finished."""

    error: str | None = None


@dataclass(frozen=True, slots=True)
class EquipDoneEvent:
    """Equip operation finished."""

    error: str | None = None


@dataclass(frozen=True, slots=True)
class LookAtDoneEvent:
    """LookAt operation finished."""

    error: str | None = None


# -- Movement --


@dataclass(frozen=True, slots=True)
class LookDoneEvent:
    """Look (yaw/pitch) operation finished."""

    error: str | None = None


# -- Sleep --


@dataclass(frozen=True, slots=True)
class SleepDoneEvent:
    """Sleep operation finished."""

    error: str | None = None


@dataclass(frozen=True, slots=True)
class WakeDoneEvent:
    """Wake operation finished."""

    error: str | None = None


# -- Inventory --


@dataclass(frozen=True, slots=True)
class UnequipDoneEvent:
    """Unequip operation finished."""

    error: str | None = None


@dataclass(frozen=True, slots=True)
class TossStackDoneEvent:
    """TossStack operation finished."""

    error: str | None = None


@dataclass(frozen=True, slots=True)
class TossDoneEvent:
    """Toss operation finished."""

    error: str | None = None


# -- Actions --


@dataclass(frozen=True, slots=True)
class ConsumeDoneEvent:
    """Consume (eat/drink) operation finished."""

    error: str | None = None


@dataclass(frozen=True, slots=True)
class FishDoneEvent:
    """Fish operation finished."""

    error: str | None = None


@dataclass(frozen=True, slots=True)
class ElytraFlyDoneEvent:
    """Elytra fly activation finished."""

    error: str | None = None


# -- Crafting --


@dataclass(frozen=True, slots=True)
class CraftDoneEvent:
    """Craft operation finished."""

    error: str | None = None


# -- Block interaction --


@dataclass(frozen=True, slots=True)
class ActivateBlockDoneEvent:
    """ActivateBlock operation finished."""

    error: str | None = None


@dataclass(frozen=True, slots=True)
class ActivateEntityDoneEvent:
    """ActivateEntity operation finished."""

    error: str | None = None


@dataclass(frozen=True, slots=True)
class ActivateEntityAtDoneEvent:
    """ActivateEntityAt operation finished."""

    error: str | None = None


# -- Containers (return JS window/instance proxy on success) --


@dataclass(frozen=True, slots=True)
class OpenContainerDoneEvent:
    """OpenContainer operation finished."""

    error: str | None = None
    result: Any = None


@dataclass(frozen=True, slots=True)
class OpenFurnaceDoneEvent:
    """OpenFurnace operation finished."""

    error: str | None = None
    result: Any = None


@dataclass(frozen=True, slots=True)
class OpenEnchantmentTableDoneEvent:
    """OpenEnchantmentTable operation finished."""

    error: str | None = None
    result: Any = None


@dataclass(frozen=True, slots=True)
class OpenAnvilDoneEvent:
    """OpenAnvil operation finished."""

    error: str | None = None
    result: Any = None


@dataclass(frozen=True, slots=True)
class OpenVillagerDoneEvent:
    """OpenVillager operation finished."""

    error: str | None = None
    result: Any = None


# -- Trading --


@dataclass(frozen=True, slots=True)
class TradeDoneEvent:
    """Trade operation finished."""

    error: str | None = None


# -- Tab completion (returns matches) --


@dataclass(frozen=True, slots=True)
class TabCompleteDoneEvent:
    """TabComplete operation finished."""

    error: str | None = None
    result: Any = None


# -- Writing --


@dataclass(frozen=True, slots=True)
class WriteBookDoneEvent:
    """WriteBook operation finished."""

    error: str | None = None


# -- World --


@dataclass(frozen=True, slots=True)
class ChunksLoadedDoneEvent:
    """WaitForChunksToLoad finished."""

    error: str | None = None


@dataclass(frozen=True, slots=True)
class WaitForTicksDoneEvent:
    """WaitForTicks finished."""

    error: str | None = None


# -- Lower-level inventory --


@dataclass(frozen=True, slots=True)
class ClickWindowDoneEvent:
    """ClickWindow operation finished."""

    error: str | None = None


@dataclass(frozen=True, slots=True)
class TransferDoneEvent:
    """Transfer operation finished."""

    error: str | None = None


@dataclass(frozen=True, slots=True)
class MoveSlotItemDoneEvent:
    """MoveSlotItem operation finished."""

    error: str | None = None


@dataclass(frozen=True, slots=True)
class PutAwayDoneEvent:
    """PutAway operation finished."""

    error: str | None = None


# -- Creative --


@dataclass(frozen=True, slots=True)
class CreativeFlyToDoneEvent:
    """Creative flyTo operation finished."""

    error: str | None = None


@dataclass(frozen=True, slots=True)
class CreativeSetSlotDoneEvent:
    """Creative setInventorySlot operation finished."""

    error: str | None = None


@dataclass(frozen=True, slots=True)
class CreativeClearSlotDoneEvent:
    """Creative clearSlot operation finished."""

    error: str | None = None


@dataclass(frozen=True, slots=True)
class CreativeClearInventoryDoneEvent:
    """Creative clearInventory operation finished."""

    error: str | None = None


# -- Armor Manager --


@dataclass(frozen=True, slots=True)
class ArmorEquipDoneEvent:
    """ArmorManager equipAll operation finished."""

    error: str | None = None


# -- Entity placement --


@dataclass(frozen=True, slots=True)
class PlaceEntityDoneEvent:
    """PlaceEntity operation finished."""

    error: str | None = None
    result: Any = None


# -- Plugin: mineflayer-tool --


@dataclass(frozen=True, slots=True)
class ToolEquipDoneEvent:
    """Tool equip-for-block operation finished.

    Ref: mineflayer-tool/lib/Tool.js — ``equipForBlock``
    """

    error: str | None = None


# -- Panorama --


@dataclass(frozen=True, slots=True)
class PanoramaDoneEvent:
    """Panorama capture finished (result is JPEG stream proxy on success).

    Ref: mineflayer-panorama/lib/camera.js — ``panoramaImage``
    """

    error: str | None = None
    result: Any = None


@dataclass(frozen=True, slots=True)
class PictureDoneEvent:
    """Single picture capture finished (result is JPEG stream proxy on success).

    Ref: mineflayer-panorama/lib/camera.js — ``takePicture``
    """

    error: str | None = None
    result: Any = None


# -- HawkEye --


@dataclass(frozen=True, slots=True)
class SimplyShotDoneEvent:
    """SimplyShot operation finished."""

    error: str | None = None


# -- Viewer service --


@dataclass(frozen=True, slots=True)
class ViewerStartDoneEvent:
    """Viewer initialisation finished.

    Ref: prismarine-viewer/lib/mineflayer.js — module.exports
    """

    error: str | None = None


# -- Web inventory service --


@dataclass(frozen=True, slots=True)
class WebInvStartDoneEvent:
    """Web inventory start() finished.

    Ref: mineflayer-web-inventory/index.js — start()
    """

    error: str | None = None


@dataclass(frozen=True, slots=True)
class WebInvStopDoneEvent:
    """Web inventory stop() finished.

    Ref: mineflayer-web-inventory/index.js — stop()
    """

    error: str | None = None


# -- GUI (mineflayer-gui) --


@dataclass(frozen=True, slots=True)
class GuiQueryDoneEvent:
    """GUI query (click) operation finished."""

    error: str | None = None
    result: bool = False


@dataclass(frozen=True, slots=True)
class GuiDropDoneEvent:
    """GUI drop operation finished."""

    error: str | None = None
    result: bool = False
