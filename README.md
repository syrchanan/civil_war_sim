# Lanchester Modeling for Imperial Generals

Imperial Generals is a strategic war game where players command armies and engage in battles. This repository contains an implementation of the Lanchester equations to model combat scenarios within the game.

Currently, the implementation is in R, though there are plans to port it to Julia in the future to leverage its performance advantages for numerical computations. Additionally, a Julia-implementation would allow the functions to be compiled into a shared library for use in both R and Python.

## Overview

The Lanchester equations are a set of differential equations that describe the dynamics of two opposing forces in combat. They help predict the outcome of battles based on the number of units and their effectiveness. This implementation allows players to simulate battles between different types of units, taking into account their strengths and weaknesses.

## Features

-   **Lanchester Equations**: Implements both Lanchester's Linear and Square Laws to model combat scenarios.
-   **Unit Types**: Leverages the Imperial Generals statistics for various unit types to determine combat effectiveness.
-   **Simulation**: Allows users to simulate battles between two forces with multiple phases (ambush, frontal confrontation).

## Effectiveness Coefficients

The Lanchester equations require effectiveness coefficients for each unit type to determine how effectively they can inflict casualties on the opposing force.

Typically, coefficients are derived from historical data or expert judgment. In this implementation, coefficients are calculated based on the unit's attributes such as experience, morale, weapon quality, and whether they are melee or ranged units (more on that below).

The coefficients typically fall within the range of 0 to 1.000 or more. In practice, the coefficients indicate:

-   **Higher Coefficient**: Indicates a more effective unit type that can inflict more casualties on the opposing force.
-   **Lower Coefficient**: Indicates a less effective unit type that inflicts fewer casualties.

In this implementation, a coefficient N means that for each 1 soldier of that type, they can kill N soldiers of the opposing force per time unit. For example, when N = 1, it means that 1 soldier can kill 1 soldier of the opposing force per time unit; however, when N = 1/100, it means that it takes 100 soldiers to kill 1 soldier of the opposing force per time unit.

## Unit Stat Blocks

Each unit type has a stat block that includes the following attributes:

-   **XP**: Experience level of the unit from training or prior combat \[1, 10\]

-   **Morale**: The morale level of the unit, affecting its performance in battle \[1, 10\]

-   **Weapon**: The stat of the unit's weapon from unarmed to futuristic \[-2, 2\]

-   **Melee**: Boolean indicating if the unit is a melee unit \[0, 1\]

For example, a unit stat block might look like this: `10/10/2/0`

Based on these attributes, the unit's combat effectiveness is calculated, and a coefficient is derived for use in the Lanchester equations. In this case, the coefficient would be `1.000`, as this is the maximum possible value.\*

\*Since Imperial Generals is generally set in the Napoleonic/American Civil War era, a coefficient of 1.000 represents the best possible unit in this context, since the best a single soldier can do is kill/wound one enemy soldier each round.

## Future Plans

-   **Dynamic Morale**: Incorporate morale effects into the Lanchester equations to reflect changing battle conditions and early breaking of forces.
-   **Enhanced Unit Interactions**: Incorporate more complex interactions between different unit types.
-   **Graphical Interface**: Develop a user-friendly interface for setting up and visualizing battles.