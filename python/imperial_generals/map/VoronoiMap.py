
"""
Voronoi diagram computation utilities.
"""

import numpy as np
from scipy.spatial import Voronoi
from shapely.geometry import Polygon, box, Point
import matplotlib.pyplot as plt
from typing import List, Tuple, Any, Optional
import logging
from imperial_generals.map.Cell import Cell

# Configure logging for this module
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class VoronoiMap:
    def __init__(self, points: List[Tuple[float, float]], width: int = 100, height: int = 100) -> None:
        """
        Initialize the VoronoiMap.

        Args:
            points (List[Tuple[float, float]]): List of (x, y) points.
            width (int): Width of the bounding rectangle.
            height (int): Height of the bounding rectangle.
        """
        self.points: np.ndarray = np.array(points)
        self.width: int = width
        self.height: int = height
        self.diagram: Optional[Voronoi] = None
        self.polygons: List[Polygon] = []
        self.cells: List[Cell] = []
        logger.info(f"Initialized VoronoiMap with {len(points)} points, width={width}, height={height}")


    def __str__(self) -> str:
        """String representation of VoronoiMap."""
        return f"VoronoiMap with {len(self.points)} points"


    def __repr__(self) -> str:
        """Detailed representation of VoronoiMap."""
        return (
            f"<VoronoiMap(points={self.points!r}, width={self.width}, height={self.height}, diagram={self.diagram!r})>"
        )


    def add_points(self, points: List[Tuple[float, float]]) -> None:
        """
        Add points to the diagram.
        Args:
            points (List[Tuple[float, float]]): Points to add.
        """
        # Note: np.ndarray does not have 'extend', so this may need to be np.vstack or np.concatenate in real usage.
        self.points = np.vstack([self.points, np.array(points)])
        logger.info(f"Added {len(points)} points. Total now: {len(self.points)}")


    def _order_region(self, vertices: np.ndarray) -> np.ndarray:
        """
        Order vertices counterclockwise around centroid.
        Args:
            vertices (np.ndarray): Array of vertex coordinates.
        Returns:
            np.ndarray: Ordered vertices.
        """
        centroid = np.mean(vertices, axis=0)
        angles = np.arctan2(vertices[:,1] - centroid[1], vertices[:,0] - centroid[0])
        return vertices[np.argsort(angles)]


    def generate_diagram(self) -> None:
        """
        Compute the Voronoi diagram and store the clipped cells, including infinite regions.
        Handles both finite and infinite regions by reconstructing polygons and clipping to bounding box.
        Creates Cell objects for each polygon with metadata.
        """
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
            if not region or len(region) == 0:
                continue

            if -1 not in region:
                # Finite region: create polygon from vertices
                polygon = Polygon([self.diagram.vertices[i] for i in region])
            else:
                # Infinite region: reconstruct polygon by extending infinite ridges
                ridge_vertices = []
                for (p1, p2), (v1, v2) in zip(self.diagram.ridge_points, self.diagram.ridge_vertices):
                    if point_idx not in (p1, p2):
                        continue
                    if v1 == -1 or v2 == -1:
                        # Infinite ridge: extend to bounding box
                        finite_v = v2 if v1 == -1 else v1
                        t = self.diagram.points[p2] - self.diagram.points[p1]
                        t /= np.linalg.norm(t)
                        n = np.array([-t[1], t[0]])
                        midpoint = self.diagram.points[[p1, p2]].mean(axis=0)
                        direction = np.sign(np.dot(midpoint - center, n)) * n
                        far_point = self.diagram.vertices[finite_v] + direction * radius
                        ridge_vertices.append(tuple(self.diagram.vertices[finite_v]))
                        ridge_vertices.append(tuple(far_point))
                    else:
                        ridge_vertices.append(tuple(self.diagram.vertices[v1]))
                        ridge_vertices.append(tuple(self.diagram.vertices[v2]))
                # Remove duplicates and order vertices
                ridge_vertices = np.array(list(dict.fromkeys(ridge_vertices)))
                if len(ridge_vertices) < 3:
                    continue
                centroid = ridge_vertices.mean(axis=0)
                angles = np.arctan2(ridge_vertices[:,1] - centroid[1], ridge_vertices[:,0] - centroid[0])
                ridge_vertices = ridge_vertices[np.argsort(angles)]
                polygon = Polygon(ridge_vertices)

            # Clip polygon to bounding box
            clipped = polygon.intersection(bbox)
            if not clipped.is_empty and clipped.geom_type == 'Polygon':
                self.polygons.append(clipped)
                # Create Cell object with the original point as center
                cell_center = tuple(self.diagram.points[point_idx])
                cell = Cell(
                    index=len(self.cells),
                    center=cell_center,
                    polygon=clipped
                )
                self.cells.append(cell)

        logger.info(f"Generated Voronoi diagram with {len(self.polygons)} polygons and {len(self.cells)} cells.")

    def get_cells(self) -> List[Cell]:
        """
        Return the list of Cell objects.

        Returns:
            List[Cell]: List of Cell objects with metadata.
        """
        return self.cells

    def get_cell(self, index: int) -> Optional[Cell]:
        """
        Get a cell by its index.

        Args:
            index (int): The cell index.

        Returns:
            Optional[Cell]: The Cell object, or None if index is invalid.
        """
        if 0 <= index < len(self.cells):
            return self.cells[index]
        return None

    def get_cell_at_position(self, x: float, y: float) -> Optional[Cell]:
        """
        Find the cell containing the given (x, y) coordinates.

        Args:
            x (float): X coordinate.
            y (float): Y coordinate.

        Returns:
            Optional[Cell]: The Cell containing the point, or None if not found.
        """
        point = Point(x, y)
        for cell in self.cells:
            if cell.polygon.contains(point):
                return cell
        return None


    def visualize_points(self) -> None:
        """
        Visualize the input points using matplotlib.
        In Positron/Jupyter, the plot will automatically appear in the viewer.
        """
        if self.points.size == 0:
            logger.warning("No points to visualize.")
            print("No points to visualize.")
            return
        xs, ys = zip(*self.points)
        plt.figure(figsize=(8, 8))
        plt.scatter(xs, ys, c='blue', s=20, alpha=0.6)
        plt.title("Voronoi Points", fontsize=14, fontweight='bold')
        plt.xlabel("X", fontsize=12)
        plt.ylabel("Y", fontsize=12)
        plt.xlim(0, self.width)
        plt.ylim(0, self.height)
        plt.axis('equal')
        plt.grid(True, alpha=0.3)
        plt.tight_layout()


    def visualize_cells(self, show_metadata: bool = False) -> None:
        """
        Visualize the Voronoi cells (polygons) and input points using matplotlib.
        In Positron/Jupyter, the plot will automatically appear in the viewer.

        Args:
            show_metadata (bool): If True, display cell indices at centers.
        """
        if not self.polygons:
            logger.warning("No Voronoi diagram to visualize.")
            print("No Voronoi diagram to visualize.")
            return

        fig, ax = plt.subplots(figsize=(10, 10))

        for poly in self.polygons:
            x, y = poly.exterior.xy
            ax.fill(x, y, alpha=0.4, edgecolor='black', linewidth=0.5)

        # Plot the points
        ax.scatter(self.points[:, 0], self.points[:, 1], c='red', s=15, zorder=10, alpha=0.7)

        # Optionally show metadata
        if show_metadata and self.cells:
            for cell in self.cells:
                # Draw cell index at center
                ax.text(
                    cell.center[0], cell.center[1],
                    str(cell.index),
                    ha='center', va='center',
                    fontsize=8, color='darkred', weight='bold',
                    bbox=dict(boxstyle='round,pad=0.3', facecolor='yellow', alpha=0.7)
                )

        ax.set_xlim(0, self.width)
        ax.set_ylim(0, self.height)
        ax.set_aspect('equal')
        ax.set_xlabel('X', fontsize=12)
        ax.set_ylabel('Y', fontsize=12)
        title = "Voronoi Map" + (" (with cell indices)" if show_metadata else "")
        plt.title(title, fontsize=14, fontweight='bold')
        plt.tight_layout()

    def visualize_cell_property(self, property_name: str) -> None:
        """
        Visualize cells colored by a specific property (e.g., 'elevation', 'cover_value').

        In Positron/Jupyter, the plot will automatically appear in the viewer.
        In other environments, you may need to call plt.show() separately.

        Args:
            property_name (str): Name of the Cell property to visualize.
        """
        if not self.cells:
            logger.warning("No cells to visualize.")
            print("No cells to visualize.")
            return

        fig, ax = plt.subplots(figsize=(10, 10))

        # Collect property values
        values = []
        for cell in self.cells:
            if hasattr(cell, property_name):
                values.append(getattr(cell, property_name))
            else:
                logger.warning(f"Cell does not have property '{property_name}'")
                print(f"Error: Cells do not have property '{property_name}'")
                return

        # Normalize values for coloring
        if all(isinstance(v, (int, float)) for v in values):
            min_val = min(values)
            max_val = max(values)
            if max_val > min_val:
                normalized = [(v - min_val) / (max_val - min_val) for v in values]
            else:
                normalized = [0.5] * len(values)

            # Plot cells with color based on property value
            for cell, norm_val in zip(self.cells, normalized):
                x, y = cell.polygon.exterior.xy
                ax.fill(x, y, alpha=0.7, edgecolor='black', linewidth=0.5,
                       facecolor=plt.cm.terrain(norm_val))

            # Add colorbar
            sm = plt.cm.ScalarMappable(
                cmap=plt.cm.terrain,
                norm=plt.Normalize(vmin=min_val, vmax=max_val)
            )
            sm.set_array([])
            cbar = plt.colorbar(sm, ax=ax, label=property_name.replace('_', ' ').title())
            cbar.ax.tick_params(labelsize=10)

            # Add statistics text
            avg_val = sum(values) / len(values)
            stats_text = f"Min: {min_val:.1f}\nMax: {max_val:.1f}\nAvg: {avg_val:.1f}"
            ax.text(0.02, 0.98, stats_text, transform=ax.transAxes,
                   fontsize=10, verticalalignment='top',
                   bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))
        else:
            # For non-numeric properties (like terrain_type), use distinct colors
            unique_vals = list(set(values))
            color_map = {val: plt.cm.tab10(i / len(unique_vals))
                        for i, val in enumerate(unique_vals)}

            for cell in self.cells:
                val = getattr(cell, property_name)
                x, y = cell.polygon.exterior.xy
                ax.fill(x, y, alpha=0.7, edgecolor='black', linewidth=0.5,
                       facecolor=color_map[val])

            # Create legend
            from matplotlib.patches import Patch
            legend_elements = [Patch(facecolor=color_map[val], label=val)
                             for val in unique_vals]
            ax.legend(handles=legend_elements, title=property_name.replace('_', ' ').title(),
                     loc='upper right', fontsize=10)

        ax.set_xlim(0, self.width)
        ax.set_ylim(0, self.height)
        ax.set_aspect('equal')
        ax.set_xlabel('X', fontsize=12)
        ax.set_ylabel('Y', fontsize=12)
        plt.title(f"Voronoi Map - {property_name.replace('_', ' ').title()}",
                 fontsize=14, fontweight='bold')
        plt.tight_layout()

if __name__ == "__main__":
    from imperial_generals.map import PoissonDiscSampler
    sample_points = PoissonDiscSampler.generate(100, 100, 5)
    voronoi = VoronoiMap(sample_points, width=100, height=100)
    voronoi.visualize_points()
    voronoi.generate_diagram()
    voronoi.visualize_cells()

