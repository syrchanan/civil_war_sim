"""
Point sampling and Voronoi diagram generation.

Consolidates PoissonDiscSampler and VoronoiMap.
"""

import logging
from collections import defaultdict
from typing import List, Tuple, Optional

import numpy as np
import matplotlib.pyplot as plt
from scipy.spatial import KDTree, Voronoi
from shapely.geometry import Polygon, box, Point

from imperial_generals.map.Cell import Cell

logger = logging.getLogger(__name__)


# =============================================================================
# Point sampling
# =============================================================================

class PoissonDiscSampler:
    """Generates evenly-distributed 2D points via Poisson disc sampling."""

    @staticmethod
    def generate(
        width: float,
        height: float,
        min_distance: float,
        k: int = 20
    ) -> List[Tuple[float, float]]:
        """
        Generate 2D points using Poisson disc sampling.

        Args:
            width: Width of the sampling area.
            height: Height of the sampling area.
            min_distance: Minimum allowed distance between points.
            k: Candidate attempts per active point (default 20).

        Returns:
            List of (x, y) tuples.
        """
        if not isinstance(width, (int, float)):
            raise TypeError("width must be a number")
        if not isinstance(height, (int, float)):
            raise TypeError("height must be a number")
        if not isinstance(min_distance, (int, float)):
            raise TypeError("min_distance must be a number")
        if not isinstance(k, int):
            raise TypeError("k must be an integer")
        if width < 0:
            raise ValueError("width must be non-negative")
        if height < 0:
            raise ValueError("height must be non-negative")
        if min_distance <= 0:
            raise ValueError("min_distance must be positive")
        if k <= 0:
            raise ValueError("k must be positive")
        if width == 0 or height == 0:
            return []

        cell_size   = min_distance / 2
        grid: defaultdict = defaultdict(list)
        points: List[Tuple[float, float]] = []
        active: List[Tuple[float, float]] = []

        pt = (np.random.uniform(0, width), np.random.uniform(0, height))
        points.append(pt)
        active.append(pt)
        grid[(int(pt[0] // cell_size), int(pt[1] // cell_size))].append(pt)

        while active:
            idx = np.random.randint(len(active))
            center = active[idx]
            found = False
            tree = KDTree(points) if points else None

            for _ in range(k):
                angle  = np.random.uniform(0, 2 * np.pi)
                r      = np.random.uniform(min_distance, 2 * min_distance)
                new_pt = (center[0] + r * np.cos(angle), center[1] + r * np.sin(angle))

                if not (0 <= new_pt[0] < width and 0 <= new_pt[1] < height):
                    continue
                if tree is not None and tree.query_ball_point(new_pt, min_distance - 1e-8):
                    continue

                points.append(new_pt)
                active.append(new_pt)
                grid[(int(new_pt[0] // cell_size), int(new_pt[1] // cell_size))].append(new_pt)
                found = True
                break

            if not found:
                active.pop(idx)

        logger.info("Poisson disc sampling complete: %d points.", len(points))
        return points


# =============================================================================
# Voronoi map
# =============================================================================

class VoronoiMap:
    """Computes a Voronoi diagram from seed points and clips it to a bounding box."""

    def __init__(self, points: List[Tuple[float, float]],
                 width: int = 100, height: int = 100) -> None:
        self.points: np.ndarray = np.array(points)
        self.width: int  = width
        self.height: int = height
        self.diagram: Optional[Voronoi] = None
        self.polygons: List[Polygon] = []
        self.cells: List[Cell] = []
        logger.info(f"Initialized VoronoiMap with {len(points)} points, "
                    f"width={width}, height={height}")

    def __str__(self) -> str:
        return f"VoronoiMap with {len(self.points)} points"

    def __repr__(self) -> str:
        return (f"<VoronoiMap(points={self.points!r}, width={self.width}, "
                f"height={self.height}, diagram={self.diagram!r})>")

    def add_points(self, points: List[Tuple[float, float]]) -> None:
        self.points = np.vstack([self.points, np.array(points)])

    def _order_region(self, vertices: np.ndarray) -> np.ndarray:
        centroid = np.mean(vertices, axis=0)
        angles   = np.arctan2(vertices[:, 1] - centroid[1],
                              vertices[:, 0] - centroid[0])
        return vertices[np.argsort(angles)]

    def generate_diagram(self) -> None:
        """Compute and store clipped Voronoi cells; create Cell objects."""
        if self.points.size == 0:
            self.diagram = {}
            logger.warning("No points provided; diagram not generated.")
            return

        self.diagram = Voronoi(self.points)
        bbox = box(0, 0, self.width, self.height)
        self.polygons = []
        self.cells = []

        center = self.diagram.points.mean(axis=0)
        radius = np.linalg.norm(self.diagram.points - center, axis=1).max() * 2

        for point_idx, region_idx in enumerate(self.diagram.point_region):
            region = self.diagram.regions[region_idx]
            if not region or len(region) == 0:  # pragma: no cover
                continue

            if -1 not in region:
                polygon = Polygon([self.diagram.vertices[i] for i in region])
            else:
                ridge_vertices = []
                for (p1, p2), (v1, v2) in zip(self.diagram.ridge_points,
                                               self.diagram.ridge_vertices):
                    if point_idx not in (p1, p2):
                        continue
                    if v1 == -1 or v2 == -1:
                        finite_v  = v2 if v1 == -1 else v1
                        t         = self.diagram.points[p2] - self.diagram.points[p1]
                        t        /= np.linalg.norm(t)
                        n         = np.array([-t[1], t[0]])
                        midpoint  = self.diagram.points[[p1, p2]].mean(axis=0)
                        direction = np.sign(np.dot(midpoint - center, n)) * n
                        far_point = self.diagram.vertices[finite_v] + direction * radius
                        ridge_vertices.append(tuple(self.diagram.vertices[finite_v]))
                        ridge_vertices.append(tuple(far_point))
                    else:
                        ridge_vertices.append(tuple(self.diagram.vertices[v1]))
                        ridge_vertices.append(tuple(self.diagram.vertices[v2]))

                ridge_vertices = np.array(list(dict.fromkeys(ridge_vertices)))
                if len(ridge_vertices) < 3:  # pragma: no cover
                    continue
                centroid = ridge_vertices.mean(axis=0)
                angles   = np.arctan2(ridge_vertices[:, 1] - centroid[1],
                                      ridge_vertices[:, 0] - centroid[0])
                polygon  = Polygon(ridge_vertices[np.argsort(angles)])

            clipped = polygon.intersection(bbox)
            if not clipped.is_empty and clipped.geom_type == 'Polygon':
                self.polygons.append(clipped)
                cell = Cell(
                    index=len(self.cells),
                    center=tuple(self.diagram.points[point_idx]),
                    polygon=clipped
                )
                self.cells.append(cell)

        logger.info(f"Voronoi: {len(self.polygons)} polygons, {len(self.cells)} cells.")

    def get_cells(self) -> List[Cell]:
        return self.cells

    def get_cell(self, index: int) -> Optional[Cell]:
        if 0 <= index < len(self.cells):
            return self.cells[index]
        return None

    def get_cell_at_position(self, x: float, y: float) -> Optional[Cell]:
        point = Point(x, y)
        for cell in self.cells:
            if cell.polygon.contains(point):
                return cell
        return None

    # ------------------------------------------------------------------
    # Visualisation
    # ------------------------------------------------------------------

    def visualize_points(self) -> None:
        if self.points.size == 0:
            print("No points to visualize.")
            return
        xs, ys = zip(*self.points)
        plt.figure(figsize=(8, 8))
        plt.scatter(xs, ys, c='blue', s=20, alpha=0.6)
        plt.title("Voronoi Points", fontsize=14, fontweight='bold')
        plt.xlim(0, self.width)
        plt.ylim(0, self.height)
        plt.axis('equal')
        plt.tight_layout()

    def visualize_cells(self, show_metadata: bool = False) -> None:
        if not self.polygons:
            print("No Voronoi diagram to visualize.")
            return
        fig, ax = plt.subplots(figsize=(10, 10))
        for poly in self.polygons:
            x, y = poly.exterior.xy
            ax.fill(x, y, alpha=0.4, edgecolor='black', linewidth=0.5)
        ax.scatter(self.points[:, 0], self.points[:, 1],
                   c='red', s=15, zorder=10, alpha=0.7)
        if show_metadata and self.cells:
            for cell in self.cells:
                ax.text(cell.center[0], cell.center[1], str(cell.index),
                        ha='center', va='center', fontsize=8, color='darkred',
                        weight='bold',
                        bbox=dict(boxstyle='round,pad=0.3', facecolor='yellow', alpha=0.7))
        ax.set_xlim(0, self.width)
        ax.set_ylim(0, self.height)
        ax.set_aspect('equal')
        title = "Voronoi Map" + (" (with cell indices)" if show_metadata else "")
        plt.title(title, fontsize=14, fontweight='bold')
        plt.tight_layout()

    def visualize_cell_property(self, property_name: str) -> None:
        if not self.cells:
            print("No cells to visualize.")
            return

        fig, ax = plt.subplots(figsize=(10, 10))
        values = []
        for cell in self.cells:
            if hasattr(cell, property_name):
                values.append(getattr(cell, property_name))
            else:
                print(f"Error: Cells do not have property '{property_name}'")
                return

        if all(isinstance(v, (int, float)) for v in values):
            min_val, max_val = min(values), max(values)
            if max_val > min_val:
                normalized = [(v - min_val) / (max_val - min_val) for v in values]
            else:
                normalized = [0.5] * len(values)

            for cell, norm_val in zip(self.cells, normalized):
                x, y = cell.polygon.exterior.xy
                ax.fill(x, y, alpha=0.7, edgecolor='black', linewidth=0.5,
                        facecolor=plt.cm.terrain(norm_val))

            sm = plt.cm.ScalarMappable(cmap=plt.cm.terrain,
                                       norm=plt.Normalize(vmin=min_val, vmax=max_val))
            sm.set_array([])
            cbar = plt.colorbar(sm, ax=ax, label=property_name.replace('_', ' ').title())
            cbar.ax.tick_params(labelsize=10)
            avg_val = sum(values) / len(values)
            ax.text(0.02, 0.98,
                    f"Min: {min_val:.1f}\nMax: {max_val:.1f}\nAvg: {avg_val:.1f}",
                    transform=ax.transAxes, fontsize=10, verticalalignment='top',
                    bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))
        else:
            from imperial_generals.config import get_config
            unique_vals = list(set(values))
            terrain_colors = get_config()['visualization']['terrain_colors']
            color_map = {v: terrain_colors.get(v, '#aaaaaa') for v in unique_vals}
            for cell in self.cells:
                val  = getattr(cell, property_name)
                x, y = cell.polygon.exterior.xy
                ax.fill(x, y, alpha=0.7, edgecolor='black', linewidth=0.5,
                        facecolor=color_map[val])
            from matplotlib.patches import Patch
            ax.legend(handles=[Patch(facecolor=color_map[v], label=v) for v in unique_vals],
                      title=property_name.replace('_', ' ').title(),
                      loc='upper right', fontsize=10)

        ax.set_xlim(0, self.width)
        ax.set_ylim(0, self.height)
        ax.set_aspect('equal')
        plt.title(f"Voronoi Map - {property_name.replace('_', ' ').title()}",
                  fontsize=14, fontweight='bold')
        plt.tight_layout()


if __name__ == "__main__":  # pragma: no cover
    pts = PoissonDiscSampler.generate(100, 100, 5)
    vm  = VoronoiMap(pts, width=100, height=100)
    vm.generate_diagram()
    vm.visualize_cells()
