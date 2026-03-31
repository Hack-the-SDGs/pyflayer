import pytest
from pyflayer.models.item import ItemStack


class TestItemStack:
    def test_creation_minimal(self) -> None:
        item = ItemStack(
            name="diamond_pickaxe",
            display_name="Diamond Pickaxe",
            count=1,
            slot=0,
            max_stack_size=1,
        )
        assert item.name == "diamond_pickaxe"
        assert item.display_name == "Diamond Pickaxe"
        assert item.count == 1
        assert item.slot == 0
        assert item.max_stack_size == 1
        assert item.enchantments is None
        assert item.nbt is None

    def test_creation_with_enchantments(self) -> None:
        enchants = [{"name": "efficiency", "level": 5}]
        item = ItemStack(
            name="diamond_pickaxe",
            display_name="Diamond Pickaxe",
            count=1,
            slot=0,
            max_stack_size=1,
            enchantments=enchants,
        )
        assert item.enchantments == enchants

    def test_creation_with_nbt(self) -> None:
        nbt_data = {"Damage": 0}
        item = ItemStack(
            name="diamond_sword",
            display_name="Diamond Sword",
            count=1,
            slot=1,
            max_stack_size=1,
            nbt=nbt_data,
        )
        assert item.nbt == nbt_data

    def test_frozen(self) -> None:
        item = ItemStack(
            name="cobblestone",
            display_name="Cobblestone",
            count=64,
            slot=5,
            max_stack_size=64,
        )
        with pytest.raises(AttributeError):
            item.count = 32  # type: ignore[misc]

    def test_stackable_item(self) -> None:
        item = ItemStack(
            name="cobblestone",
            display_name="Cobblestone",
            count=64,
            slot=3,
            max_stack_size=64,
        )
        assert item.count == 64
        assert item.max_stack_size == 64
