import math

import pytest

from imperial_generals.utils.fdlibm import log


# Expected values are V8's Math.log (itself an fdlibm port), so the TypeScript
# port gets identical results whether it calls Math.log or ports this module.
V8_LOG = [
    (1.0, 0.0),
    (0.5, -0.6931471805599453),
    (2.0, 0.6931471805599453),
    (0.95, -0.05129329438755058),
    (0.07014678454301787, -2.6571653103620725),
    (0.6027634319710867, -0.5062304776878799),   # platform libm differs by 1 ulp here
    (1e-300, -690.7755278982137),
    (5e-324, -744.4400719213812),                # smallest subnormal
    (2.2250738585072014e-308, -708.3964185322641),
    (1 - 2**-53, -1.1102230246251565e-16),
    (1 + 2**-52, 2.2204460492503128e-16),
    (0.9999990463256836, -9.5367477115389e-7),   # |f| < 2**-20 branch
    (1.0000009536743164, 9.536738616591883e-7),
    (math.e, 1.0),
    (10.0, 2.302585092994046),
    (123456.789, 11.723646487185881),
    (1.7976931348623157e308, 709.782712893384),
    (0.1, -2.3025850929940455),
    (0.3, -1.2039728043259361),
    (0.7, -0.35667494393873245),
]


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
