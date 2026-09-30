import math
from functools import lru_cache

import numpy as np
from imperial_generals.config import get_config


@lru_cache(maxsize=1)
def _levels() -> tuple:
    """(min_raw, max_raw, scale, last_index), read once: config never changes at runtime."""
    morale_cfg = get_config()['morale']
    min_raw, max_raw, scale = morale_cfg['min_raw'], morale_cfg['max_raw'], morale_cfg['raw_scale_factor']
    return min_raw, max_raw, scale, (max_raw - min_raw) // scale


def get_closest_morale_stat(morale: float) -> int:
    """
    Find the closest morale stat (1-10 scale) to a given morale value.

    Args:
        morale (float): The current morale value (raw scale, e.g. 0-100).

    Returns:
        int: The closest morale stat on the 1-10 stat scale.

    Notes:
        Rounds to the nearest morale level (min_raw, min_raw + scale, ..., max_raw) to avoid harsh penalties
        for small morale losses; exact ties go to the lower level. Computed arithmetically rather than by
        scanning the levels, since it runs on every casualty. Bounds and scale factor are read from config.
    """
    if not isinstance(morale, (int, float, np.integer, np.floating)):
        raise TypeError(f"morale must be a number (int, float, or numpy numeric), got {type(morale).__name__}")

    min_raw, max_raw, scale, last_index = _levels()

    if morale < 0 or morale > max_raw:
        raise ValueError(f"morale must be in the range 0 to {max_raw}, got {morale}")

    # index of the nearest level; ceil(x - 0.5) sends exact halves down, like the old first-minimum scan
    index = max(0, min(last_index, math.ceil((morale - min_raw) / scale - 0.5)))
    return int((min_raw + index * scale) // scale)

if __name__ == "__main__":  # pragma: no cover
    test_morales = [95, 87, 76, 64, 53, 42, 31, 20, 9, 0]
    for m in test_morales:
        print(f"Morale: {m} -> Closest Morale Stat: {get_closest_morale_stat(m)}")
