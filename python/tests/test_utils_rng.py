import math

import pytest

from imperial_generals.utils import Rng
from imperial_generals.utils.fdlibm import log as fdlibm_log


# Reference values were produced by an independent JavaScript implementation
# (the future TypeScript port must reproduce them exactly). The raw [1, 2, 3, 4]
# sequence matches the published xoshiro128** reference vector.


# =============================================================================
# Core generator — xoshiro128**
# =============================================================================

def test_xoshiro_reference_vector():
    rng = Rng.from_state([1, 2, 3, 4])
    assert [rng.next_u32() for _ in range(5)] == [11520, 0, 5927040, 70819200, 2031721883]


def test_seeded_u32_sequence_matches_js_reference():
    rng = Rng(42)
    assert [rng.next_u32() for _ in range(5)] == [660444221, 3652823732, 77672526, 910233633, 2297337756]


def test_seed_expands_to_state_via_splitmix32():
    assert Rng(42).state == [551831576, 144025891, 322543647, 3034809370]


def test_same_seed_same_sequence():
    a, b = Rng(123), Rng(123)
    assert [a.next_u32() for _ in range(100)] == [b.next_u32() for _ in range(100)]


def test_different_seed_different_sequence():
    a, b = Rng(1), Rng(2)
    assert [a.next_u32() for _ in range(10)] != [b.next_u32() for _ in range(10)]


def test_u32_outputs_are_in_range():
    rng = Rng(9)
    assert all(0 <= rng.next_u32() < 2**32 for _ in range(1000))


# =============================================================================
# Seed validation
# =============================================================================

@pytest.mark.parametrize("seed", [0, 1, 2**32 - 1])
def test_valid_seeds(seed):
    Rng(seed)


@pytest.mark.parametrize("seed", [-1, 2**32])
def test_out_of_range_seed_raises(seed):
    with pytest.raises(ValueError):
        Rng(seed)


@pytest.mark.parametrize("seed", [1.5, "42", None, True])
def test_non_int_seed_raises(seed):
    with pytest.raises(TypeError):
        Rng(seed)


# =============================================================================
# State round-trip (for battle serialization)
# =============================================================================

def test_state_round_trip_resumes_sequence():
    rng = Rng(5)
    for _ in range(10):
        rng.next_u32()
    resumed = Rng.from_state(rng.state)
    assert [resumed.next_u32() for _ in range(20)] == [rng.next_u32() for _ in range(20)]


def test_seed_is_remembered():
    assert Rng(42).seed == 42
    assert Rng.from_state([1, 2, 3, 4]).seed is None


def test_state_is_a_copy():
    rng = Rng(5)
    snapshot = rng.state
    rng.next_u32()
    assert snapshot != rng.state


@pytest.mark.parametrize("state", [[1, 2, 3], [1, 2, 3, 4, 5], [0, 0, 0, 0], [1, 2, 3, -4], [1, 2, 3, 2**32], [1, 2, 3, 4.0]])
def test_invalid_state_raises(state):
    with pytest.raises(ValueError):
        Rng.from_state(state)


# =============================================================================
# Uniform floats
# =============================================================================

def test_random_matches_js_reference():
    rng = Rng(42)
    assert [rng.random() for _ in range(3)] == [0.15377165265745885, 0.018084542542176507, 0.5348906284683476]


def test_random_uses_53_bits_from_two_draws():
    a, b = Rng(11), Rng(11)
    hi, lo = b.next_u32(), b.next_u32()
    assert a.random() == ((hi >> 5) * 67108864 + (lo >> 6)) / 9007199254740992


def test_random_in_unit_interval():
    rng = Rng(3)
    assert all(0.0 <= rng.random() < 1.0 for _ in range(10_000))


# =============================================================================
# Exponential sampling
# =============================================================================

def test_exponential_matches_js_reference():
    rng = Rng(7)
    assert [rng.exponential(2.0) for _ in range(3)] == [0.02512565165840173, 1.3285826551810358, 0.25311523884393994]


def test_exponential_is_inverse_cdf_of_random():
    a, b = Rng(8), Rng(8)
    assert a.exponential(3.0) == -fdlibm_log(1.0 - b.random()) / 3.0


def test_exponential_mean_approximates_inverse_rate():
    rng = Rng(2024)
    n = 20_000
    mean = sum(rng.exponential(4.0) for _ in range(n)) / n
    assert mean == pytest.approx(0.25, rel=0.03)


@pytest.mark.parametrize("rate", [0, -1.0, math.inf, math.nan])
def test_exponential_invalid_rate_raises(rate):
    with pytest.raises(ValueError):
        Rng(1).exponential(rate)
