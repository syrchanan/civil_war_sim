"""
Pure-arithmetic ports of fdlibm functions.

Platform libm implementations (e.g. the Windows CRT) can differ from V8's ``Math.log`` in the
last bit. These ports use only IEEE-754 +, -, *, / and bit manipulation, so they give identical
results on every platform and match V8, which itself uses fdlibm. The TypeScript port must use
the same algorithm.

Source: fdlibm 5.3 ``e_log.c`` (Sun Microsystems, freely redistributable).
"""

import struct

_LN2_HI = 6.93147180369123816490e-01   # 3fe62e42 fee00000
_LN2_LO = 1.90821492927058770002e-10   # 3dea39ef 35793c76
_TWO54 = 1.80143985094819840000e+16    # 43500000 00000000
_LG1 = 6.666666666666735130e-01        # 3FE55555 55555593
_LG2 = 3.999999999940941908e-01        # 3FD99999 9997FA04
_LG3 = 2.857142874366239149e-01        # 3FD24924 94229359
_LG4 = 2.222219843214978396e-01        # 3FCC71C5 1D8E78AF
_LG5 = 1.818357216161805012e-01        # 3FC74664 96CB03DE
_LG6 = 1.531383769920937332e-01        # 3FC39A09 D078C69F
_LG7 = 1.479819860511658591e-01        # 3FC2F112 DF3E5244


def _words(x: float) -> tuple[int, int]:
    """(signed high word, unsigned low word) of a double."""
    bits = struct.unpack('<q', struct.pack('<d', x))[0]
    return bits >> 32, bits & 0xFFFFFFFF


def _from_words(hi: int, lo: int) -> float:
    return struct.unpack('<d', struct.pack('<Q', ((hi & 0xFFFFFFFF) << 32) | lo))[0]


def log(x: float) -> float:
    """Natural logarithm, bit-identical to fdlibm ``__ieee754_log`` (and V8 ``Math.log``)."""
    hx, lx = _words(x)
    k = 0
    if hx < 0x00100000:                        # x < 2**-1022
        if ((hx & 0x7FFFFFFF) | lx) == 0:
            return float('-inf')               # log(+-0) = -inf
        if hx < 0:
            return float('nan')                # log(-#) = NaN
        k -= 54
        x *= _TWO54                            # subnormal: scale up
        hx, lx = _words(x)
    if hx >= 0x7FF00000:
        return x + x                           # inf or NaN
    k += (hx >> 20) - 1023
    hx &= 0x000FFFFF
    i = (hx + 0x95F64) & 0x100000
    x = _from_words(hx | (i ^ 0x3FF00000), lx)  # normalize x or x/2
    k += i >> 20
    f = x - 1.0
    if (0x000FFFFF & (2 + hx)) < 3:            # |f| < 2**-20
        if f == 0.0:
            if k == 0:
                return 0.0
            dk = float(k)
            return dk * _LN2_HI + dk * _LN2_LO
        R = f * f * (0.5 - 0.33333333333333333 * f)
        if k == 0:
            return f - R
        dk = float(k)
        return dk * _LN2_HI - ((R - dk * _LN2_LO) - f)
    s = f / (2.0 + f)
    dk = float(k)
    z = s * s
    i = hx - 0x6147A
    w = z * z
    j = 0x6B851 - hx
    t1 = w * (_LG2 + w * (_LG4 + w * _LG6))
    t2 = z * (_LG1 + w * (_LG3 + w * (_LG5 + w * _LG7)))
    i |= j
    R = t2 + t1
    if i > 0:
        hfsq = 0.5 * f * f
        if k == 0:
            return f - (hfsq - s * (hfsq + R))
        return dk * _LN2_HI - ((hfsq - (s * (hfsq + R) + dk * _LN2_LO)) - f)
    if k == 0:
        return f - s * (f - R)
    return dk * _LN2_HI - ((s * (f - R) - dk * _LN2_LO) - f)
