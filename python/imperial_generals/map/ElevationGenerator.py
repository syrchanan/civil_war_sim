"""
Elevation generation using OpenSimplex noise with fractal Brownian motion (fBm).
"""

import logging
from typing import List, Tuple
import numpy as np
from opensimplex import OpenSimplex

from imperial_generals.map.ElevationConfig import ElevationConfig
from imperial_generals.map.Cell import Cell

logger = logging.getLogger(__name__)


class ElevationGenerator:
    """
    Generates elevation values for map cells using fractal Brownian motion (fBm).

    Uses OpenSimplex noise layered at multiple octaves to create realistic terrain.
    Supports deterministic generation via seeds and customizable terrain characteristics.
    """

    def __init__(self, config: ElevationConfig) -> None:
        """
        Initialize the elevation generator.

        Args:
            config (ElevationConfig): Configuration parameters for elevation generation.
        """
        if not isinstance(config, ElevationConfig):
            raise TypeError("config must be an ElevationConfig instance")

        self.config = config
        self.noise = OpenSimplex(seed=config.seed)
        logger.info(f"Initialized ElevationGenerator with seed={config.seed}")

    def _fbm_noise(self, x: float, y: float) -> float:
        """
        Generate fractal Brownian motion (fBm) noise at given coordinates.

        Combines multiple octaves of noise with decreasing amplitude and increasing frequency
        to create natural-looking terrain with detail at multiple scales.

        Args:
            x (float): X coordinate.
            y (float): Y coordinate.

        Returns:
            float: Noise value in range [-1, 1] (approximately).
        """
        total = 0.0
        frequency = 1.0
        amplitude = 1.0
        max_value = 0.0  # Used for normalizing

        for octave in range(self.config.octaves):
            # Scale coordinates by frequency and divide by scale
            sample_x = x * frequency / self.config.scale
            sample_y = y * frequency / self.config.scale

            # Get noise value for this octave
            noise_val = self.noise.noise2(sample_x, sample_y)

            # Accumulate
            total += noise_val * amplitude
            max_value += amplitude

            # Prepare for next octave
            amplitude *= self.config.persistence
            frequency *= self.config.lacunarity

        # Normalize to [-1, 1]
        return total / max_value if max_value > 0 else 0.0

    def generate_elevation(self, x: float, y: float) -> float:
        """
        Generate elevation value at given coordinates.

        Args:
            x (float): X coordinate.
            y (float): Y coordinate.

        Returns:
            float: Elevation value.
        """
        # Get fBm noise in range [-1, 1]
        noise_val = self._fbm_noise(x, y)

        # Normalize to [0, 1]
        normalized = (noise_val + 1.0) / 2.0

        # Apply exponent for terrain shaping
        shaped = normalized ** self.config.exponent

        # Scale to elevation range and add base
        elevation = self.config.base_elevation + (shaped - 0.5) * self.config.elevation_range

        return elevation

    def apply_to_cells(self, cells: List[Cell]) -> None:
        """
        Apply elevation generation to a list of cells.

        Args:
            cells (List[Cell]): List of Cell objects to update with elevation values.
        """
        if not cells:
            logger.warning("No cells provided to apply_to_cells")
            return

        logger.info(f"Generating elevation for {len(cells)} cells...")

        for cell in cells:
            x, y = cell.center
            elevation = self.generate_elevation(x, y)
            cell.set_elevation(elevation)

        # Log statistics
        elevations = [cell.elevation for cell in cells]
        min_elev = min(elevations)
        max_elev = max(elevations)
        avg_elev = sum(elevations) / len(elevations)

        logger.info(
            f"Elevation generation complete. "
            f"Range: [{min_elev:.2f}, {max_elev:.2f}], "
            f"Average: {avg_elev:.2f}"
        )

    def generate_elevation_array(
        self,
        width: int,
        height: int,
        resolution: int = 1
    ) -> np.ndarray:
        """
        Generate a 2D elevation array for visualization or analysis.

        Args:
            width (int): Width of the map.
            height (int): Height of the map.
            resolution (int): Sampling resolution (1 = every unit, 2 = every other unit, etc.).

        Returns:
            np.ndarray: 2D array of elevation values.
        """
        rows = height // resolution
        cols = width // resolution

        elevation_map = np.zeros((rows, cols))

        for i in range(rows):
            for j in range(cols):
                x = j * resolution
                y = i * resolution
                elevation_map[i, j] = self.generate_elevation(x, y)

        return elevation_map

    def __str__(self) -> str:
        """String representation."""
        return (
            f"ElevationGenerator(seed={self.config.seed}, "
            f"octaves={self.config.octaves}, "
            f"scale={self.config.scale})"
        )

    def __repr__(self) -> str:
        """Detailed representation."""
        return f"<ElevationGenerator(config={self.config!r})>"


if __name__ == "__main__":
    # Example usage
    from imperial_generals.map.ElevationConfig import TerrainPresets

    logging.basicConfig(level=logging.INFO)

    print("=== ElevationGenerator Demo ===\n")

    # Test different presets
    presets = [
        ("Hills", TerrainPresets.hills(seed=42)),
        ("Mountains", TerrainPresets.mountains(seed=42)),
    ]

    for name, config in presets:
        print(f"\n{name} Preset:")
        gen = ElevationGenerator(config)

        # Sample some points
        test_points = [(0, 0), (25, 25), (50, 50), (75, 75)]
        print(f"  Sample elevations at various points:")
        for x, y in test_points:
            elev = gen.generate_elevation(x, y)
            print(f"    ({x:3}, {y:3}): {elev:6.2f}")
