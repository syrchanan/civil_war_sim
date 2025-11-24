"""
Poisson disc sampling for 2D point generation.
"""

# base libs
from typing import List, Tuple
import logging
from collections import defaultdict

# ext libs
import numpy as np
from scipy.spatial import KDTree

# Inherit logging configuration from the main application
logger = logging.getLogger(__name__)

class PoissonDiscSampler:
    """
    Implements Poisson disc sampling for generating evenly distributed 2D points.
    """

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
            width (float): Width of the sampling area.
            height (float): Height of the sampling area.
            min_distance (float): Minimum allowed distance between points.
            k (int, optional): Number of attempts per active point. Defaults to 30.

        Returns:
            List[Tuple[float, float]]: List of sampled (x, y) points.
        """
        # Type checks
        if not isinstance(width, (int, float)):
            raise TypeError("width must be a number")
        if not isinstance(height, (int, float)):
            raise TypeError("height must be a number")
        if not isinstance(min_distance, (int, float)):
            raise TypeError("min_distance must be a number")
        if not isinstance(k, int):
            raise TypeError("k must be an integer")
        # Value checks
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

        cell_size = min_distance / 2 # Cell size for grid
        grid_width = int(np.ceil(width / cell_size)) # Number of cells in x direction
        grid_height = int(np.ceil(height / cell_size)) # Number of cells in y direction
        grid: defaultdict[Tuple[int, int], List[Tuple[float, float]]] = defaultdict(list) # Spatial grid initialization
        points: List[Tuple[float, float]] = [] # Final list of points
        active: List[Tuple[float, float]] = [] # List of active points

        logger.info("Starting Poisson disc sampling: width=%s, height=%s, min_distance=%s, k=%s", width, height, min_distance, k)
        logger.debug("Cell size: %s, Grid size: (%s, %s)", cell_size, grid_width, grid_height)

        # Generate the initial random point
        pt = (np.random.uniform(0, width), np.random.uniform(0, height))
        points.append(pt)
        active.append(pt)
        grid[(int(pt[0] // cell_size), int(pt[1] // cell_size))].append(pt)
        logger.info("Initial point: %s", pt)

        # Main loop: process active points
        while active:
            idx = np.random.randint(len(active))
            center = active[idx]
            found = False
            logger.debug("Processing active point: %s (index %s)", center, idx)

            # Build KDTree from current points (if any)
            tree = KDTree(points) if points else None

            # Try up to k times to generate a valid new point
            for attempt in range(k):
                angle = np.random.uniform(0, 2 * np.pi)
                r = np.random.uniform(min_distance, 2 * min_distance)
                new_pt = (
                    center[0] + r * np.cos(angle),
                    center[1] + r * np.sin(angle)
                )
                logger.debug("Attempt %s: Generated candidate point %s", attempt, new_pt)

                # Check if the new point is within bounds
                if not (0 <= new_pt[0] < width and 0 <= new_pt[1] < height):
                    logger.debug("Candidate point %s out of bounds", new_pt)
                    continue

                gx, gy = int(new_pt[0] // cell_size), int(new_pt[1] // cell_size)

                # Use KDTree to check for neighbors within min_distance
                if tree is not None:
                    close_idx = tree.query_ball_point(new_pt, min_distance - 1e-8)
                    if close_idx:
                        logger.debug("Candidate point %s too close to KDTree neighbors", new_pt)
                        continue
                
                # Accept the new point:
                points.append(new_pt)
                active.append(new_pt)
                grid[(gx, gy)].append(new_pt)
                found = True
                logger.info("Accepted new point: %s", new_pt)
                break

            # If no valid point was found, remove the center from active list
            if not found:
                logger.debug("No valid point found for active point %s, removing from active list", center)
                active.pop(idx)

        logger.info("Sampling complete. Generated %d points.", len(points))
        return points


if __name__ == "__main__":
    samples = PoissonDiscSampler.generate(100, 100, 5)
    print(f"Generated {len(samples)} points.")
