# main.py
- entrypoint to the map generation module

# config
- configuration class 
    - generation parameters (width, height, point density)
    - map feature parameters (TODO)

# map_generator.py
- main map generation logic combining Poisson Disc Sampling and Voronoi diagram

# poisson_disc.py
- implementation of Poisson Disc Sampling algorithm for point distribution
- creates `PoissonDiscSampler` class for voronoi diagram generation

# voronoi.py
- implementation of Voronoi diagram generation using points from Poisson Disc Sampling
- creates `VoronoiMap` class for map region creation

# TODO
- implement additional map features
    - elevation
    - rivers
    - mountains
    - roads
    - sea