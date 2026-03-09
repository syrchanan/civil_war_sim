"""
Terrain zone configuration and noise-based biome generation.

Consolidates TerrainZone, BiomeMapConfig, BiomePresets, and BiomeGenerator.
"""

import logging
from dataclasses import dataclass, field
from typing import List, Dict

import numpy as np
from opensimplex import OpenSimplex

from imperial_generals.map.elevation import ElevationConfig, ElevationGenerator

logger = logging.getLogger(__name__)


# =============================================================================
# Configuration
# =============================================================================

def _biome_default(key):
    """Return a default_factory that reads a single biome default from config."""
    def factory():
        from imperial_generals.config import get_config
        return get_config()['map']['biome_defaults'][key]
    return factory


@dataclass
class TerrainZone:
    """
    Defines a terrain zone/biome with its characteristics.

    Attributes:
        name (str): Display name (e.g. "Mountains", "Farmland").
        percentage (float): Target fraction of map to cover (0.0–1.0).
        elevation_config (ElevationConfig): Elevation parameters for this zone.
        terrain_type (str): Terrain classification for cells in this zone.
        cover_value (float): Default cover value for cells (0.0–1.0).
        no_blend (bool): If True, cells near this zone's boundary are never blended.
    """
    name: str
    percentage: float
    elevation_config: ElevationConfig
    terrain_type: str = 'open'
    cover_value: float = 0.0
    no_blend: bool = False

    def __post_init__(self):
        if not isinstance(self.name, str) or not self.name:
            raise ValueError("name must be a non-empty string")
        if not 0.0 <= self.percentage <= 1.0:
            raise ValueError(f"percentage must be between 0 and 1, got {self.percentage}")
        if not isinstance(self.elevation_config, ElevationConfig):
            raise TypeError("elevation_config must be an ElevationConfig instance")
        if not isinstance(self.terrain_type, str):
            raise TypeError("terrain_type must be a string")
        if not 0.0 <= self.cover_value <= 1.0:
            raise ValueError(f"cover_value must be between 0 and 1, got {self.cover_value}")
        if not isinstance(self.no_blend, bool):
            raise TypeError(f"no_blend must be a bool, got {type(self.no_blend).__name__}")


@dataclass
class BiomeMapConfig:
    """
    Configuration for generating maps with multiple terrain zones.

    Attributes:
        zones (List[TerrainZone]): Terrain zones to distribute across the map.
        seed (int): Random seed for deterministic zone distribution.
        zone_scale (float): Scale of zone noise — larger = bigger zone blobs.
        blend_zones (bool): Whether to blend elevation at zone boundaries.
        blend_distance (float): Distance (map units) over which to blend zones.
    """
    zones: List[TerrainZone]
    seed: int              = field(default_factory=_biome_default('seed'))
    zone_scale: float      = field(default_factory=_biome_default('zone_scale'))
    blend_zones: bool      = field(default_factory=_biome_default('blend_zones'))
    blend_distance: float  = field(default_factory=_biome_default('blend_distance'))

    def __post_init__(self):
        if not self.zones:
            raise ValueError("zones list cannot be empty")
        if not all(isinstance(z, TerrainZone) for z in self.zones):
            raise TypeError("All zones must be TerrainZone instances")
        total = sum(z.percentage for z in self.zones)
        if not (0.99 <= total <= 1.01):
            raise ValueError(
                f"Zone percentages must sum to 1.0, got {total:.3f}. "
                f"Current: {', '.join(f'{z.name}={z.percentage:.2%}' for z in self.zones)}"
            )
        if self.zone_scale <= 0:
            raise ValueError(f"zone_scale must be positive, got {self.zone_scale}")
        if self.blend_distance < 0:
            raise ValueError(f"blend_distance must be non-negative, got {self.blend_distance}")


class BiomePresets:
    """
    Predefined biome configurations. All zone data is loaded from simulation.yaml.

    Usage:
        config = BiomePresets.mixed_battlefield(seed=42)
        config = BiomePresets.mountainous_region()
    """

    @staticmethod
    def _from_config(preset_name: str, seed: int) -> BiomeMapConfig:
        from imperial_generals.config import get_config
        cfg = get_config()
        preset_data    = cfg['map']['biome_presets'][preset_name]
        terrain_params = cfg['map']['terrain_presets']
        zones = [
            TerrainZone(
                name=z['name'],
                percentage=z['percentage'],
                elevation_config=ElevationConfig(seed=seed, **terrain_params[z['terrain_preset']]),
                terrain_type=z['terrain_type'],
                cover_value=z['cover_value'],
                no_blend=z.get('no_blend', False),
            )
            for z in preset_data['zones']
        ]
        return BiomeMapConfig(seed=seed, zone_scale=preset_data['zone_scale'], zones=zones)

    @staticmethod
    def mixed_battlefield(seed: int = 12345) -> BiomeMapConfig:
        """Balanced battlefield with varied terrain."""
        return BiomePresets._from_config('mixed_battlefield', seed)

    @staticmethod
    def mountainous_region(seed: int = 12345) -> BiomeMapConfig:
        """Primarily mountainous with some valleys."""
        return BiomePresets._from_config('mountainous_region', seed)

    @staticmethod
    def coastal_landing(seed: int = 12345) -> BiomeMapConfig:
        """Coastal terrain with beaches and inland areas."""
        return BiomePresets._from_config('coastal_landing', seed)

    @staticmethod
    def open_plains(seed: int = 12345) -> BiomeMapConfig:
        """Mostly flat terrain with minimal cover."""
        return BiomePresets._from_config('open_plains', seed)

    @staticmethod
    def cliffs_and_valleys(seed: int = 12345) -> BiomeMapConfig:
        """Dramatic cliff faces with flat valleys and rolling hills."""
        return BiomePresets._from_config('cliffs_and_valleys', seed)

    @staticmethod
    def custom(zones: List[TerrainZone], seed: int = 12345,
               zone_scale: float = 70.0) -> BiomeMapConfig:
        """Create a custom biome configuration."""
        return BiomeMapConfig(seed=seed, zone_scale=zone_scale, zones=zones)


# =============================================================================
# Generator
# =============================================================================

class BiomeGenerator:
    """
    Assigns terrain biomes to cells using OpenSimplex noise for natural clustering.
    """

    def __init__(self, config: BiomeMapConfig) -> None:
        if not isinstance(config, BiomeMapConfig):
            raise TypeError("config must be a BiomeMapConfig instance")
        self.config = config
        self.zone_noise = OpenSimplex(seed=config.seed)
        self.elevation_generators: Dict[str, ElevationGenerator] = {
            zone.name: ElevationGenerator(zone.elevation_config)
            for zone in config.zones
        }
        logger.info(f"Initialized BiomeGenerator with {len(config.zones)} zones, seed={config.seed}")

    def _get_zone_noise_value(self, x: float, y: float) -> float:
        noise_val = self.zone_noise.noise2(x / self.config.zone_scale, y / self.config.zone_scale)
        return (noise_val + 1.0) / 2.0

    def _assign_zone(self, noise_value: float) -> TerrainZone:
        cumulative = 0.0
        for zone in self.config.zones:
            cumulative += zone.percentage
            if noise_value <= cumulative:
                return zone
        return self.config.zones[-1]  # pragma: no cover — float rounding fallback

    def _compute_blended_elevation(self, noise_value: float, x: float, y: float) -> float:
        """
        Compute elevation with optional blending at zone boundaries.

        If blend_zones is False or blend_distance <= 0, returns the primary zone's
        elevation unchanged. Otherwise, checks whether noise_value is within blend_half
        of any zone boundary threshold and linearly interpolates between adjacent zones.
        Skips blending if either adjacent zone has no_blend=True.
        """
        primary_zone = self._assign_zone(noise_value)
        primary_elev = self.elevation_generators[primary_zone.name].generate_elevation(x, y)

        if not self.config.blend_zones or self.config.blend_distance <= 0:
            return primary_elev

        blend_half = min(
            self.config.blend_distance / self.config.zone_scale * 0.2,
            0.15,
        )

        # Build cumulative boundary thresholds (all except the last zone)
        zones = self.config.zones
        boundaries = []
        cumulative = 0.0
        for i, zone in enumerate(zones[:-1]):
            cumulative += zone.percentage
            boundaries.append((cumulative, zones[i], zones[i + 1]))

        for threshold, zone_below, zone_above in boundaries:
            dist = noise_value - threshold
            if abs(dist) <= blend_half:
                # Skip blending if either zone has no_blend set
                if zone_below.no_blend or zone_above.no_blend:
                    return primary_elev
                # Linear interpolation: t=0 → fully zone_below, t=1 → fully zone_above
                t = (dist + blend_half) / (2.0 * blend_half)
                elev_below = self.elevation_generators[zone_below.name].generate_elevation(x, y)
                elev_above = self.elevation_generators[zone_above.name].generate_elevation(x, y)
                return elev_below + t * (elev_above - elev_below)

        return primary_elev

    def apply_to_cells(self, cells) -> Dict[str, int]:
        if not cells:
            logger.warning("No cells provided to apply_to_cells")
            return {}

        logger.info(f"Generating biomes for {len(cells)} cells...")
        zone_counts: Dict[str, int] = {zone.name: 0 for zone in self.config.zones}
        cell_zones: Dict[int, TerrainZone] = {}
        cell_noise: Dict[int, float] = {}

        # First pass: assign zones and record noise values
        for cell in cells:
            x, y = cell.center
            noise_value = self._get_zone_noise_value(x, y)
            zone = self._assign_zone(noise_value)
            cell_zones[cell.index] = zone
            cell_noise[cell.index] = noise_value
            zone_counts[zone.name] += 1

        # Second pass: set elevation (with blending), terrain type, and cover
        for cell in cells:
            zone = cell_zones[cell.index]
            x, y = cell.center
            noise_value = cell_noise[cell.index]
            cell.set_elevation(self._compute_blended_elevation(noise_value, x, y))
            cell.set_terrain_type(zone.terrain_type)
            cell.set_cover_value(zone.cover_value)

        logger.info("Biome generation complete. Distribution:")
        for zone_name, count in zone_counts.items():
            logger.info(f"  {zone_name}: {count} cells ({count / len(cells) * 100:.1f}%)")

        return zone_counts

    def get_zone_at_position(self, x: float, y: float) -> TerrainZone:
        return self._assign_zone(self._get_zone_noise_value(x, y))

    def generate_zone_map_array(self, width: int, height: int,
                                 resolution: int = 1) -> np.ndarray:
        rows = height // resolution
        cols = width // resolution
        zone_map = np.zeros((rows, cols), dtype=int)
        for i in range(rows):
            for j in range(cols):
                zone = self._assign_zone(
                    self._get_zone_noise_value(j * resolution, i * resolution)
                )
                zone_map[i, j] = next(
                    idx for idx, z in enumerate(self.config.zones) if z.name == zone.name
                )
        return zone_map

    def __str__(self) -> str:
        return f"BiomeGenerator(zones={[z.name for z in self.config.zones]}, seed={self.config.seed})"

    def __repr__(self) -> str:
        return f"<BiomeGenerator(config={self.config!r})>"


if __name__ == "__main__":  # pragma: no cover
    from shapely.geometry import box as _box
    from imperial_generals.map.Cell import Cell as _Cell
    import logging as _logging
    _logging.basicConfig(level=_logging.INFO)

    config = BiomePresets.mixed_battlefield(seed=42)
    gen = BiomeGenerator(config)
    cells = [
        _Cell(index=i * 20 + j, center=(i * 5 + 2.5, j * 5 + 2.5),
              polygon=_box(i * 5, j * 5, i * 5 + 5, j * 5 + 5))
        for i in range(20) for j in range(20)
    ]
    counts = gen.apply_to_cells(cells)
    for name, count in counts.items():
        print(f"  {name}: {count}/{len(cells)} ({count/len(cells)*100:.1f}%)")
