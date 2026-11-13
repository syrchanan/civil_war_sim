"""
Cosine and sine of an angle in degrees, bit-identical in Python and the TypeScript port (web/src/engine/trig.ts).

Library ``sin`` / ``cos`` may differ in the last bit between platforms, so these use only + - * /, which IEEE
doubles do the same everywhere: the angle is reduced exactly to [-45, 45] degrees (subtracting whole multiples of
90 and folding), turned into radians, and fed to fixed-order Taylor polynomials (error < 1e-16 on that range).
Used for facings (compass degrees), so arguments are moderate.
"""

_RAD = 0.017453292519943295          # pi / 180

# Taylor coefficients: sin x = x (1 - x²/3! + x⁴/5! - ...), cos x = 1 - x²/2! + x⁴/4! - ...
_S = (-1 / 6, 1 / 120, -1 / 5040, 1 / 362880, -1 / 39916800, 1 / 6227020800, -1 / 1307674368000)
_C = (-1 / 2, 1 / 24, -1 / 720, 1 / 40320, -1 / 3628800, 1 / 479001600, -1 / 87178291200, 1 / 20922789888000)


def _sin_small(r: float) -> float:
    """sin of r radians, |r| <= pi/4."""
    z = r * r
    p = _S[6]
    for c in (_S[5], _S[4], _S[3], _S[2], _S[1], _S[0]):
        p = c + z * p
    return r + r * (z * p)


def _cos_small(r: float) -> float:
    """cos of r radians, |r| <= pi/4."""
    z = r * r
    p = _C[7]
    for c in (_C[6], _C[5], _C[4], _C[3], _C[2], _C[1], _C[0]):
        p = c + z * p
    return 1.0 + z * p


def _reduce(degrees: float) -> tuple:
    """(quarter turn 0-3, angle in [0, 90)) for any angle in degrees."""
    d = degrees % 360.0
    if d < 0:            # pragma: no cover - Python's % is never negative for a positive divisor
        d += 360.0
    quarter = 0
    while d >= 90.0 and quarter < 3:
        d -= 90.0
        quarter += 1
    if d >= 90.0:        # rounding at the very top of the turn
        d, quarter = 0.0, 0
    return quarter, d


def _first_quarter(d: float) -> tuple:
    """(cos, sin) of d degrees, 0 <= d < 90."""
    if d > 45.0:
        r = (90.0 - d) * _RAD
        return _sin_small(r), _cos_small(r)
    r = d * _RAD
    return _cos_small(r), _sin_small(r)


def cos_deg(degrees: float) -> float:
    quarter, d = _reduce(degrees)
    c, s = _first_quarter(d)
    return (c, -s, -c, s)[quarter] + 0.0      # + 0.0: no negative zero


def sin_deg(degrees: float) -> float:
    quarter, d = _reduce(degrees)
    c, s = _first_quarter(d)
    return (s, c, -s, -c)[quarter] + 0.0
