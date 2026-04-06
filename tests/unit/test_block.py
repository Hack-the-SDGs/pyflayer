import pytest
from minethon.models.block import Block
from minethon.models.vec3 import Vec3


class TestBlock:
    def test_creation(self) -> None:
        b = Block(
            name="oak_log",
            display_name="Oak Log",
            position=Vec3(10.0, 64.0, -5.0),
            hardness=2.0,
            is_solid=True,
            is_liquid=False,
            bounding_box="block",
        )
        assert b.name == "oak_log"
        assert b.display_name == "Oak Log"
        assert b.position == Vec3(10.0, 64.0, -5.0)
        assert b.hardness == 2.0
        assert b.is_solid is True
        assert b.is_liquid is False
        assert b.bounding_box == "block"

    def test_frozen(self) -> None:
        b = Block(
            name="stone",
            display_name="Stone",
            position=Vec3(0.0, 0.0, 0.0),
            hardness=1.5,
            is_solid=True,
            is_liquid=False,
            bounding_box="block",
        )
        with pytest.raises(AttributeError):
            b.name = "dirt"  # type: ignore[misc]

    def test_hardness_none_for_unbreakable(self) -> None:
        b = Block(
            name="bedrock",
            display_name="Bedrock",
            position=Vec3(0.0, 0.0, 0.0),
            hardness=None,
            is_solid=True,
            is_liquid=False,
            bounding_box="block",
        )
        assert b.hardness is None

    def test_liquid_block(self) -> None:
        b = Block(
            name="water",
            display_name="Water",
            position=Vec3(5.0, 62.0, 5.0),
            hardness=None,
            is_solid=False,
            is_liquid=True,
            bounding_box="empty",
        )
        assert b.is_liquid is True
        assert b.is_solid is False
        assert b.bounding_box == "empty"

    def test_equality(self) -> None:
        pos = Vec3(1.0, 2.0, 3.0)
        a = Block("stone", "Stone", pos, 1.5, True, False, "block")
        b = Block("stone", "Stone", pos, 1.5, True, False, "block")
        assert a == b
