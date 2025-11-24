# Notes

## TODO

[ ] finish converting all R files to Python

## Ideas

### Map

- Poisson-disc sampling for placing points
- Create voronoi diagram from points
- Voronoi cells are map cells for unit movement
- Create different terrain types for maps
- Use noise functions to generate elevation
- Rivers flowing from high elevation to low elevation
- Roads and paths
- Each terrain type has different movement costs

### Combat

- Implement range system for attacks
    - Out of range is less effective, closer is more effective to a certain point
    - Once elevation is added, effective range is affected by elevation differences
        - sin(height difference / flat distance) = effective distance
        - need to give downhill advantage, uphill disadvantage