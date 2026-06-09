import numpy as np
from imperial_generals.config import get_config

def get_closest_morale_stat(morale: float) -> int:
    """
    Find the closest morale stat (1-10 scale) to a given morale value.

    Args:
        morale (float): The current morale value (raw scale, e.g. 0-100).

    Returns:
        int: The closest morale stat on the 1-10 stat scale.

    Notes:
        Rounds to the nearest morale level to avoid harsh penalties for small
        morale losses. Bounds and scale factor are read from config.
    """
    if not isinstance(morale, (int, float, np.integer, np.floating)):
        raise TypeError(f"morale must be a number (int, float, or numpy numeric), got {type(morale).__name__}")

    morale_cfg = get_config()['morale']
    min_raw = morale_cfg['min_raw']
    max_raw = morale_cfg['max_raw']
    scale   = morale_cfg['raw_scale_factor']

    if morale < 0 or morale > max_raw:
        raise ValueError(f"morale must be in the range 0 to {max_raw}, got {morale}")

    morale_options = np.arange(min_raw, max_raw + 1, scale)
    morale_diffs = np.abs(morale_options - morale)
    closest_morale = morale_options[np.argmin(morale_diffs)]
    return int(closest_morale // scale)

if __name__ == "__main__":  # pragma: no cover
    test_morales = [95, 87, 76, 64, 53, 42, 31, 20, 9, 0]
    for m in test_morales:
        print(f"Morale: {m} -> Closest Morale Stat: {get_closest_morale_stat(m)}")
