"""
Elevation configuration and noise-based generation for map terrain.

Consolidates ElevationConfig, TerrainPresets, and ElevationGenerator.
"""

import logging
from dataclasses import dataclass, field
from typing import List

import numpy as np
from opensimplex import OpenSimplex

logger = logging.getLogger(__name__)


# =============================================================================
# Configuration
# =============================================================================

def _elev_default(key):
    """Return a default_factory that reads a single elevation default from config."""
    def factory():
        from imperial_generals.config import get_config
        return get_config()['map']['elevation_defaults'][key]
    return factory


@dataclass
class ElevationConfig:
    """
    Configuration parameters for elevation generation using fractal noise.

    Attributes:
        seed (int): Random seed for deterministic generation.
        octaves (int): Number of noise layers (1–8).
        persistence (float): Amplitude decay per octave (0.0–1.0).
        lacunarity (float): Frequency multiplier per octave (1.5–4.0).
        scale (float): Overall feature size in map units (> 0).
        base_elevation (float): Starting elevation before noise is applied.
        elevation_range (float): Total elevation span (>= 0).
        exponent (float): Power applied to normalized noise (> 0).
    """

    seed: int              = field(default_factory=_elev_default('seed'))
    octaves: int           = field(default_factory=_elev_default('octaves'))
    persistence: float     = field(default_factory=_elev_default('persistence'))
    lacunarity: float      = field(default_factory=_elev_default('lacunarity'))
    scale: float           = field(default_factory=_elev_default('scale'))
    base_elevation: float  = field(default_factory=_elev_default('base_elevation'))
    elevation_range: float = field(default_factory=_elev_default('elevation_range'))
    exponent: float        = field(default_factory=_elev_default('exponent'))

    def __post_init__(self):
        if not 1 <= self.octaves <= 8:
            raise ValueError(f"octaves must be between 1 and 8, got {self.octaves}")
        if not 0.0 <= self.persistence <= 1.0:
            raise ValueError(f"persistence must be between 0 and 1, got {self.persistence}")
        if not 1.5 <= self.lacunarity <= 4.0:
            raise ValueError(f"lacunarity must be between 1.5 and 4.0, got {self.lacunarity}")
        if self.scale <= 0:
            raise ValueError(f"scale must be positive, got {self.scale}")
        if self.elevation_range < 0:
            raise ValueError(f"elevation_range must be non-negative, got {self.elevation_range}")
        if self.exponent <= 0:
            raise ValueError(f"exponent must be positive, got {self.exponent}")


class TerrainPresets:
    """
    Predefined ElevationConfigs for common terrain types.
    All parameters are loaded from simulation.yaml.

    Usage:
        config = TerrainPresets.mountains(seed=12345)
        config = TerrainPresets.hills()
    """

    @staticmethod
    def _from_config(preset_name: str, seed: int) -> ElevationConfig:
        from imperial_generals.config import get_config
        params = get_config()['map']['terrain_presets'][preset_name]
        return ElevationConfig(seed=seed, **params)

    @staticmethod
    def flat(seed: int = 12345) -> ElevationConfig:
        return TerrainPresets._from_config('flat', seed)

    @staticmethod
    def hills(seed: int = 12345) -> ElevationConfig:
        return TerrainPresets._from_config('hills', seed)

    @staticmethod
    def mountains(seed: int = 12345) -> ElevationConfig:
        return TerrainPresets._from_config('mountains', seed)

    @staticmethod
    def coastal(seed: int = 12345) -> ElevationConfig:
        return TerrainPresets._from_config('coastal', seed)

    @staticmethod
    def forest(seed: int = 12345) -> ElevationConfig:
        return TerrainPresets._from_config('forest', seed)

    @staticmethod
    def badlands(seed: int = 12345) -> ElevationConfig:
        return TerrainPresets._from_config('badlands', seed)


# =============================================================================
# Generator
# =============================================================================

class ElevationGenerator:
    """
    Generates elevation values using fractal Brownian motion (fBm) over OpenSimplex noise.
    """

    def __init__(self, config: ElevationConfig) -> None:
        if not isinstance(config, ElevationConfig):
            raise TypeError("config must be an ElevationConfig instance")
        self.config = config
        self.noise = OpenSimplex(seed=config.seed)
        logger.info(f"Initialized ElevationGenerator with seed={config.seed}")

    def _fbm_noise(self, x: float, y: float) -> float:
        total = 0.0
        frequency = 1.0
        amplitude = 1.0
        max_value = 0.0

        for _ in range(self.config.octaves):
            sample_x = x * frequency / self.config.scale
            sample_y = y * frequency / self.config.scale
            total += self.noise.noise2(sample_x, sample_y) * amplitude
            max_value += amplitude
            amplitude *= self.config.persistence
            frequency *= self.config.lacunarity

        return total / max_value if max_value > 0 else 0.0

    def generate_elevation(self, x: float, y: float) -> float:
        noise_val = self._fbm_noise(x, y)
        normalized = (noise_val + 1.0) / 2.0
        shaped = normalized ** self.config.exponent
        return self.config.base_elevation + (shaped - 0.5) * self.config.elevation_range

    def apply_to_cells(self, cells) -> None:
        if not cells:
            logger.warning("No cells provided to apply_to_cells")
            return
        logger.info(f"Generating elevation for {len(cells)} cells...")
        for cell in cells:
            x, y = cell.center
            cell.set_elevation(self.generate_elevation(x, y))
        elevations = [cell.elevation for cell in cells]
        logger.info(
            f"Elevation complete. Range: [{min(elevations):.2f}, {max(elevations):.2f}], "
            f"Avg: {sum(elevations)/len(elevations):.2f}"
        )

    def generate_elevation_array(self, width: int, height: int,
                                  resolution: int = 1) -> np.ndarray:
        rows = height // resolution
        cols = width // resolution
        arr = np.zeros((rows, cols))
        for i in range(rows):
            for j in range(cols):
                arr[i, j] = self.generate_elevation(j * resolution, i * resolution)
        return arr

    def __str__(self) -> str:
        return (f"ElevationGenerator(seed={self.config.seed}, "
                f"octaves={self.config.octaves}, scale={self.config.scale})")

    def __repr__(self) -> str:
        return f"<ElevationGenerator(config={self.config!r})>"


if __name__ == "__main__":  # pragma: no cover
    import logging as _logging
    _logging.basicConfig(level=_logging.INFO)
    for name, cfg in [("Hills", TerrainPresets.hills(42)), ("Mountains", TerrainPresets.mountains(42))]:
        print(f"\n{name}:")
        gen = ElevationGenerator(cfg)
        for x, y in [(0, 0), (25, 25), (50, 50)]:
            print(f"  ({x},{y}): {gen.generate_elevation(x, y):.2f}")
