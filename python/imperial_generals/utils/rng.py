"""
Portable seeded random number generator.

Specified exactly so the TypeScript port can reproduce every draw bit-for-bit:

- Seeding: a 32-bit seed is expanded to four state words with splitmix32.
- Core: xoshiro128** (32-bit operations only; JS needs just ``Math.imul`` and ``>>> 0``).
- ``random()``: 53-bit float in [0, 1) built from two 32-bit draws.
- ``exponential(rate)``: inverse CDF, ``-log(1 - u) / rate``, using the fdlibm ``log`` port
  (platform libm can differ from V8 in the last bit; the port is bit-identical to ``Math.log``).
"""

import math

from .fdlibm import log

_MASK = 0xFFFFFFFF


def _rotl(x: int, k: int) -> int:
    return ((x << k) | (x >> (32 - k))) & _MASK


def _is_u32(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= _MASK


def _splitmix32(seed: int):
    a = seed
    while True:
        a = (a + 0x9E3779B9) & _MASK
        t = a ^ (a >> 16)
        t = (t * 0x21F0AAAD) & _MASK
        t ^= t >> 15
        t = (t * 0x735A2D97) & _MASK
        t ^= t >> 15
        yield t


class Rng:
    """
    Seeded xoshiro128** generator shared by the Python engine and the TypeScript port.

    Parameters
    ----------
    seed : int
        Integer in [0, 2**32).

    Raises
    ------
    TypeError
        If seed is not an int.
    ValueError
        If seed is outside [0, 2**32).
    """

    def __init__(self, seed: int) -> None:
        if not isinstance(seed, int) or isinstance(seed, bool):
            raise TypeError(f"seed must be an int, got {type(seed).__name__}.")
        if not _is_u32(seed):
            raise ValueError(f"seed must be in [0, 2**32), got {seed}.")
        words = _splitmix32(seed)
        self._s: list[int] = [next(words) for _ in range(4)]
        self.seed: int | None = seed      # informational; the state words are what matter

    @classmethod
    def from_state(cls, state: list[int]) -> 'Rng':
        """
        Restore a generator from a saved ``state`` (four 32-bit unsigned ints, not all zero).

        Raises
        ------
        ValueError
            If state is not four 32-bit unsigned ints, or is all zero.
        """
        if len(state) != 4 or not all(_is_u32(v) for v in state) or not any(state):
            raise ValueError(f"state must be four 32-bit unsigned ints, not all zero, got {state}.")
        rng = cls.__new__(cls)
        rng._s = list(state)
        rng.seed = None
        return rng

    @property
    def state(self) -> list[int]:
        """Copy of the four internal state words (for serialization)."""
        return list(self._s)

    def next_u32(self) -> int:
        """Next 32-bit unsigned integer."""
        s = self._s
        result = (_rotl((s[1] * 5) & _MASK, 7) * 9) & _MASK
        t = (s[1] << 9) & _MASK
        s[2] ^= s[0]
        s[3] ^= s[1]
        s[1] ^= s[2]
        s[0] ^= s[3]
        s[2] ^= t
        s[3] = _rotl(s[3], 11)
        return result

    def random(self) -> float:
        """Uniform float in [0, 1) with 53 bits of precision."""
        hi = self.next_u32() >> 5
        lo = self.next_u32() >> 6
        return (hi * 67108864 + lo) / 9007199254740992

    def exponential(self, rate: float) -> float:
        """
        Exponentially distributed sample with the given rate (mean ``1 / rate``).

        Raises
        ------
        ValueError
            If rate is not a finite positive number.
        """
        if not (math.isfinite(rate) and rate > 0):
            raise ValueError(f"rate must be finite and > 0, got {rate}.")
        return -log(1.0 - self.random()) / rate
