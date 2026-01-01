# Notes

## TODO

[ ] finish converting all R files to Python
[ ] write tests for all converted code
[ ] create TypeScript port of Python code
[ ] write tests for TypeScript code using same golden files as Python tests

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

# From Keep

## BRIGADE LEVEL
- Brigade level linked lists, so each step, a target is assigned per brigade and those calcs are run
- if they fire at each other, can use sq law for each
- if only one fires, then can use 0 coef for the other

## RETREAT
- based on losses and morale/XP
- come up with algo to combine them
- or more specifically a rate conversion of losses -> morale drop
- eventually make it more complex with morale boosts from a retreating enemy, or morale drop from retreating neighbors

## EFFICIENCY
- add in melee vs ranged switch based on distance to target
- add in range decay
- add in elevation

## UNIT MOVEMENT
- start with assuming static positions
- can always consider a battle turn to have 2 parts, move and shoot 

## OTHER
- bonus/malus for admin effect?
- each step would only be 1 turn, so calculations wouldn't ever be too insane
- once two groups get into melee, switch to linear law

## ALGO
- weather effects?