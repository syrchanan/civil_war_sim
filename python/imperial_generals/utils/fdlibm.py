"""
Pure-arithmetic ports of fdlibm functions.

Platform libm implementations (e.g. the Windows CRT) can differ from V8's ``Math.log`` in the
last bit. These ports use only IEEE-754 +, -, *, / and bit manipulation, so they give identical
results on every platform and match V8, which itself uses fdlibm. The TypeScript port must use
the same algorithm.

Sources: fdlibm 5.3 ``e_log.c`` / ``e_exp.c`` (Sun Microsystems, freely redistributable), with ``exp``
following V8's ``ieee754::exp`` variant (power-of-two scaling by multiplication).
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


_HUGE = 1.0e+300
_TWOM1000 = 9.33263618503218878990e-302     # 2**-1000
_TWO1023 = 8.988465674311579539e+307        # 2**1023
_O_THRESHOLD = 7.09782712893383973096e+02   # 0x40862E42 FEFA39EF
_U_THRESHOLD = -7.45133219101941108420e+02  # 0xc0874910 D52D3051
_INVLN2 = 1.44269504088896338700e+00        # 0x3ff71547 652b82fe
_P1 = 1.66666666666666019037e-01            # 0x3FC55555 5555553E
_P2 = -2.77777777770155933842e-03           # 0xBF66C16C 16BEBD93
_P3 = 6.61375632143793436117e-05            # 0x3F11566A AF25DE2C
_P4 = -1.65339022054652515390e-06           # 0xBEBBBD41 C5D26BF1
_P5 = 4.13813679705723846039e-08            # 0x3E663769 72BEA4D0


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


def exp(x: float) -> float:
    """Exponential, bit-identical to V8 ``Math.exp`` (fdlibm ``__ieee754_exp``)."""
    hx, lx = _words(x)
    xsb = 1 if hx < 0 else 0                   # sign bit
    hx &= 0x7FFFFFFF                           # high word of |x|

    if hx >= 0x40862E42:                       # |x| >= 709.78...
        if hx >= 0x7FF00000:
            if ((hx & 0xFFFFF) | lx) != 0:
                return x + x                   # NaN
            return x if xsb == 0 else 0.0      # exp(+-inf) = {inf, 0}
        if x > _O_THRESHOLD:
            return float('inf')                # overflow
        if x < _U_THRESHOLD:
            return 0.0                         # underflow

    k = 0
    hi = lo = 0.0
    if hx > 0x3FD62E42:                        # |x| > 0.5 ln2: argument reduction
        if hx < 0x3FF0A2B2:                    # and |x| < 1.5 ln2
            if x == 1.0:
                return 2.718281828459045       # V8 special case: fdlibm is 1 ulp off for exp(1)
            if xsb == 0:
                hi, lo, k = x - _LN2_HI, _LN2_LO, 1
            else:
                hi, lo, k = x + _LN2_HI, -_LN2_LO, -1
        else:
            k = int(_INVLN2 * x + (0.5 if xsb == 0 else -0.5))  # truncates toward zero, like C
            t = float(k)
            hi = x - t * _LN2_HI               # t*ln2_hi is exact here
            lo = t * _LN2_LO
        x = hi - lo
    elif hx < 0x3E300000:                      # |x| < 2**-28
        if _HUGE + x > 1.0:
            return 1.0 + x

    # x is now in the primary range
    t = x * x
    c = x - t * (_P1 + t * (_P2 + t * (_P3 + t * (_P4 + t * _P5))))
    if k == 0:
        return 1.0 - ((x * c) / (c - 2.0) - x)
    y = 1.0 - ((lo - (x * c) / (2.0 - c)) - hi)
    if k >= -1021:
        if k == 1024:
            return y * 2.0 * _TWO1023
        return y * _from_words(0x3FF00000 + (k << 20), 0)
    return y * _from_words(0x3FF00000 + ((k + 1000) << 20), 0) * _TWOM1000
