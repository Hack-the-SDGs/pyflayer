"""3D vector type for positions and directions."""

import math
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Vec3:
    """An immutable 3D vector."""

    x: float
    y: float
    z: float

    def distance_to(self, other: Vec3) -> float:
        """Euclidean distance to another vector."""
        return math.sqrt(
            (self.x - other.x) ** 2 + (self.y - other.y) ** 2 + (self.z - other.z) ** 2
        )

    def offset(self, dx: float, dy: float, dz: float) -> Vec3:
        """Return a new vector offset by (dx, dy, dz)."""
        return Vec3(self.x + dx, self.y + dy, self.z + dz)

    def floored(self) -> Vec3:
        """Return a new vector with each component floored."""
        return Vec3(
            float(math.floor(self.x)),
            float(math.floor(self.y)),
            float(math.floor(self.z)),
        )

    def __add__(self, other: Vec3) -> Vec3:
        return Vec3(self.x + other.x, self.y + other.y, self.z + other.z)

    def __sub__(self, other: Vec3) -> Vec3:
        return Vec3(self.x - other.x, self.y - other.y, self.z - other.z)
