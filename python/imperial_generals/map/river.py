"""
River generation for the map pipeline (Stage 3).

Generates `num_rivers` source-to-sink rivers:
  - Source: high-elevation interior cell (not on map boundary)
  - Flow: greedy lowest-neighbour walk (downhill); allows brief uphill to escape
    local minima; falls back to BFS if completely stuck.
  - Sink: map edge cell, or merge into an existing river cell.
  - Cell effect: cells on a river path get terrain_type = 'river'.

Rivers are generated in order; later rivers may merge into earlier ones.
"""

import logging
import random
from collections import deque
from typing import Dict, List, Set

from shapely.geometry import box

from imperial_generals.map.Cell import Cell

logger = logging.getLogger(__name__)


class RiverGenerator:
    """
    Generates rivers as greedy downhill paths on the cell adjacency graph.

    Args:
        cells (List[Cell]): All map cells (same list as VoronoiMap.get_cells()).
        width (int): Map width in units — used for boundary detection.
        height (int): Map height in units — used for boundary detection.
    """

    def __init__(self, cells: List[Cell], width: int, height: int) -> None:
        self._cells = cells
        self._width = width
        self._height = height
        self._index_to_cell: Dict[int, Cell] = {c.index: c for c in cells}
        self._neighbor_map: Dict[int, Set[int]] = self._build_neighbor_map()
        self._edge_cells: Set[int] = {
            c.index for c in cells if self._is_edge_cell(c)
        }

    # ------------------------------------------------------------------
    # Neighbour graph
    # ------------------------------------------------------------------

    def _build_neighbor_map(self) -> Dict[int, Set[int]]:
        """
        Build adjacency map: cell index → set of adjacent cell indices.

        Two cells are adjacent when their polygons share a line segment
        (shared-edge length > 0). Uses a Shapely STRtree for efficiency.
        """
        from shapely.strtree import STRtree

        neighbor_map: Dict[int, Set[int]] = {c.index: set() for c in self._cells}
        if not self._cells:
            return neighbor_map

        polygons = [c.polygon for c in self._cells]
        tree = STRtree(polygons)

        for i, cell in enumerate(self._cells):
            candidate_positions = tree.query(cell.polygon)
            for pos in candidate_positions:
                if pos <= i:
                    continue  # each unordered pair checked exactly once
                other = self._cells[pos]
                intersection = cell.polygon.intersection(other.polygon)
                if not intersection.is_empty and intersection.length > 1e-9:
                    neighbor_map[cell.index].add(other.index)
                    neighbor_map[other.index].add(cell.index)

        return neighbor_map

    def get_neighbors(self, cell: Cell) -> List[Cell]:
        """Return all cells that share an edge with *cell*."""
        return [
            self._index_to_cell[idx]
            for idx in self._neighbor_map.get(cell.index, set())
        ]

    # ------------------------------------------------------------------
    # Edge detection
    # ------------------------------------------------------------------

    def _is_edge_cell(self, cell: Cell) -> bool:
        """Return True if *cell*'s polygon touches the map boundary as a line."""
        map_boundary = box(0, 0, self._width, self._height).exterior
        intersection = map_boundary.intersection(cell.polygon.exterior)
        return not intersection.is_empty and intersection.length > 1e-9

    # ------------------------------------------------------------------
    # Source selection
    # ------------------------------------------------------------------

    def _source_candidates(self, top_fraction: float = 0.3) -> List[Cell]:
        """
        Return interior (non-edge) cells sorted by elevation descending,
        limited to the top *top_fraction* by elevation.

        At least one candidate is always returned when interior cells exist.
        """
        interior = [c for c in self._cells if c.index not in self._edge_cells]
        interior.sort(key=lambda c: c.elevation, reverse=True)
        cutoff = max(1, int(len(interior) * top_fraction))
        return interior[:cutoff]

    # ------------------------------------------------------------------
    # Path finding
    # ------------------------------------------------------------------

    def _flow_path(self, source: Cell, river_indices: Set[int]) -> List[Cell]:
        """
        Two-phase source-to-sink river path.

        Phase 1 — strict downhill walk:
            At each step moves to the unvisited neighbour with the strictly
            lowest elevation (must be lower than current).  Terminates when an
            edge cell or existing river cell is reached, or when no strictly-
            lower unvisited neighbour exists (local minimum).

        Phase 2 — unrestricted BFS escape (only if Phase 1 stalls):
            BFS from the stuck position to the nearest exit (map edge or
            existing river).  No walk-history restriction is applied so BFS
            can always escape on a finite connected map.

        Rationale: allowing uphill movement in Phase 1 causes the path to
        spiral on flat biome maps (narrow elevation range), eventually forming
        a closed barrier that traps the walker and prevents escape.

        Args:
            source: Starting cell (should be high-elevation, interior).
            river_indices: Cell indices already designated as river cells.

        Returns:
            List of cells from source (inclusive) to terminus (inclusive).
            The path is contiguous — each consecutive pair shares an edge.
        """
        path: List[Cell] = [source]
        visited: Set[int] = {source.index}
        current = source

        # ── Phase 1: strict downhill ──────────────────────────────────────
        while True:
            if current is not source and current.index in self._edge_cells:
                return path

            # Unvisited neighbours
            unvisited = [
                self._index_to_cell[idx]
                for idx in self._neighbor_map.get(current.index, set())
                if idx not in visited
            ]

            # Prefer merging into an adjacent river immediately
            river_adjacent = [c for c in unvisited if c.index in river_indices]
            if river_adjacent:
                path.append(min(river_adjacent, key=lambda c: (c.elevation, c.index)))
                return path

            # Only descend — no uphill movement that could create spirals
            lower = [c for c in unvisited if c.elevation < current.elevation]
            if not lower:
                break  # local minimum — hand off to BFS

            next_cell = min(lower, key=lambda c: (c.elevation, c.index))
            path.append(next_cell)
            visited.add(next_cell.index)
            current = next_cell

        # ── Phase 2: unrestricted BFS from local minimum ──────────────────
        # Empty visited set means BFS walks freely — guaranteed to find exit.
        extension = self._bfs_to_exit(current, set(), river_indices)
        path.extend(extension)
        return path

    def _bfs_to_exit(
        self,
        start: Cell,
        visited: Set[int],
        river_indices: Set[int],
    ) -> List[Cell]:
        """
        BFS from *start* to the nearest exit (edge cell or existing river cell).

        Returns the path from the cell *after* start to the exit (start excluded).
        Returns an empty list if no exit is reachable (should not happen on a
        finite, fully-connected map).
        """
        queue: deque = deque([[start]])
        seen: Set[int] = {start.index} | visited

        while queue:
            path = queue.popleft()
            current = path[-1]

            for idx in self._neighbor_map.get(current.index, set()):
                if idx in seen:
                    continue
                cell = self._index_to_cell[idx]
                new_path = path + [cell]
                if idx in self._edge_cells or idx in river_indices:
                    return new_path[1:]  # exclude start (already in main path)
                seen.add(idx)
                queue.append(new_path)

        return []  # pragma: no cover — finite map always has a reachable exit

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(self, num_rivers: int, seed: int) -> List[List[Cell]]:
        """
        Generate river paths without modifying any cells.

        Args:
            num_rivers: Number of rivers to generate (0 or negative → empty list).
            seed: Random seed for reproducible source selection.

        Returns:
            List of paths. Each path is a list of Cell objects from source to
            terminus. May be shorter than *num_rivers* when there are fewer
            valid source candidates than requested.
        """
        if num_rivers <= 0:
            return []

        rng = random.Random(seed)
        candidates = self._source_candidates()
        if not candidates:
            logger.warning("No valid river source candidates found; skipping river generation.")
            return []

        n = min(num_rivers, len(candidates))
        sources = rng.sample(candidates, n)

        river_indices: Set[int] = set()
        rivers: List[List[Cell]] = []

        for source in sources:
            if source.index in river_indices:  # pragma: no cover
                continue  # Already incorporated into a previous river
            path = self._flow_path(source, river_indices)
            rivers.append(path)
            for cell in path:
                river_indices.add(cell.index)
            logger.debug(
                f"River from cell {source.index} "
                f"(elev={source.elevation:.1f}): {len(path)} cells"
            )

        logger.info(
            f"Generated {len(rivers)} river(s), "
            f"{sum(len(p) for p in rivers)} total cells."
        )
        return rivers

    def apply_to_cells(self, num_rivers: int, seed: int) -> None:
        """
        Generate rivers and set terrain_type='river' on all path cells.

        Args:
            num_rivers: Number of rivers to generate.
            seed: Random seed for reproducible results.
        """
        rivers = self.generate(num_rivers, seed)
        for path in rivers:
            for cell in path:
                cell.set_terrain_type('river')
        logger.info(
            f"Applied terrain_type='river' to "
            f"{sum(len(p) for p in rivers)} cell(s) across {len(rivers)} river(s)."
        )


if __name__ == "__main__":  # pragma: no cover
    from shapely.geometry import box as _box
    cells = []
    for i in range(7):
        for j in range(7):
            poly = _box(j * 10, i * 10, j * 10 + 10, i * 10 + 10)
            c = Cell(index=len(cells), center=(j * 10 + 5, i * 10 + 5), polygon=poly)
            c.set_elevation(float(i * 20))
            cells.append(c)
    gen = RiverGenerator(cells, 70, 70)
    gen.apply_to_cells(2, seed=42)
    river_cells = [c for c in cells if c.terrain_type == 'river']
    print(f"River cells: {len(river_cells)}")
