import math


class Position:
    """
    Positional data for a unit on the battlefield.

    Parameters
    ----------
    x : float
        X map coordinate.
    y : float
        Y map coordinate.
    z : float
        Elevation.
    cover : float
        Cover percentage, must be in [0.0, 1.0].
    terrain_type : str
        Terrain type, must be one of VALID_TERRAIN_TYPES.
    """

    # TODO: replace this hardcoded set with values derived from the biome/terrain
    # system (TerrainZone / BiomePresets) once the map module is hooked up.
    VALID_TERRAIN_TYPES: frozenset[str] = frozenset({
        'open',
        'forest',
        'hill',
        'swamp',
        'road',
        'urban',
        'water',
    })

    def __init__(self, x: float, y: float, z: float, cover: float, terrain_type: str) -> None:
        if not (0.0 <= cover <= 1.0):
            raise ValueError(f"cover must be between 0.0 and 1.0, got {cover}.")
        if terrain_type not in self.VALID_TERRAIN_TYPES:
            raise ValueError(
                f"terrain_type '{terrain_type}' is not valid. "
                f"Must be one of: {sorted(self.VALID_TERRAIN_TYPES)}."
            )
        self.x = x
        self.y = y
        self.z = z
        self.cover = cover
        self.terrain_type = terrain_type

    def flat_distance_to(self, other: 'Position') -> float:
        """Euclidean distance on the x/y plane, ignoring elevation."""
        return math.sqrt((self.x - other.x) ** 2 + (self.y - other.y) ** 2)

    def true_distance_to(self, other: 'Position') -> float:
        """Euclidean distance in 3D space, including elevation."""
        return math.sqrt(
            (self.x - other.x) ** 2
            + (self.y - other.y) ** 2
            + (self.z - other.z) ** 2
        )

    def elevation_difference_to(self, other: 'Position') -> float:
        """Signed elevation difference: other.z - self.z (positive means other is higher)."""
        return other.z - self.z

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Position):
            return NotImplemented
        return (
            self.x == other.x
            and self.y == other.y
            and self.z == other.z
            and self.cover == other.cover
            and self.terrain_type == other.terrain_type
        )

    def __str__(self) -> str:
        return (
            f"Position: ({self.x}, {self.y}) | "
            f"Elevation={self.z} | "
            f"Cover={self.cover:.0%} | "
            f"Terrain={self.terrain_type}"
        )

    def __repr__(self) -> str:
        return (
            f"Position(x={self.x!r}, y={self.y!r}, z={self.z!r}, "
            f"cover={self.cover!r}, terrain_type={self.terrain_type!r})"
        )

    @classmethod
    def from_dict(cls, d: dict) -> 'Position':
        return cls(
            x=d['x'], y=d['y'], z=d['z'],
            cover=d['cover'], terrain_type=d['terrain_type'],
        )
