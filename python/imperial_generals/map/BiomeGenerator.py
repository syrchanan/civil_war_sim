"""
Biome generation for multi-terrain maps using noise-based zone distribution.
"""

import logging
from typing import List, Dict
import numpy as np
from opensimplex import OpenSimplex

from imperial_generals.map.TerrainZone import BiomeMapConfig, TerrainZone
from imperial_generals.map.ElevationGenerator import ElevationGenerator
from imperial_generals.map.Cell import Cell

logger = logging.getLogger(__name__)


class BiomeGenerator:
    """
    Generates terrain biomes/zones using noise for natural clustering.

    Uses OpenSimplex noise to create continuous zones across the map, then assigns
    cells to zones based on their position's noise value and the configured percentages.
    """

    def __init__(self, config: BiomeMapConfig) -> None:
        """
        Initialize the biome generator.

        Args:
            config (BiomeMapConfig): Configuration for biome distribution.
        """
        if not isinstance(config, BiomeMapConfig):
            raise TypeError("config must be a BiomeMapConfig instance")

        self.config = config
        self.zone_noise = OpenSimplex(seed=config.seed)
        self.elevation_generators: Dict[str, ElevationGenerator] = {}

        # Create elevation generators for each zone
        for zone in config.zones:
            self.elevation_generators[zone.name] = ElevationGenerator(zone.elevation_config)

        logger.info(f"Initialized BiomeGenerator with {len(config.zones)} zones, seed={config.seed}")

    def _get_zone_noise_value(self, x: float, y: float) -> float:
        """
        Get normalized noise value for zone assignment at given position.

        Args:
            x (float): X coordinate.
            y (float): Y coordinate.

        Returns:
            float: Noise value in range [0, 1].
        """
        # Sample noise at scaled coordinates
        noise_val = self.zone_noise.noise2(x / self.config.zone_scale, y / self.config.zone_scale)
        # Normalize from [-1, 1] to [0, 1]
        return (noise_val + 1.0) / 2.0

    def _assign_zone(self, noise_value: float) -> TerrainZone:
        """
        Assign a zone based on noise value and configured percentages.

        Uses cumulative percentage thresholds to map noise values to zones.

        Args:
            noise_value (float): Normalized noise value [0, 1].

        Returns:
            TerrainZone: The assigned zone.
        """
        cumulative = 0.0
        for zone in self.config.zones:
            cumulative += zone.percentage
            if noise_value <= cumulative:
                return zone

        # Fallback to last zone (handles floating point rounding)
        return self.config.zones[-1]

    def apply_to_cells(self, cells: List[Cell]) -> Dict[str, int]:
        """
        Apply biome generation to a list of cells.

        Assigns each cell to a zone, then applies elevation, terrain type, and cover value.

        Args:
            cells (List[Cell]): List of Cell objects to update.

        Returns:
            Dict[str, int]: Statistics showing cell count per zone.
        """
        if not cells:
            logger.warning("No cells provided to apply_to_cells")
            return {}

        logger.info(f"Generating biomes for {len(cells)} cells...")

        zone_counts: Dict[str, int] = {zone.name: 0 for zone in self.config.zones}
        cell_zones: Dict[int, TerrainZone] = {}

        # Phase 1: Assign zones based on noise
        for cell in cells:
            x, y = cell.center
            noise_val = self._get_zone_noise_value(x, y)
            zone = self._assign_zone(noise_val)

            cell_zones[cell.index] = zone
            zone_counts[zone.name] += 1

        # Phase 2: Apply zone characteristics
        for cell in cells:
            zone = cell_zones[cell.index]

            # Generate elevation for this cell using the zone's generator
            x, y = cell.center
            elevation = self.elevation_generators[zone.name].generate_elevation(x, y)
            cell.set_elevation(elevation)

            # Apply terrain type and cover value
            cell.set_terrain_type(zone.terrain_type)
            cell.set_cover_value(zone.cover_value)

        # Log statistics
        logger.info("Biome generation complete. Distribution:")
        for zone_name, count in zone_counts.items():
            percentage = (count / len(cells)) * 100
            logger.info(f"  {zone_name}: {count} cells ({percentage:.1f}%)")

        return zone_counts

    def get_zone_at_position(self, x: float, y: float) -> TerrainZone:
        """
        Get the terrain zone at a specific position.

        Args:
            x (float): X coordinate.
            y (float): Y coordinate.

        Returns:
            TerrainZone: The zone at this position.
        """
        noise_val = self._get_zone_noise_value(x, y)
        return self._assign_zone(noise_val)

    def generate_zone_map_array(self, width: int, height: int, resolution: int = 1) -> np.ndarray:
        """
        Generate a 2D array showing zone assignments for visualization.

        Args:
            width (int): Width of the map.
            height (int): Height of the map.
            resolution (int): Sampling resolution.

        Returns:
            np.ndarray: 2D array of zone indices.
        """
        rows = height // resolution
        cols = width // resolution

        zone_map = np.zeros((rows, cols), dtype=int)

        for i in range(rows):
            for j in range(cols):
                x = j * resolution
                y = i * resolution
                noise_val = self._get_zone_noise_value(x, y)
                zone = self._assign_zone(noise_val)
                # Find zone index
                zone_idx = next(idx for idx, z in enumerate(self.config.zones) if z.name == zone.name)
                zone_map[i, j] = zone_idx

        return zone_map

    def __str__(self) -> str:
        """String representation."""
        zone_names = [z.name for z in self.config.zones]
        return f"BiomeGenerator(zones={zone_names}, seed={self.config.seed})"

    def __repr__(self) -> str:
        """Detailed representation."""
        return f"<BiomeGenerator(config={self.config!r})>"


if __name__ == "__main__":
    # Example usage
    from imperial_generals.map.TerrainZone import BiomePresets
    from shapely.geometry import box

    logging.basicConfig(level=logging.INFO)

    print("=== BiomeGenerator Demo ===\n")

    # Test with mixed battlefield preset
    config = BiomePresets.mixed_battlefield(seed=42)
    gen = BiomeGenerator(config)

    print(f"Generator: {gen}\n")

    # Create some test cells
    cells = []
    for i in range(20):
        for j in range(20):
            x, y = i * 5, j * 5
            poly = box(x, y, x + 5, y + 5)
            cell = Cell(index=len(cells), center=(x + 2.5, y + 2.5), polygon=poly)
            cells.append(cell)

    # Apply biomes
    zone_counts = gen.apply_to_cells(cells)

    print("\nZone distribution:")
    for zone_name, count in zone_counts.items():
        percentage = (count / len(cells)) * 100
        print(f"  {zone_name}: {count}/{len(cells)} cells ({percentage:.1f}%)")

    # Sample some cells
    print("\nSample cells:")
    for i in range(min(5, len(cells))):
        cell = cells[i * 80]  # Sample every 80th cell
        print(f"  Cell {cell.index}: "
              f"terrain={cell.terrain_type}, "
              f"elevation={cell.elevation:.1f}, "
              f"cover={cell.cover_value}")
