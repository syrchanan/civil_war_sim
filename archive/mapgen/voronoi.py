"""
Voronoi diagram computation utilities.
"""

import numpy as np
from scipy.spatial import Voronoi
from shapely.geometry import Polygon, box
import matplotlib.pyplot as plt

class VoronoiMap:
    def __init__(self, points, width, height):
        """
        Initialize the VoronoiMap.

        Args:
            points (List[Tuple[float, float]]): List of (x, y) points.
            width (int): Width of the bounding rectangle.
            height (int): Height of the bounding rectangle.
        """
        self.points = np.array(points)
        self.width = width
        self.height = height
        self.diagram = None
        self.polygons = []

    def __str__(self):
        return f"VoronoiMap with {len(self.points)} points"

    def __repr__(self):
        return (
            f"<VoronoiMap(points={self.points!r}, width={self.width}, height={self.height}, diagram={self.diagram!r})>"
        )

    def add_points(self, points):
        """Add points to the diagram."""
        self.points.extend(points)

    def _order_region(self, vertices):
        # Order vertices counterclockwise around centroid
        centroid = np.mean(vertices, axis=0)
        angles = np.arctan2(vertices[:,1] - centroid[1], vertices[:,0] - centroid[0])
        return vertices[np.argsort(angles)]

    def generate_diagram(self):
        """Compute the Voronoi diagram and store the clipped cells, including infinite regions."""
        if self.points.size == 0:
            self.diagram = {}
            return

        self.diagram = Voronoi(self.points)
        bbox = box(0, 0, self.width, self.height)
        self.polygons = []

        center = self.diagram.points.mean(axis=0)
        radius = np.linalg.norm(self.diagram.points - center, axis=1).max() * 2

        for point_idx, region_idx in enumerate(self.diagram.point_region):
            region = self.diagram.regions[region_idx]
            if not region or len(region) == 0:
                continue

            if -1 not in region:
                # Finite region
                polygon = Polygon([self.diagram.vertices[i] for i in region])
            else:
                # Infinite region: reconstruct
                ridge_vertices = []
                for (p1, p2), (v1, v2) in zip(self.diagram.ridge_points, self.diagram.ridge_vertices):
                    if point_idx not in (p1, p2):
                        continue
                    if v1 == -1 or v2 == -1:
                        # Infinite ridge: need to extend
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

            # Clip to bounding box
            clipped = polygon.intersection(bbox)
            if not clipped.is_empty and clipped.geom_type == 'Polygon':
                self.polygons.append(clipped)

    def get_cells(self):
        """Return the Voronoi cells as a dict."""
        return self.diagram

    def visualize_points(self):
        """Visualize the points."""
        if self.points.size == 0:
            print("No points to visualize.")
            return
        xs, ys = zip(*self.points)
        plt.figure(figsize=(6, 6))
        plt.scatter(xs, ys, c='blue', s=10)
        plt.title("Voronoi Points")
        plt.xlabel("X")
        plt.ylabel("Y")
        plt.axis('equal')
        plt.show()

    def visualize_cells(self):
        """Visualize the Voronoi cells (polygons) and points."""
        if not self.polygons:
            print("No Voronoi diagram to visualize.")
            return
        fig, ax = plt.subplots()
        for poly in self.polygons:
            x, y = poly.exterior.xy
            ax.fill(x, y, alpha=0.4, edgecolor='black')
        # Plot the points
        ax.scatter(self.points[:, 0], self.points[:, 1], c='blue', s=10, zorder=10)
        ax.set_xlim(0, self.width)
        ax.set_ylim(0, self.height)
        ax.set_aspect('equal')
        plt.show()

if __name__ == "__main__":
    from mapgen.src.poisson_disc import PoissonDiscSampler
    sample_points = PoissonDiscSampler.generate(100, 100, 10)
    voronoi = VoronoiMap(sample_points, width=100, height=100)
    voronoi.visualize_points()
    voronoi.generate_diagram()
    voronoi.visualize_cells()

