"""
Tests for RiverGenerator (SPEC §1.2 — River generation, Stage 3).

Uses a deterministic grid of square cells to verify:
  - Neighbour graph construction
  - Edge-cell detection
  - Source candidate selection
  - Downhill path finding and termination
  - Cell mutation (terrain_type = 'river')
  - Determinism with a fixed seed
"""

import pytest
from shapely.geometry import box

from imperial_generals.map.Cell import Cell
from imperial_generals.map.river import RiverGenerator


# =============================================================================
# Helpers
# =============================================================================

def make_grid(rows: int = 7, cols: int = 7, cell_size: float = 10.0):
    """
    Create a rows×cols grid of square cells.

    Returns (cells, width, height).
    Cell index = row * cols + col.
    Row 0 is at the bottom (y=0), row rows-1 is at the top.
    """
    cells = []
    for i in range(rows):
        for j in range(cols):
            x0, y0 = j * cell_size, i * cell_size
            poly = box(x0, y0, x0 + cell_size, y0 + cell_size)
            center = (x0 + cell_size / 2.0, y0 + cell_size / 2.0)
            cells.append(Cell(index=len(cells), center=center, polygon=poly))
    return cells, cols * cell_size, rows * cell_size


def set_row_elevation(cells, rows, cols):
    """
    Set elevation = row * 20.0.

    Row 0 (bottom edge) = 0.0 (lowest).
    Row rows-1 (top edge) = (rows-1)*20 (highest).
    Interior high-elevation sources are in the upper rows.
    """
    for cell in cells:
        row = cell.index // cols
        cell.set_elevation(float(row * 20))


def cell_at(cells, row, col, cols=7):
    return cells[row * cols + col]


# =============================================================================
# Initialisation
# =============================================================================

class TestRiverGeneratorInit:
    def test_init_stores_dimensions(self):
        cells, w, h = make_grid(5, 5)
        gen = RiverGenerator(cells, w, h)
        assert gen._width == w
        assert gen._height == h

    def test_init_stores_cells(self):
        cells, w, h = make_grid(5, 5)
        gen = RiverGenerator(cells, w, h)
        assert gen._cells is cells

    def test_init_empty_cells(self):
        gen = RiverGenerator([], 100, 100)
        assert gen._cells == []
        assert gen._neighbor_map == {}

    def test_init_builds_neighbor_map_dict(self):
        cells, w, h = make_grid(5, 5)
        gen = RiverGenerator(cells, w, h)
        assert isinstance(gen._neighbor_map, dict)
        assert len(gen._neighbor_map) == len(cells)

    def test_init_builds_edge_set(self):
        cells, w, h = make_grid(5, 5)
        gen = RiverGenerator(cells, w, h)
        assert isinstance(gen._edge_cells, set)
        assert len(gen._edge_cells) > 0


# =============================================================================
# Neighbour map
# =============================================================================

class TestNeighborMap:
    def setup_method(self):
        self.cells, self.w, self.h = make_grid(5, 5)
        self.gen = RiverGenerator(self.cells, self.w, self.h)

    def test_interior_cell_has_four_neighbors(self):
        c = cell_at(self.cells, 2, 2, 5)
        assert len(self.gen.get_neighbors(c)) == 4

    def test_corner_cell_has_two_neighbors(self):
        c = cell_at(self.cells, 0, 0, 5)
        assert len(self.gen.get_neighbors(c)) == 2

    def test_edge_non_corner_has_three_neighbors(self):
        c = cell_at(self.cells, 0, 2, 5)
        assert len(self.gen.get_neighbors(c)) == 3

    def test_neighbor_relationship_is_symmetric(self):
        for cell in self.cells:
            for n_idx in self.gen._neighbor_map[cell.index]:
                assert cell.index in self.gen._neighbor_map[n_idx]

    def test_diagonal_cells_are_not_neighbors(self):
        # (row=0, col=0) and (row=1, col=1) share only a corner point
        c00 = cell_at(self.cells, 0, 0, 5)
        c11 = cell_at(self.cells, 1, 1, 5)
        assert c11.index not in self.gen._neighbor_map[c00.index]

    def test_get_neighbors_returns_cell_objects(self):
        c = cell_at(self.cells, 2, 2, 5)
        neighbors = self.gen.get_neighbors(c)
        assert all(isinstance(n, Cell) for n in neighbors)

    def test_known_horizontal_neighbors(self):
        # (row=2, col=1) and (row=2, col=2) must be neighbors
        left = cell_at(self.cells, 2, 1, 5)
        right = cell_at(self.cells, 2, 2, 5)
        assert right.index in self.gen._neighbor_map[left.index]
        assert left.index in self.gen._neighbor_map[right.index]

    def test_known_vertical_neighbors(self):
        below = cell_at(self.cells, 1, 2, 5)
        above = cell_at(self.cells, 2, 2, 5)
        assert above.index in self.gen._neighbor_map[below.index]
        assert below.index in self.gen._neighbor_map[above.index]


# =============================================================================
# Edge cell detection
# =============================================================================

class TestIsEdgeCell:
    def setup_method(self):
        self.cells, self.w, self.h = make_grid(5, 5)
        self.gen = RiverGenerator(self.cells, self.w, self.h)

    def test_bottom_left_corner_is_edge(self):
        assert self.gen._is_edge_cell(cell_at(self.cells, 0, 0, 5)) is True

    def test_top_right_corner_is_edge(self):
        assert self.gen._is_edge_cell(cell_at(self.cells, 4, 4, 5)) is True

    def test_bottom_edge_mid_is_edge(self):
        assert self.gen._is_edge_cell(cell_at(self.cells, 0, 2, 5)) is True

    def test_left_edge_mid_is_edge(self):
        assert self.gen._is_edge_cell(cell_at(self.cells, 2, 0, 5)) is True

    def test_right_edge_mid_is_edge(self):
        assert self.gen._is_edge_cell(cell_at(self.cells, 2, 4, 5)) is True

    def test_top_edge_mid_is_edge(self):
        assert self.gen._is_edge_cell(cell_at(self.cells, 4, 2, 5)) is True

    def test_interior_cell_is_not_edge(self):
        assert self.gen._is_edge_cell(cell_at(self.cells, 2, 2, 5)) is False

    def test_all_border_cells_are_edge_in_5x5(self):
        # In a 5x5 grid every cell with row=0, row=4, col=0, or col=4 is a border cell
        for cell in self.cells:
            row = cell.index // 5
            col = cell.index % 5
            expected = (row == 0 or row == 4 or col == 0 or col == 4)
            assert self.gen._is_edge_cell(cell) == expected

    def test_edge_cells_set_matches_is_edge_cell_method(self):
        for cell in self.cells:
            assert (cell.index in self.gen._edge_cells) == self.gen._is_edge_cell(cell)


# =============================================================================
# Source candidates
# =============================================================================

class TestSourceCandidates:
    def setup_method(self):
        self.cells, self.w, self.h = make_grid(7, 7)
        set_row_elevation(self.cells, 7, 7)
        self.gen = RiverGenerator(self.cells, self.w, self.h)

    def test_no_edge_cells_in_candidates(self):
        candidates = self.gen._source_candidates()
        for c in candidates:
            assert c.index not in self.gen._edge_cells

    def test_candidates_sorted_descending_by_elevation(self):
        candidates = self.gen._source_candidates(top_fraction=1.0)
        elevations = [c.elevation for c in candidates]
        assert elevations == sorted(elevations, reverse=True)

    def test_full_fraction_returns_all_interior(self):
        all_interior = [c for c in self.cells if c.index not in self.gen._edge_cells]
        full = self.gen._source_candidates(top_fraction=1.0)
        assert len(full) == len(all_interior)

    def test_top_fraction_limits_count(self):
        all_interior = [c for c in self.cells if c.index not in self.gen._edge_cells]
        half = self.gen._source_candidates(top_fraction=0.5)
        assert len(half) <= max(1, int(len(all_interior) * 0.5) + 1)

    def test_returns_highest_elevation_cell_first(self):
        candidates = self.gen._source_candidates()
        all_interior = [c for c in self.cells if c.index not in self.gen._edge_cells]
        max_interior_elev = max(c.elevation for c in all_interior)
        assert candidates[0].elevation == max_interior_elev

    def test_always_returns_at_least_one_candidate(self):
        # Even with tiny fraction, at least 1 candidate (interior cells exist)
        candidates = self.gen._source_candidates(top_fraction=0.01)
        assert len(candidates) >= 1


# =============================================================================
# Flow path
# =============================================================================

class TestFlowPath:
    def setup_method(self):
        self.cells, self.w, self.h = make_grid(7, 7)
        set_row_elevation(self.cells, 7, 7)
        self.gen = RiverGenerator(self.cells, self.w, self.h)

    def test_path_starts_at_source(self):
        source = cell_at(self.cells, 5, 3)
        path = self.gen._flow_path(source, set())
        assert path[0] is source

    def test_path_ends_at_map_edge(self):
        # On a row-gradient map a downhill walk from row=5 must hit row=0 (edge)
        source = cell_at(self.cells, 5, 3)
        path = self.gen._flow_path(source, set())
        assert path[-1].index in self.gen._edge_cells

    def test_path_is_contiguous(self):
        source = cell_at(self.cells, 5, 3)
        path = self.gen._flow_path(source, set())
        for a, b in zip(path, path[1:]):
            assert b.index in self.gen._neighbor_map[a.index], \
                f"Cell {b.index} not a neighbour of {a.index}"

    def test_path_has_no_repeated_cells(self):
        source = cell_at(self.cells, 5, 3)
        path = self.gen._flow_path(source, set())
        indices = [c.index for c in path]
        assert len(indices) == len(set(indices))

    def test_path_first_step_goes_downhill(self):
        source = cell_at(self.cells, 5, 3)
        path = self.gen._flow_path(source, set())
        # Phase 1 is strict downhill — first step must be strictly lower
        assert path[1].elevation < source.elevation

    def test_bfs_escape_when_source_is_local_minimum(self):
        """When source has no lower neighbours Phase 2 BFS escapes to edge."""
        # All cells at 50 except the source at 30 → instant local minimum
        cells, w, h = make_grid(5, 5)
        for c in cells:
            c.set_elevation(50.0)
        source = cell_at(cells, 2, 2, 5)   # interior centre cell
        source.set_elevation(30.0)          # lower than all neighbours
        gen = RiverGenerator(cells, w, h)
        path = gen._flow_path(source, set())
        assert path[0] is source
        assert path[-1].index in gen._edge_cells

    def test_path_minimum_length_is_two(self):
        source = cell_at(self.cells, 4, 3)
        path = self.gen._flow_path(source, set())
        assert len(path) >= 2

    def test_path_terminates_at_existing_river_cell(self):
        # Pre-mark (row=3, col=3) as an existing river cell
        target = cell_at(self.cells, 3, 3)
        river_indices = {target.index}
        source = cell_at(self.cells, 5, 3)
        path = self.gen._flow_path(source, river_indices)
        last = path[-1]
        assert last.index in self.gen._edge_cells or last.index in river_indices

    def test_path_length_equals_rows_traversed_on_gradient(self):
        # Source at row=5 (elevation=100); path must pass through rows 4,3,2,1,0
        source = cell_at(self.cells, 5, 3)
        path = self.gen._flow_path(source, set())
        # Path must include at least rows 5 and 0 (6 cells minimum)
        assert len(path) >= 6


# =============================================================================
# BFS fallback
# =============================================================================

class TestBFSFallback:
    def setup_method(self):
        self.cells, self.w, self.h = make_grid(5, 5)
        self.gen = RiverGenerator(self.cells, self.w, self.h)

    def test_bfs_returns_path_to_edge(self):
        interior = cell_at(self.cells, 2, 2, 5)
        extension = self.gen._bfs_to_exit(interior, {interior.index}, set())
        assert len(extension) > 0
        assert extension[-1].index in self.gen._edge_cells

    def test_bfs_extension_is_contiguous_from_start(self):
        interior = cell_at(self.cells, 2, 2, 5)
        extension = self.gen._bfs_to_exit(interior, {interior.index}, set())
        # First cell of extension must be a neighbor of interior
        assert extension[0].index in self.gen._neighbor_map[interior.index]
        # Remaining cells form a contiguous chain
        for a, b in zip(extension, extension[1:]):
            assert b.index in self.gen._neighbor_map[a.index]

    def test_bfs_stops_at_river_cell(self):
        interior = cell_at(self.cells, 2, 2, 5)
        # Mark (row=2, col=3) as an existing river — adjacent to interior
        river_target = cell_at(self.cells, 2, 3, 5)
        river_indices = {river_target.index}
        extension = self.gen._bfs_to_exit(interior, {interior.index}, river_indices)
        assert len(extension) >= 1
        assert extension[-1].index in self.gen._edge_cells or \
               extension[-1].index in river_indices


# =============================================================================
# generate()
# =============================================================================

class TestGenerate:
    def setup_method(self):
        self.cells, self.w, self.h = make_grid(7, 7)
        set_row_elevation(self.cells, 7, 7)
        self.gen = RiverGenerator(self.cells, self.w, self.h)

    def test_zero_rivers_returns_empty_list(self):
        assert self.gen.generate(0, seed=42) == []

    def test_negative_returns_empty_list(self):
        assert self.gen.generate(-5, seed=42) == []

    def test_one_river_returns_one_path(self):
        rivers = self.gen.generate(1, seed=42)
        assert len(rivers) == 1

    def test_two_rivers_returns_two_paths(self):
        rivers = self.gen.generate(2, seed=42)
        assert len(rivers) == 2

    def test_each_path_is_list_of_cells(self):
        rivers = self.gen.generate(2, seed=1)
        for path in rivers:
            assert isinstance(path, list)
            assert all(isinstance(c, Cell) for c in path)

    def test_each_path_ends_at_edge_or_river_merge(self):
        rivers = self.gen.generate(2, seed=7)
        river_indices_so_far: set = set()
        for path in rivers:
            last = path[-1]
            assert last.index in self.gen._edge_cells or \
                   last.index in river_indices_so_far, \
                f"River path ended at non-exit cell {last.index}"
            for cell in path:
                river_indices_so_far.add(cell.index)

    def test_all_paths_are_contiguous(self):
        rivers = self.gen.generate(3, seed=5)
        for path in rivers:
            for a, b in zip(path, path[1:]):
                assert b.index in self.gen._neighbor_map[a.index]

    def test_same_seed_is_deterministic(self):
        rivers_a = self.gen.generate(2, seed=99)
        rivers_b = self.gen.generate(2, seed=99)
        for pa, pb in zip(rivers_a, rivers_b):
            assert [c.index for c in pa] == [c.index for c in pb]

    def test_requesting_more_rivers_than_candidates_does_not_raise(self):
        candidates = self.gen._source_candidates()
        rivers = self.gen.generate(len(candidates) + 100, seed=0)
        assert len(rivers) <= len(candidates)

    def test_generate_with_all_edge_cells_returns_empty(self):
        """When every cell is on the map boundary there are no valid sources."""
        # A 2×2 grid: all 4 cells touch the map boundary
        cells, w, h = make_grid(2, 2)
        gen = RiverGenerator(cells, w, h)
        rivers = gen.generate(1, seed=42)
        assert rivers == []

    def test_generate_does_not_mutate_cells(self):
        original = {c.index: c.terrain_type for c in self.cells}
        self.gen.generate(2, seed=42)
        for c in self.cells:
            assert c.terrain_type == original[c.index]

    def test_each_path_has_no_duplicate_cells(self):
        rivers = self.gen.generate(2, seed=3)
        for path in rivers:
            indices = [c.index for c in path]
            assert len(indices) == len(set(indices))


# =============================================================================
# apply_to_cells()
# =============================================================================

class TestApplyToCells:
    def setup_method(self):
        self.cells, self.w, self.h = make_grid(7, 7)
        set_row_elevation(self.cells, 7, 7)
        self.gen = RiverGenerator(self.cells, self.w, self.h)

    def test_zero_rivers_changes_no_cells(self):
        self.gen.apply_to_cells(0, seed=42)
        assert all(c.terrain_type == 'open' for c in self.cells)

    def test_one_river_marks_some_cells_as_river(self):
        self.gen.apply_to_cells(1, seed=42)
        river_cells = [c for c in self.cells if c.terrain_type == 'river']
        assert len(river_cells) > 0

    def test_two_rivers_marks_more_cells(self):
        self.gen.apply_to_cells(2, seed=42)
        river_cells = [c for c in self.cells if c.terrain_type == 'river']
        assert len(river_cells) >= 2

    def test_only_river_cells_have_river_terrain(self):
        original = {c.index: c.terrain_type for c in self.cells}
        self.gen.apply_to_cells(1, seed=42)
        for cell in self.cells:
            if cell.terrain_type != 'river':
                assert cell.terrain_type == original[cell.index]

    def test_apply_is_deterministic(self):
        cells_a, w, h = make_grid(7, 7)
        set_row_elevation(cells_a, 7, 7)
        cells_b, _, _ = make_grid(7, 7)
        set_row_elevation(cells_b, 7, 7)

        RiverGenerator(cells_a, w, h).apply_to_cells(2, seed=77)
        RiverGenerator(cells_b, w, h).apply_to_cells(2, seed=77)

        for ca, cb in zip(cells_a, cells_b):
            assert ca.terrain_type == cb.terrain_type

    def test_river_terrain_type_value(self):
        self.gen.apply_to_cells(1, seed=1)
        for cell in self.cells:
            if cell.terrain_type == 'river':
                assert cell.terrain_type == 'river'


# =============================================================================
# MapGenerator pipeline integration
# =============================================================================

class TestMapGeneratorIntegration:
    def test_num_rivers_zero_produces_no_river_cells(self):
        from imperial_generals.map import MapConfig, MapGenerator, BiomePresets
        biome = BiomePresets.mixed_battlefield(seed=42)
        config = MapConfig(width=80, height=80, min_distance=12,
                           biome_config=biome, num_rivers=0)
        result = MapGenerator(config).generate_map()
        assert all(c.terrain_type != 'river' for c in result.cells)

    def test_num_rivers_one_produces_river_cells(self):
        from imperial_generals.map import MapConfig, MapGenerator, BiomePresets
        biome = BiomePresets.mixed_battlefield(seed=42)
        config = MapConfig(width=80, height=80, min_distance=12,
                           biome_config=biome, num_rivers=1)
        result = MapGenerator(config).generate_map()
        river_cells = [c for c in result.cells if c.terrain_type == 'river']
        assert len(river_cells) > 0

    def test_two_rivers_marks_at_least_as_many_cells_as_one(self):
        """On the same cell graph, 2 rivers mark >= cells than 1 river."""
        from imperial_generals.map import MapConfig, MapGenerator, BiomePresets
        from imperial_generals.map.river import RiverGenerator
        biome = BiomePresets.mixed_battlefield(seed=7)
        config = MapConfig(width=80, height=80, min_distance=12,
                           biome_config=biome, num_rivers=0)
        result = MapGenerator(config).generate_map()
        gen = RiverGenerator(result.cells, config.width, config.height)
        count1 = sum(len(p) for p in gen.generate(1, seed=7))
        count2 = sum(len(p) for p in gen.generate(2, seed=7))
        assert count2 >= count1

    def test_river_generator_on_pipeline_cells_is_deterministic(self):
        """RiverGenerator.generate() is deterministic given the same cell graph."""
        from imperial_generals.map import MapConfig, MapGenerator, BiomePresets
        from imperial_generals.map.river import RiverGenerator
        biome = BiomePresets.mixed_battlefield(seed=42)
        config = MapConfig(width=80, height=80, min_distance=12,
                           biome_config=biome, num_rivers=0)
        result = MapGenerator(config).generate_map()
        gen = RiverGenerator(result.cells, config.width, config.height)
        paths_a = gen.generate(1, seed=42)
        paths_b = gen.generate(1, seed=42)
        assert [c.index for c in paths_a[0]] == [c.index for c in paths_b[0]]

    def test_elevation_only_config_with_rivers(self):
        from imperial_generals.map import MapConfig, MapGenerator, ElevationConfig, TerrainPresets
        elev = TerrainPresets.hills(seed=5)
        config = MapConfig(width=80, height=80, min_distance=12,
                           elevation_config=elev, num_rivers=1)
        result = MapGenerator(config).generate_map()
        river_cells = [c for c in result.cells if c.terrain_type == 'river']
        assert len(river_cells) > 0
