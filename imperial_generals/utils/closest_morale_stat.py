import numpy as np

def get_closest_morale_stat(morale: float) -> int:
    """
    Find the closest morale stat (1-10 scale) to a given morale value.

    Args:
        morale (float): The current morale value (0-100 scale).

    Returns:
        int: The closest morale stat on a 1-10 scale.

    Notes:
        The function finds the nearest multiple of 10 to the input morale value, then converts it to a 1-10 scale by dividing by 10.
        Avoids harsh penalties for small morale losses by rounding to the nearest level.
    """
    if not isinstance(morale, (int, float, np.integer, np.floating)):
        raise TypeError(f"morale must be a number (int, float, or numpy numeric), got {type(morale).__name__}")
    if morale < 0 or morale > 100:
        raise ValueError(f"morale must be in the range 0 to 100, got {morale}")

    morale_options = np.arange(10, 101, 10)
    morale_diffs = np.abs(morale_options - morale)
    closest_morale = morale_options[np.argmin(morale_diffs)]
    return int(closest_morale // 10)

if __name__ == "__main__":
    test_morales = [95, 87, 76, 64, 53, 42, 31, 20, 9, 0]
    for morale in test_morales:
        closest_stat = get_closest_morale_stat(morale)
        print(f"Morale: {morale} -> Closest Morale Stat: {closest_stat}")