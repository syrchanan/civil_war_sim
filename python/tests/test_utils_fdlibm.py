import math

import pytest

from imperial_generals.utils.fdlibm import exp, log


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
    (1.4, 0.33647223662121284),                  # k == 0, i > 0 branch
    (1.39, 0.3293037471426003),
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


# =============================================================================
# exp (V8 Math.exp goldens)
# =============================================================================

V8_EXP = [
    (0.0, 1.0),
    (1.0, 2.718281828459045),
    (-1.0, 0.36787944117144233),
    (0.5, 1.6487212707001282),
    (-0.5, 0.6065306597126334),
    (0.34657359027997264, 1.414213562373095),     # |x| just above 0.5*ln2
    (0.3, 1.3498588075760032),
    (1.0397207708399179, 2.82842712474619),       # 0.5*ln2 < |x| < 1.5*ln2 branch
    (1.2, 3.3201169227365472),
    (2.0, 7.38905609893065),
    (-2.0, 0.1353352832366127),
    (10.0, 22026.465794806718),
    (-10.0, 0.00004539992976248485),
    (-0.0001, 0.9999000049998333),
    (1e-9, 1.000000001),
    (-1e-9, 0.999999999),
    (1e-30, 1.0),                                  # |x| < 2**-28 branch
    (100.0, 2.6881171418161356e+43),
    (-100.0, 3.720075976020836e-44),
    (700.0, 1.0142320547350045e+304),
    (709.7, 1.6549840276802644e+308),
    (-708.0, 3.307553003638408e-308),
    (-740.0, 4.2e-322),                            # subnormal result
    (-745.1, 5e-324),
    (-746.0, 0.0),                                 # underflow
    (-0.6931471805599453, 0.5),
    (-3.4657359027997265, 0.03125),
    (-0.013862943611198907, 0.9862327044933592),   # shock-decay-sized steps
    (-5.545177444479562, 0.003906250000000001),
]


@pytest.mark.parametrize("x, expected", V8_EXP)
def test_exp_matches_v8_bit_for_bit(x, expected):
    assert exp(x) == expected


def test_exp_overflow_is_infinity():
    assert exp(709.8) == math.inf


def test_exp_infinities_and_nan():
    assert exp(math.inf) == math.inf
    assert exp(-math.inf) == 0.0
    assert math.isnan(exp(math.nan))
