/**
 * Pure-arithmetic ports of fdlibm `log` and `exp` (port of python/imperial_generals/utils/fdlibm.py).
 *
 * V8's Math.log / Math.exp are fdlibm too, but the engine uses these ports on both sides so that results never
 * depend on a platform's libm: only IEEE-754 +, -, *, / and bit manipulation.
 *
 * Sources: fdlibm 5.3 e_log.c / e_exp.c (Sun Microsystems, freely redistributable), with exp following V8's
 * ieee754::exp variant (power-of-two scaling by multiplication).
 */

const LN2_HI = 6.93147180369123816490e-01; // 3fe62e42 fee00000
const LN2_LO = 1.90821492927058770002e-10; // 3dea39ef 35793c76
const TWO54 = 1.80143985094819840000e+16; // 43500000 00000000
const LG1 = 6.666666666666735130e-01; // 3FE55555 55555593
const LG2 = 3.999999999940941908e-01; // 3FD99999 9997FA04
const LG3 = 2.857142874366239149e-01; // 3FD24924 94229359
const LG4 = 2.222219843214978396e-01; // 3FCC71C5 1D8E78AF
const LG5 = 1.818357216161805012e-01; // 3FC74664 96CB03DE
const LG6 = 1.531383769920937332e-01; // 3FC39A09 D078C69F
const LG7 = 1.479819860511658591e-01; // 3FC2F112 DF3E5244

const HUGE = 1.0e+300;
const TWOM1000 = 9.33263618503218878990e-302; // 2**-1000
const TWO1023 = 8.988465674311579539e+307; // 2**1023
const O_THRESHOLD = 7.09782712893383973096e+02; // 0x40862E42 FEFA39EF
const U_THRESHOLD = -7.45133219101941108420e+02; // 0xc0874910 D52D3051
const INVLN2 = 1.44269504088896338700e+00; // 0x3ff71547 652b82fe
const P1 = 1.66666666666666019037e-01; // 0x3FC55555 5555553E
const P2 = -2.77777777770155933842e-03; // 0xBF66C16C 16BEBD93
const P3 = 6.61375632143793436117e-05; // 0x3F11566A AF25DE2C
const P4 = -1.65339022054652515390e-06; // 0xBEBBBD41 C5D26BF1
const P5 = 4.13813679705723846039e-08; // 0x3E663769 72BEA4D0

const view = new DataView(new ArrayBuffer(8));

/** [signed high word, unsigned low word] of a double. */
function words(x: number): [number, number] {
  view.setFloat64(0, x);
  return [view.getInt32(0), view.getUint32(4)];
}

function fromWords(hi: number, lo: number): number {
  view.setInt32(0, hi);
  view.setUint32(4, lo);
  return view.getFloat64(0);
}

/** Natural logarithm, bit-identical to fdlibm __ieee754_log (and V8 Math.log). */
export function log(x: number): number {
  let [hx, lx] = words(x);
  let k = 0;
  if (hx < 0x00100000) { // x < 2**-1022
    if (((hx & 0x7fffffff) | lx) === 0) return -Infinity; // log(+-0) = -inf
    if (hx < 0) return NaN; // log(-#) = NaN
    k -= 54;
    x *= TWO54; // subnormal: scale up
    [hx, lx] = words(x);
  }
  if (hx >= 0x7ff00000) return x + x; // inf or NaN
  k += (hx >> 20) - 1023;
  hx &= 0x000fffff;
  let i = (hx + 0x95f64) & 0x100000;
  x = fromWords(hx | (i ^ 0x3ff00000), lx); // normalize x or x/2
  k += i >> 20;
  const f = x - 1.0;
  if ((0x000fffff & (2 + hx)) < 3) { // |f| < 2**-20
    if (f === 0.0) {
      if (k === 0) return 0.0;
      return k * LN2_HI + k * LN2_LO;
    }
    const R = f * f * (0.5 - 0.33333333333333333 * f);
    if (k === 0) return f - R;
    return k * LN2_HI - ((R - k * LN2_LO) - f);
  }
  const s = f / (2.0 + f);
  const dk = k;
  const z = s * s;
  i = hx - 0x6147a;
  const w = z * z;
  const j = 0x6b851 - hx;
  const t1 = w * (LG2 + w * (LG4 + w * LG6));
  const t2 = z * (LG1 + w * (LG3 + w * (LG5 + w * LG7)));
  i |= j;
  const R = t2 + t1;
  if (i > 0) {
    const hfsq = 0.5 * f * f;
    if (k === 0) return f - (hfsq - s * (hfsq + R));
    return dk * LN2_HI - ((hfsq - (s * (hfsq + R) + dk * LN2_LO)) - f);
  }
  if (k === 0) return f - s * (f - R);
  return dk * LN2_HI - ((s * (f - R) - dk * LN2_LO) - f);
}

/** Exponential, bit-identical to V8 Math.exp (fdlibm __ieee754_exp). */
export function exp(x: number): number {
  let [hx, lx] = words(x);
  const xsb = hx < 0 ? 1 : 0; // sign bit
  hx &= 0x7fffffff; // high word of |x|

  if (hx >= 0x40862e42) { // |x| >= 709.78...
    if (hx >= 0x7ff00000) {
      if (((hx & 0xfffff) | lx) !== 0) return x + x; // NaN
      return xsb === 0 ? x : 0.0; // exp(+-inf) = {inf, 0}
    }
    if (x > O_THRESHOLD) return Infinity; // overflow
    if (x < U_THRESHOLD) return 0.0; // underflow
  }

  let k = 0;
  let hi = 0.0;
  let lo = 0.0;
  if (hx > 0x3fd62e42) { // |x| > 0.5 ln2: argument reduction
    if (hx < 0x3ff0a2b2) { // and |x| < 1.5 ln2
      if (x === 1.0) return 2.718281828459045; // V8 special case: fdlibm is 1 ulp off for exp(1)
      if (xsb === 0) {
        hi = x - LN2_HI;
        lo = LN2_LO;
        k = 1;
      } else {
        hi = x + LN2_HI;
        lo = -LN2_LO;
        k = -1;
      }
    } else {
      k = Math.trunc(INVLN2 * x + (xsb === 0 ? 0.5 : -0.5)); // truncates toward zero, like C
      hi = x - k * LN2_HI; // k*ln2_hi is exact here
      lo = k * LN2_LO;
    }
    x = hi - lo;
  } else if (hx < 0x3e300000) { // |x| < 2**-28
    // always true: in C it raises the inexact flag
    /* v8 ignore next */
    if (HUGE + x > 1.0) return 1.0 + x;
  }

  // x is now in the primary range
  const t = x * x;
  const c = x - t * (P1 + t * (P2 + t * (P3 + t * (P4 + t * P5))));
  if (k === 0) return 1.0 - ((x * c) / (c - 2.0) - x);
  const y = 1.0 - ((lo - (x * c) / (2.0 - c)) - hi);
  if (k >= -1021) {
    if (k === 1024) return y * 2.0 * TWO1023;
    return y * fromWords(0x3ff00000 + (k << 20), 0);
  }
  return y * fromWords(0x3ff00000 + ((k + 1000) << 20), 0) * TWOM1000;
}
