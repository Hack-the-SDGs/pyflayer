import pytest
from pyflayer.models.vec3 import Vec3


class TestVec3:
    def test_creation(self) -> None:
        v = Vec3(1.0, 2.0, 3.0)
        assert v.x == 1.0
        assert v.y == 2.0
        assert v.z == 3.0

    def test_frozen(self) -> None:
        v = Vec3(1.0, 2.0, 3.0)
        with pytest.raises(AttributeError):
            v.x = 5.0  # type: ignore[misc]

    def test_add(self) -> None:
        a = Vec3(1.0, 2.0, 3.0)
        b = Vec3(4.0, 5.0, 6.0)
        assert a + b == Vec3(5.0, 7.0, 9.0)

    def test_sub(self) -> None:
        a = Vec3(4.0, 5.0, 6.0)
        b = Vec3(1.0, 2.0, 3.0)
        assert a - b == Vec3(3.0, 3.0, 3.0)

    def test_distance_to(self) -> None:
        a = Vec3(0.0, 0.0, 0.0)
        b = Vec3(3.0, 4.0, 0.0)
        assert a.distance_to(b) == 5.0

    def test_offset(self) -> None:
        v = Vec3(1.0, 2.0, 3.0)
        assert v.offset(10.0, 20.0, 30.0) == Vec3(11.0, 22.0, 33.0)

    def test_floored(self) -> None:
        v = Vec3(1.7, -2.3, 3.9)
        assert v.floored() == Vec3(1.0, -3.0, 3.0)

    def test_equality(self) -> None:
        assert Vec3(1.0, 2.0, 3.0) == Vec3(1.0, 2.0, 3.0)
        assert Vec3(1.0, 2.0, 3.0) != Vec3(1.0, 2.0, 4.0)
