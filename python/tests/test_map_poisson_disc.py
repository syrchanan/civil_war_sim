import pytest
import numpy as np
from imperial_generals.map import PoissonDiscSampler

def test_generate_basic():
    points = PoissonDiscSampler.generate(100, 100, 10)
    assert isinstance(points, list)
    assert all(isinstance(pt, tuple) and len(pt) == 2 for pt in points)
    assert all(0 <= pt[0] < 100 and 0 <= pt[1] < 100 for pt in points)

def test_min_distance_enforced():
    points = PoissonDiscSampler.generate(50, 50, 5)
    for i, pt1 in enumerate(points):
        for pt2 in points[i+1:]:
            dist = np.linalg.norm(np.array(pt1) - np.array(pt2))
            assert dist >= 5 - 1e8 # tolerance for floating point errors

def test_empty_area():
    points = PoissonDiscSampler.generate(0, 0, 10)
    assert points == []

def test_small_area():
    points = PoissonDiscSampler.generate(1, 1, 2)
    assert len(points) <= 1

def test_large_k():
    points = PoissonDiscSampler.generate(100, 100, 10, k=100)
    assert isinstance(points, list)

def test_invalid_types():
    with pytest.raises(TypeError):
        PoissonDiscSampler.generate("100", 100, 10)
    with pytest.raises(TypeError):
        PoissonDiscSampler.generate(100, None, 10)
    with pytest.raises(TypeError):
        PoissonDiscSampler.generate(100, 100, [10])

def test_negative_values():
    with pytest.raises(ValueError):
        PoissonDiscSampler.generate(-100, 100, 10)
    with pytest.raises(ValueError):
        PoissonDiscSampler.generate(100, -100, 10)
    with pytest.raises(ValueError):
        PoissonDiscSampler.generate(100, 100, -10)

def test_zero_min_distance():
    with pytest.raises(ValueError):
        PoissonDiscSampler.generate(100, 100, 0)

def test_points_within_bounds():
    points = PoissonDiscSampler.generate(20, 30, 2)
    for x, y in points:
        assert 0 <= x < 20
        assert 0 <= y < 30