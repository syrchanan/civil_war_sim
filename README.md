# Imperial Generals: Lanchester Combat Simulation

Imperial Generals is a strategic war game where players command armies and engage in battles. This repository contains an implementation of the Lanchester equations to model combat scenarios within the game.

The prototype was in R, but the current implementation is in Python. I'm currently considering porting it to Julia if I find I need the speedup from compiling.

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

-   **XP**: Experience level of the unit from training or prior combat [1, 10]

-   **Morale**: The morale level of the unit, affecting its performance in battle [1, 10]

-   **Weapon**: The stat of the unit's weapon from unarmed to futuristic [-2, 2]

-   **Melee**: Boolean indicating if the unit is a melee unit [0, 1]

For example, a unit stat block might look like this: `10/10/20`

Based on these attributes, the unit's combat effectiveness is calculated, and a coefficient is derived for use in the Lanchester equations. In this case, the coefficient would be `1.000`, as this is the maximum possible value.*

*Since Imperial Generals is generally set in the Napoleonic/American Civil War era, a coefficient of 1.000 represents the best possible unit in this context, since the best a single soldier can do is kill/wound one enemy soldier each round.

## Future Plans

-   **Dynamic Morale**: Incorporate morale effects into the Lanchester equations to reflect changing battle conditions and early breaking of forces.
-   **Enhanced Unit Interactions**: Incorporate more complex interactions between different unit types.
-   **Graphical Interface**: Develop a user-friendly interface for setting up and visualizing battles.

---

# Importing TypeScript Library in JS Projects

To use the TypeScript logic in your own JavaScript project:

## Option 1: Install Directly from GitHub via npm

1. **Add the GitHub repo as a dependency:**
     - In your project's `package.json`, add:
         ```json
         "dependencies": {
             "civil_war_sim": "github:syrchanan/civil_war_sim"
         }
         ```
     - Or run:
         ```shell
         npm install github:syrchanan/civil_war_sim
         ```

2. **Install dependencies and build the library:**
     - After install, the repo will be in `node_modules/civil_war_sim`.
     - If the TypeScript code is not pre-built, build it:
         ```shell
         cd node_modules/civil_war_sim/typescript
         npm install
         npm run build
         ```

3. **Import in your JS project:**
     - Use the built files from the package:
         ```javascript
         // CommonJS
         const { ImperialGenerals } = require('civil_war_sim/typescript/dist');
         // ES Modules
         import { ImperialGenerals } from 'civil_war_sim/typescript/dist';
         ```
     - Adjust the import path and exported names as needed.

---

## Option 2: Manual Download and Build

1. **Clone the repository:**
     ```shell
     git clone https://github.com/syrchanan/civil_war_sim.git
     ```

2. **Install dependencies and build:**
     ```shell
     cd civil_war_sim/typescript
     npm install
     npm run build
     ```

3. **Import in your JS project:**
     - Reference the built files using a relative path:
         ```javascript
         // CommonJS
         const { ImperialGenerals } = require('./path/to/civil_war_sim/typescript/dist');
         // ES Modules
         import { ImperialGenerals } from './path/to/civil_war_sim/typescript/dist';
         ```
     - Adjust the import path and exported names as needed.
     - See `/typescript/README.md` for more advanced examples.

---

# Civil War Sim Tabletop Tools

This repository is a monorepo containing:
- A Python implementation of battle simulation and map generation logic
- A TypeScript port designed for browser-use and future web UIs
- Shared language-neutral golden test files for test consistency across both ports

_Last updated: 2025-12-31_

---

## Current Structure

```
/
├── python/             # Python simulation code and tests
│   ├── main.py
│   ├── imperial_generals/
│   ├── archive/        # Archived R scripts and old code (will be removed)
│   ├── tests/
│   └── ...
├── typescript/         # Typescript implementation and tests
│   ├── package.json
│   ├── src/
│   ├── tests/
│   └── ...
├── test_cases/         # Golden test cases as JSON (shared by both implementations)
│   └── ...
├── README.md
└── ...
```

---

## Cross-Language Development & Testing Workflow

This project uses a language-agnostic, test-driven workflow to ensure equivalent results and high reliability across Python and TypeScript implementations:

1. **Develop and prototype algorithms in Python**, leveraging the powerful Python ecosystem for rapid iteration and Jupyter-style experimentation.
2. **Capture all expected behavior in "golden" test cases** as JSON files in `/test_cases`. These goldens serve as the reference for correctness for both codebases.
. **Port functionality to TypeScript** (for browser/React/JS UI use) by translating the validated Python logic.
4. **Run automated TypeScript tests that consume the same golden files.** If TypeScript outputs match the golden results, correctness and parity with Python is assured.

**TLDR:** Code in Python, port to TypeScript, and verify both using shared, language-neutral golden tests!

## Python Implementation (`/python`)
- Contains core battle simulation logic
- Includes map generation and supporting tools
- Test suite under `/python/tests` that will consume golden test cases from `/test_cases`

## TypeScript Implementation (`/typescript`)
- Port of the Python logic for use in a frontend (React/JS web apps)
- Organized as an npm package with `/src` for code and `/tests` for the suite
- Strict separation of logic from UI for easy reuse
- Test suite will read and validate against `/test_cases` JSON vectors (matching Python)

## Golden Test Strategy (`/test_cases`)
- All official test cases live as JSON files here
- Both Python and TypeScript test runners use these

---

## Contributing/Development Workflow
1. Develop or prototype logic/features in `/python` first
2. For each stable simulation feature, add/update golden test files in `/test_cases`
3. Log a checkpoint and open an issue or note to port to `/typescript` when ready
4. Port logic or tests as needed in `/typescript` and ensure golden file consistency

### Tips
- Update paths/imports as necessary after moving files
- Run tests from each language's folder and update shared test cases when new behaviors are introduced
- If randomness exists, use fixed seeds for deterministic tests
