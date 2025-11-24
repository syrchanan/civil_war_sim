class MapConfig:
    """
    Holds configuration for map generation.
    """
    def __init__(self, width, height, min_distance):
        if not isinstance(width, int):
            raise TypeError("width must be an int")
        if not isinstance(height, int):
            raise TypeError("height must be an int")
        if not isinstance(min_distance, int):
            raise TypeError("min_distance must be an int")
        self.width = width
        self.height = height
        self.min_distance = min_distance