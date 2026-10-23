import json
import math
import os

import pytest

from imperial_generals.utils.fdlibm import exp, log


# Expected values are V8's Math.log / Math.exp (fdlibm), shared with the TypeScript port.
with open(os.path.join(os.path.dirname(__file__), '../../test_cases/parity/fdlibm.json'), encoding='utf-8') as f:
    V8 = json.load(f)
V8_LOG = [tuple(row[:2]) for row in V8['log']]      # rows: [x, expected] or [x, expected, note]


@pytest.mark.parametrize("x, expected", V8_LOG)
def test_log_matches_v8_bit_for_bit(x, expected):
    assert log(x) == expected


def test_log_zero_is_negative_infinity():
    assert log(0.0) == -math.inf


def test_log_negative_is_nan():
    assert math.isnan(log(-1.0))


def test_log_infinity_and_nan_pass_through():
    assert log(math.inf) == math.inf
    assert math.isnan(log(math.nan))


# =============================================================================
# exp (V8 Math.exp goldens)
# =============================================================================

V8_EXP = [tuple(row[:2]) for row in V8['exp']]


@pytest.mark.parametrize("x, expected", V8_EXP)
def test_exp_matches_v8_bit_for_bit(x, expected):
    assert exp(x) == expected


def test_exp_overflow_is_infinity():
    assert exp(709.8) == math.inf


def test_exp_infinities_and_nan():
    assert exp(math.inf) == math.inf
    assert exp(-math.inf) == 0.0
    assert math.isnan(exp(math.nan))
