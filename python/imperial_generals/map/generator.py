"""
Map configuration, result container, and generation pipeline.

MapGenerator orchestrates stages in order:
  1. Voronoi mesh (always)
  2. Biome assignment  (if biome_config set)
     OR elevation-only  (if elevation_config set)
  3. (future) Rivers, Lakes, Roads, Fences — each a separate stage
     reading num_rivers / num_lakes / num_roads from MapConfig.
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from imperial_generals.map.Cell import Cell
from imperial_generals.map.voronoi import PoissonDiscSampler, VoronoiMap
from imperial_generals.map.elevation import ElevationConfig, ElevationGenerator
from imperial_generals.map.biome import BiomeMapConfig, BiomeGenerator, BiomePresets

logger = logging.getLogger(__name__)


# =============================================================================
# MapResult
# =============================================================================

class MapResult:
    """
    Output of a MapGenerator pipeline run.

    Attributes:
        voronoi (VoronoiMap): The generated Voronoi diagram.
        cells (List[Cell]): Shortcut to voronoi.get_cells() — same object.
        zone_counts (Dict[str, int]): Cells per biome zone (empty if no biome).
    """

    def __init__(self, voronoi: VoronoiMap, cells: List[Cell],
                 zone_counts: Dict[str, int] = None):
        self.voronoi     = voronoi
        self.cells       = cells
        self.zone_counts = zone_counts if zone_counts is not None else {}

    def __str__(self) -> str:
        return (f"MapResult(cells={len(self.cells)}, "
                f"zone_counts={self.zone_counts})")

    def __repr__(self) -> str:
        return (f"<MapResult(voronoi={self.voronoi!r}, "
                f"cells={len(self.cells)} cells, "
                f"zone_counts={self.zone_counts})>")


# =============================================================================
# MapConfig
# =============================================================================

class MapConfig:
    """
    Full configuration for a map generation pipeline run.

    Attributes:
        width, height (int): Map dimensions in units.
        min_distance (int): Minimum distance between Voronoi seed points.
        elevation_config (ElevationConfig | None): Single-terrain elevation.
        biome_config (BiomeMapConfig | None): Multi-terrain biome layout.
            Specify either elevation_config OR biome_config, not both.
        num_rivers (int): Number of rivers to generate (stage 3, future).
        num_lakes (int): Number of lake clusters to generate (stage 4, future).
        num_roads (int): Number of roads to generate (stage 5, future).
    """

    def __init__(
        self,
        width: int,
        height: int,
        min_distance: int,
        elevation_config: Optional[ElevationConfig] = None,
        biome_config: Optional[BiomeMapConfig] = None,
        num_rivers: int = 0,
        num_lakes: int = 0,
        num_roads: int = 0,
    ):
        if not isinstance(width, int):
            raise TypeError("width must be an int")
        if not isinstance(height, int):
            raise TypeError("height must be an int")
        if not isinstance(min_distance, int):
            raise TypeError("min_distance must be an int")
        if elevation_config is not None and not isinstance(elevation_config, ElevationConfig):
            raise TypeError("elevation_config must be an ElevationConfig instance or None")
        if biome_config is not None and not isinstance(biome_config, BiomeMapConfig):
            raise TypeError("biome_config must be a BiomeMapConfig instance or None")
        if elevation_config is not None and biome_config is not None:
            raise ValueError("Cannot specify both elevation_config and biome_config. Choose one.")
        if not isinstance(num_rivers, int):
            raise TypeError("num_rivers must be an int")
        if not isinstance(num_lakes, int):
            raise TypeError("num_lakes must be an int")
        if not isinstance(num_roads, int):
            raise TypeError("num_roads must be an int")
        if num_rivers < 0:
            raise ValueError("num_rivers must be non-negative")
        if num_lakes < 0:
            raise ValueError("num_lakes must be non-negative")
        if num_roads < 0:
            raise ValueError("num_roads must be non-negative")

        self.width            = width
        self.height           = height
        self.min_distance     = min_distance
        self.elevation_config = elevation_config
        self.biome_config     = biome_config
        self.num_rivers       = num_rivers
        self.num_lakes        = num_lakes
        self.num_roads        = num_roads

    def __repr__(self) -> str:
        return (f"<MapConfig(width={self.width}, height={self.height}, "
                f"min_distance={self.min_distance}, "
                f"elevation_config={self.elevation_config!r}, "
                f"biome_config={self.biome_config!r}, "
                f"num_rivers={self.num_rivers}, num_lakes={self.num_lakes}, "
                f"num_roads={self.num_roads})>")


# =============================================================================
# MapGenerator
# =============================================================================

class MapGenerator:
    """
    Orchestrates the map generation pipeline.

    Stages run in order; each mutates the cells in place before the next begins:
      1. Voronoi mesh
      2. Biome / elevation
      3. (future) Rivers → Lakes → Roads → Fences
    """

    def __init__(self, config: MapConfig) -> None:
        self.config = config
        logger.info(f"MapGenerator initialized: {config.width}x{config.height}, "
                    f"min_distance={config.min_distance}")

    def __str__(self) -> str:
        return (f"MapGenerator(width={self.config.width}, "
                f"height={self.config.height}, "
                f"min_distance={self.config.min_distance})")

    def __repr__(self) -> str:
        return f"<MapGenerator(config={self.config!r})>"

    # ------------------------------------------------------------------
    # Factory methods
    # ------------------------------------------------------------------

    @classmethod
    def from_preset(
        cls,
        preset_name: str,
        seed: int = None,
        width: int = None,
        height: int = None,
        min_distance: int = None,
    ) -> MapResult:
        """
        Generate a map from a named biome preset.

        Omitted dimension/seed arguments fall back to simulation.yaml defaults.

        Args:
            preset_name: Key in simulation.yaml map.biome_presets
                         (e.g. 'mixed_battlefield').
            seed: Random seed — defaults to config seed.
            width, height: Map dimensions — default to config defaults.
            min_distance: Point spacing — defaults to config default.

        Returns:
            MapResult
        """
        from imperial_generals.config import get_config
        defaults = get_config()['map']['defaults']
        _seed         = seed         if seed         is not None else defaults['seed']
        _width        = width        if width        is not None else defaults['width']
        _height       = height       if height       is not None else defaults['height']
        _min_distance = min_distance if min_distance is not None else defaults['min_distance']

        biome_config = BiomePresets._from_config(preset_name, _seed)
        config = MapConfig(width=_width, height=_height,
                           min_distance=_min_distance, biome_config=biome_config)
        return cls(config).generate_map()

    @classmethod
    def from_config(
        cls,
        preset: str = None,
        width: int = None,
        height: int = None,
        min_distance: int = None,
        seed: int = None,
    ) -> MapResult:
        """
        Generate a map using simulation.yaml defaults for all unspecified parameters.

        Args:
            preset: Optional biome preset name. If omitted, generates a plain
                    Voronoi map with no terrain assignment.
            width, height, min_distance, seed: Override config defaults.

        Returns:
            MapResult
        """
        from imperial_generals.config import get_config
        defaults      = get_config()['map']['defaults']
        _seed         = seed         if seed         is not None else defaults['seed']
        _width        = width        if width        is not None else defaults['width']
        _height       = height       if height       is not None else defaults['height']
        _min_distance = min_distance if min_distance is not None else defaults['min_distance']

        if preset is not None:
            biome_config = BiomePresets._from_config(preset, _seed)
            config = MapConfig(width=_width, height=_height,
                               min_distance=_min_distance, biome_config=biome_config)
        else:
            config = MapConfig(width=_width, height=_height,
                               min_distance=_min_distance)
        return cls(config).generate_map()

    # ------------------------------------------------------------------
    # Pipeline
    # ------------------------------------------------------------------

    def generate_map(self) -> MapResult:
        """
        Run the full generation pipeline and return a MapResult.

        Stage 1 — Voronoi mesh:
            Poisson disc sampling → Voronoi diagram → clipped cells.
        Stage 2 — Terrain:
            Biome assignment (if biome_config) or elevation-only (if elevation_config).
        Stages 3+ (future):
            Rivers, lakes, roads, fences — each reads its count from self.config.
        """
        # --- Stage 1: Voronoi mesh ---
        points = PoissonDiscSampler.generate(
            self.config.width, self.config.height, self.config.min_distance
        )
        voronoi = VoronoiMap(points, self.config.width, self.config.height)
        voronoi.generate_diagram()
        cells = voronoi.get_cells()
        logger.info(f"Stage 1 complete: {len(cells)} cells generated.")

        # --- Stage 2: Terrain ---
        zone_counts: Dict[str, int] = {}

        if self.config.biome_config is not None:
            biome_gen   = BiomeGenerator(self.config.biome_config)
            zone_counts = biome_gen.apply_to_cells(cells)
            logger.info("Stage 2 complete: biome assignment applied.")

        elif self.config.elevation_config is not None:
            elev_gen = ElevationGenerator(self.config.elevation_config)
            elev_gen.apply_to_cells(cells)
            logger.info("Stage 2 complete: elevation applied.")

        # --- Stages 3+ (future terrain features) ---
        # self.config.num_rivers, .num_lakes, .num_roads are available here.

        return MapResult(voronoi=voronoi, cells=cells, zone_counts=zone_counts)


if __name__ == "__main__":  # pragma: no cover
    result = MapGenerator.from_preset('mixed_battlefield', seed=42,
                                      width=100, height=100, min_distance=5)
    print(result)
    print(f"  {len(result.cells)} cells")
    for zone, count in result.zone_counts.items():
        print(f"  {zone}: {count}")
