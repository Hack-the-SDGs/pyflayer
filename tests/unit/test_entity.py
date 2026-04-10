import pytest

from minethon.models.entity import Entity, EntityKind
from minethon.models.vec3 import Vec3


class TestEntityKind:
    def test_values(self) -> None:
        assert EntityKind.PLAYER.value == "player"
        assert EntityKind.HOSTILE.value == "hostile"
        assert EntityKind.OTHER.value == "other"

    def test_from_value(self) -> None:
        assert EntityKind("mob") is EntityKind.MOB


class TestEntity:
    def test_creation_minimal(self) -> None:
        e = Entity(
            id=42,
            name="zombie",
            kind=EntityKind.HOSTILE,
            position=Vec3(10.0, 64.0, -5.0),
        )
        assert e.id == 42
        assert e.name == "zombie"
        assert e.kind is EntityKind.HOSTILE
        assert e.position == Vec3(10.0, 64.0, -5.0)
        assert e.velocity is None
        assert e.health is None
        assert e.metadata is None

    def test_creation_full(self) -> None:
        e = Entity(
            id=1,
            name="Steve",
            kind=EntityKind.PLAYER,
            position=Vec3(0.0, 65.0, 0.0),
            velocity=Vec3(0.1, 0.0, -0.1),
            health=20.0,
            metadata={"skin": "default"},
        )
        assert e.velocity == Vec3(0.1, 0.0, -0.1)
        assert e.health == 20.0
        assert e.metadata == {"skin": "default"}

    def test_frozen(self) -> None:
        e = Entity(
            id=1,
            name="zombie",
            kind=EntityKind.HOSTILE,
            position=Vec3(0.0, 0.0, 0.0),
        )
        with pytest.raises(AttributeError):
            e.id = 99  # type: ignore[misc]

    def test_name_none(self) -> None:
        e = Entity(
            id=5,
            name=None,
            kind=EntityKind.OTHER,
            position=Vec3(0.0, 0.0, 0.0),
        )
        assert e.name is None
