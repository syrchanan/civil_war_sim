"""
Poisson disc sampling for 2D point generation.
"""

import random
import math
import numpy as np
from collections import defaultdict

class PoissonDiscSampler:
    @staticmethod
    def generate(width, height, min_distance, k=30):
        cell_size = min_distance / np.sqrt(2)
        grid_width = int(np.ceil(width / cell_size))
        grid_height = int(np.ceil(height / cell_size))
        grid = defaultdict(list)
        points = []
        active = []

        # Initial point
        pt = (np.random.uniform(0, width), np.random.uniform(0, height))
        points.append(pt)
        active.append(pt)
        grid[(int(pt[0] // cell_size), int(pt[1] // cell_size))].append(pt)

        while active:
            idx = np.random.randint(len(active))
            center = active[idx]
            found = False
            for _ in range(k):
                angle = np.random.uniform(0, 2 * np.pi)
                r = np.random.uniform(min_distance, 2 * min_distance)
                new_pt = (
                    center[0] + r * np.cos(angle),
                    center[1] + r * np.sin(angle)
                )
                if not (0 <= new_pt[0] < width and 0 <= new_pt[1] < height):
                    continue
                gx, gy = int(new_pt[0] // cell_size), int(new_pt[1] // cell_size)
                neighbors = [
                    pt for dx in [-1, 0, 1] for dy in [-1, 0, 1]
                    for pt in grid.get((gx + dx, gy + dy), [])
                ]
                if all(np.linalg.norm(np.array(new_pt) - np.array(npt)) >= min_distance for npt in neighbors):
                    points.append(new_pt)
                    active.append(new_pt)
                    grid[(gx, gy)].append(new_pt)
                    found = True
                    break
            if not found:
                active.pop(idx)
        return points


if __name__ == "__main__":
    samples = PoissonDiscSampler.generate(1000, 1000, 10)
    print(f"Generated {len(samples)} points.")
    for point in samples:
        print(point)