"""Tests for _bridge/marshalling.py using mock JS proxy objects."""

from types import SimpleNamespace

from pyflayer._bridge.marshalling import (
    js_block_to_block,
    js_entity_to_entity,
    js_item_to_item_stack,
    js_vec3_to_vec3,
)
from pyflayer.models.entity import EntityKind
from pyflayer.models.vec3 import Vec3


def _mock_vec3(x: float, y: float, z: float) -> SimpleNamespace:
    return SimpleNamespace(x=x, y=y, z=z)


class TestJsVec3ToVec3:
    def test_basic(self) -> None:
        result = js_vec3_to_vec3(_mock_vec3(1.5, 64.0, -3.2))
        assert result == Vec3(1.5, 64.0, -3.2)

    def test_integer_values(self) -> None:
        result = js_vec3_to_vec3(_mock_vec3(10, 20, 30))
        assert result == Vec3(10.0, 20.0, 30.0)


class TestJsBlockToBlock:
    def test_solid_block(self) -> None:
        js_block = SimpleNamespace(
            name="stone",
            displayName="Stone",
            position=_mock_vec3(5.0, 60.0, 10.0),
            hardness=1.5,
            boundingBox="block",
            liquid=False,
        )
        block = js_block_to_block(js_block)
        assert block.name == "stone"
        assert block.display_name == "Stone"
        assert block.position == Vec3(5.0, 60.0, 10.0)
        assert block.hardness == 1.5
        assert block.is_solid is True
        assert block.is_liquid is False
        assert block.bounding_box == "block"

    def test_liquid_block(self) -> None:
        js_block = SimpleNamespace(
            name="water",
            displayName="Water",
            position=_mock_vec3(0.0, 62.0, 0.0),
            hardness=None,
            boundingBox="empty",
            liquid=True,
        )
        block = js_block_to_block(js_block)
        assert block.hardness is None
        assert block.is_solid is False
        assert block.is_liquid is True
        assert block.bounding_box == "empty"

    def test_no_liquid_attr(self) -> None:
        """Blocks without a 'liquid' attribute default to False."""
        js_block = SimpleNamespace(
            name="stone",
            displayName="Stone",
            position=_mock_vec3(0.0, 0.0, 0.0),
            hardness=1.5,
            boundingBox="block",
        )
        block = js_block_to_block(js_block)
        assert block.is_liquid is False


class TestJsEntityToEntity:
    def test_hostile_mob(self) -> None:
        js_entity = SimpleNamespace(
            id=42,
            name="zombie",
            type="hostile",
            position=_mock_vec3(10.0, 64.0, -5.0),
            velocity=_mock_vec3(0.0, 0.0, 0.0),
            health=20.0,
        )
        entity = js_entity_to_entity(js_entity)
        assert entity.id == 42
        assert entity.name == "zombie"
        assert entity.kind is EntityKind.HOSTILE
        assert entity.position == Vec3(10.0, 64.0, -5.0)
        assert entity.velocity == Vec3(0.0, 0.0, 0.0)
        assert entity.health == 20.0

    def test_player(self) -> None:
        js_entity = SimpleNamespace(
            id=1,
            username="Steve",
            type="player",
            position=_mock_vec3(0.0, 65.0, 0.0),
            velocity=None,
            health=None,
        )
        entity = js_entity_to_entity(js_entity)
        assert entity.name == "Steve"
        assert entity.kind is EntityKind.PLAYER
        assert entity.velocity is None
        assert entity.health is None

    def test_player_with_entity_name(self) -> None:
        """Player entities in mineflayer have name='player' AND username='Steve'.

        The marshaller must prefer username over the generic entity type name.
        """
        js_entity = SimpleNamespace(
            id=1,
            name="player",
            username="Steve",
            type="player",
            position=_mock_vec3(0.0, 65.0, 0.0),
            velocity=None,
            health=None,
        )
        entity = js_entity_to_entity(js_entity)
        assert entity.name == "Steve"
        assert entity.kind is EntityKind.PLAYER

    def test_unknown_type(self) -> None:
        js_entity = SimpleNamespace(
            id=99,
            name="something",
            type="unknown_type",
            position=_mock_vec3(0.0, 0.0, 0.0),
        )
        entity = js_entity_to_entity(js_entity)
        assert entity.kind is EntityKind.OTHER

    def test_no_type_attribute(self) -> None:
        js_entity = SimpleNamespace(
            id=5,
            name="mystery",
            position=_mock_vec3(0.0, 0.0, 0.0),
        )
        entity = js_entity_to_entity(js_entity)
        assert entity.kind is EntityKind.OTHER

    def test_no_name_or_username(self) -> None:
        js_entity = SimpleNamespace(
            id=10,
            type="object",
            position=_mock_vec3(0.0, 0.0, 0.0),
        )
        entity = js_entity_to_entity(js_entity)
        assert entity.name is None

    def test_metadata_dict(self) -> None:
        """Entity with dict-like metadata should be populated."""
        meta = SimpleNamespace()
        meta.valueOf = lambda: {"key": "value"}

        js_entity = SimpleNamespace(
            id=20,
            name="villager",
            type="mob",
            position=_mock_vec3(0.0, 0.0, 0.0),
            metadata=meta,
        )
        entity = js_entity_to_entity(js_entity)
        assert entity.metadata == {"key": "value"}

    def test_metadata_dict_like_proxy(self) -> None:
        """valueOf() returning a dict-like mapping (not a literal dict) should convert."""
        from collections import OrderedDict

        meta = SimpleNamespace()
        meta.valueOf = lambda: OrderedDict([("a", 1), ("b", 2)])

        js_entity = SimpleNamespace(
            id=21,
            name="cow",
            type="animal",
            position=_mock_vec3(0.0, 0.0, 0.0),
            metadata=meta,
        )
        entity = js_entity_to_entity(js_entity)
        assert entity.metadata == {"a": 1, "b": 2}

    def test_metadata_non_mapping_ignored(self) -> None:
        """Entity with non-mapping valueOf result should leave metadata as None."""
        meta = SimpleNamespace()
        meta.valueOf = lambda: [1, 2, 3]

        js_entity = SimpleNamespace(
            id=22,
            name="cow",
            type="animal",
            position=_mock_vec3(0.0, 0.0, 0.0),
            metadata=meta,
        )
        entity = js_entity_to_entity(js_entity)
        assert entity.metadata is None

    def test_metadata_no_valueof(self) -> None:
        """Entity without valueOf on metadata should leave metadata as None."""
        js_entity = SimpleNamespace(
            id=22,
            name="pig",
            type="animal",
            position=_mock_vec3(0.0, 0.0, 0.0),
            metadata="not_a_proxy",
        )
        entity = js_entity_to_entity(js_entity)
        assert entity.metadata is None


class TestJsItemToItemStack:
    def test_basic_item(self) -> None:
        js_item = SimpleNamespace(
            name="diamond_pickaxe",
            displayName="Diamond Pickaxe",
            count=1,
            slot=0,
            stackSize=1,
            enchants=None,
            nbt=None,
        )
        item = js_item_to_item_stack(js_item)
        assert item.name == "diamond_pickaxe"
        assert item.display_name == "Diamond Pickaxe"
        assert item.count == 1
        assert item.slot == 0
        assert item.max_stack_size == 1
        assert item.enchantments is None
        assert item.nbt is None

    def test_stackable_item(self) -> None:
        js_item = SimpleNamespace(
            name="cobblestone",
            displayName="Cobblestone",
            count=64,
            slot=5,
            stackSize=64,
            enchants=None,
            nbt=None,
        )
        item = js_item_to_item_stack(js_item)
        assert item.count == 64
        assert item.max_stack_size == 64

    def test_with_enchantments(self) -> None:
        enchant_list = [{"name": "efficiency", "level": 5}]
        js_enchants = SimpleNamespace()
        js_enchants.valueOf = lambda: enchant_list

        js_item = SimpleNamespace(
            name="diamond_pickaxe",
            displayName="Diamond Pickaxe",
            count=1,
            slot=0,
            stackSize=1,
            enchants=js_enchants,
            nbt=None,
        )
        item = js_item_to_item_stack(js_item)
        assert item.enchantments == enchant_list

    def test_with_nbt(self) -> None:
        nbt_data = {"Damage": 0}
        js_nbt = SimpleNamespace()
        js_nbt.valueOf = lambda: nbt_data

        js_item = SimpleNamespace(
            name="diamond_sword",
            displayName="Diamond Sword",
            count=1,
            slot=1,
            stackSize=1,
            enchants=None,
            nbt=js_nbt,
        )
        item = js_item_to_item_stack(js_item)
        assert item.nbt == nbt_data
