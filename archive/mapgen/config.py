class Config:
    """
    Holds configuration for map generation.
    """
    def __init__(self, width, height, min_distance):
        self.width = width
        self.height = height
        self.min_distance = min_distance