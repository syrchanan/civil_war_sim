"""
Cell class representing a single Voronoi cell with associated metadata.
"""

from typing import Tuple, Optional
from shapely.geometry import Polygon
import logging

logger = logging.getLogger(__name__)


class Cell:
    """
    Represents a single map cell (Voronoi polygon) with metadata.

    Attributes:
        index (int): Unique identifier for this cell.
        center (Tuple[float, float]): (x, y) coordinates of the cell center point.
        polygon (Polygon): Shapely polygon representing the cell boundaries.
        elevation (float): Elevation value for this cell (default 0.0).
        terrain_type (str): Type of terrain ('open', 'forest', 'hill', 'water', etc.).
        cover_value (float): Cover/concealment value, range [0.0, 1.0]. 0 = no cover, 1 = full cover.
    """

    def __init__(
        self,
        index: int,
        center: Tuple[float, float],
        polygon: Polygon,
        elevation: float = 0.0,
        terrain_type: str = 'open',
        cover_value: float = 0.0
    ) -> None:
        """
        Initialize a Cell.

        Args:
            index (int): Unique identifier for this cell.
            center (Tuple[float, float]): (x, y) center coordinates.
            polygon (Polygon): Shapely polygon for the cell.
            elevation (float): Elevation value (default 0.0).
            terrain_type (str): Terrain type (default 'open').
            cover_value (float): Cover value in [0.0, 1.0] (default 0.0).
        """
        if not isinstance(index, int):
            raise TypeError("index must be an int")
        if not isinstance(center, tuple) or len(center) != 2:
            raise TypeError("center must be a tuple of (x, y)")
        if not isinstance(polygon, Polygon):
            raise TypeError("polygon must be a Shapely Polygon")
        if not isinstance(elevation, (int, float)):
            raise TypeError("elevation must be a number")
        if not isinstance(terrain_type, str):
            raise TypeError("terrain_type must be a string")
        if not isinstance(cover_value, (int, float)) or not (0.0 <= cover_value <= 1.0):
            raise ValueError("cover_value must be a number in [0.0, 1.0]")

        self.index: int = index
        self.center: Tuple[float, float] = center
        self.polygon: Polygon = polygon
        self.elevation: float = float(elevation)
        self.terrain_type: str = terrain_type
        self.cover_value: float = float(cover_value)

        logger.debug(f"Created Cell {index} at {center} with terrain={terrain_type}")

    def set_elevation(self, elevation: float) -> None:
        """
        Set the elevation value for this cell.

        Args:
            elevation (float): New elevation value.
        """
        if not isinstance(elevation, (int, float)):
            raise TypeError("elevation must be a number")
        self.elevation = float(elevation)

    def set_terrain_type(self, terrain_type: str) -> None:
        """
        Set the terrain type for this cell.

        Args:
            terrain_type (str): New terrain type.
        """
        if not isinstance(terrain_type, str):
            raise TypeError("terrain_type must be a string")
        self.terrain_type = terrain_type

    def set_cover_value(self, cover_value: float) -> None:
        """
        Set the cover value for this cell.

        Args:
            cover_value (float): New cover value in [0.0, 1.0].
        """
        if not isinstance(cover_value, (int, float)) or not (0.0 <= cover_value <= 1.0):
            raise ValueError("cover_value must be a number in [0.0, 1.0]")
        self.cover_value = float(cover_value)

    def distance_to(self, other: 'Cell') -> float:
        """
        Calculate center-to-center distance to another cell.

        Args:
            other (Cell): Another Cell instance.

        Returns:
            float: Euclidean distance between cell centers.
        """
        if not isinstance(other, Cell):
            raise TypeError("other must be a Cell instance")
        dx = self.center[0] - other.center[0]
        dy = self.center[1] - other.center[1]
        return (dx**2 + dy**2)**0.5

    def __str__(self) -> str:
        """String representation of Cell."""
        return (
            f"Cell(index={self.index}, center={self.center}, "
            f"terrain={self.terrain_type}, elevation={self.elevation:.2f})"
        )

    def __repr__(self) -> str:
        """Detailed representation of Cell."""
        return (
            f"<Cell(index={self.index}, center={self.center}, polygon={self.polygon!r}, "
            f"elevation={self.elevation}, terrain_type={self.terrain_type!r}, "
            f"cover_value={self.cover_value})>"
        )


if __name__ == "__main__":  # pragma: no cover
    # Example usage
    from shapely.geometry import box

    poly = box(0, 0, 10, 10)
    cell = Cell(index=0, center=(5.0, 5.0), polygon=poly, elevation=10.5, terrain_type='forest')
    print(cell)

    cell.set_cover_value(0.7)
    print(f"Cover value: {cell.cover_value}")
