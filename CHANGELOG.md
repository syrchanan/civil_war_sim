# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),  
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.3] - 2025-12-31

### Added
- **TypeScript `package.json` improvements**: Package is now named `imperial_generals`, with type and main exports. Description and keywords reflect wargame simulation and mapgen utility.
- **Golden test case system for combat efficiency**: Shared `test_cases/combat_efficiency.json` enables both Python (`pytest`) and TypeScript tests. See refactored `python/tests/test_utils_combat_efficiency.py`.
- **TypeScript port of Regiment unit class**: Added `src/imperial_generals/units/Regiment.ts`, along with `getCombatEfficiency` and `getClosestMoraleStat` utilities, ready for browser/React UI integration.
- **Jest test runner for TypeScript**: `/typescript/tests/imperial_generals/Regiment.test.ts` validates against golden files in `/test_cases/regiment_examples.json`.
- **Empty `__init__.py` files**: Added to `python/` and `python/imperial_generals/` for package recognition.

### Changed
- Expanded test coverage in TypeScript using shared golden files for cross-language parity checks.
- Updated `src/index.ts` in TypeScript to align with new packaging.

## [0.1.2] - 2025-12-31

### Added
- **Monorepo structure**: Created top-level directories `/python`, `/typescript`, and `/test_cases` for clearer separation of implementation and tests.
- **TypeScript port scaffold**: Initialized `/typescript/` with `package.json`, `/src`, and `/tests` folders, and created starter `index.ts`.
- **Golden test case system**: Added `/test_cases/` folder to collect shared language-neutral JSON files for inputs and outputs to be used by both Python and TypeScript tests.
- **Monorepo plan documentation**: Added `monorepo_plan.md` to describe project strategy and workflow for porting and testing.

### Changed
- Moved all existing Python code, modules, and test files from root and subfolders into `/python`.
- Updated `README.md` to reflect monorepo design, the location of code, how to contribute, and the golden file testing strategy.

### Fixed
- Ensured existing Python test files are located in `/python/tests` for easier test management after migration.

### Notes
- No code functionality was changed in simulation or core logic at this step, but all paths and organization have been updated for future scalability.
- Legacy and planning documentation is now included near the bottom of the README, following the new repo introduction.

## [0.1.1] - 2025-11-25

### Added
- New modules for map generation:
  - **`imperial_generals.map`**: `MapConfig.py`, `PoissonDiscSampler.py`, `VoronoiMap.py`, `MapGenerator.py`
- New test files:
  - `tests/test_battles_simulation.py`
  - `tests/test_map_map_config.py`
  - `tests/test_map_poisson_disc.py`
  - `tests/test_map_voronoi_map.py`
  - `tests/test_units_army.py`
  - `tests/test_units_infantry_regiment.py`
  - `tests/test_units_regiment.py`
  - `tests/test_utils_closest_morale_stat.py`
  - `tests/test_utils_combat_efficiency.py`
- New code owners file: `CODEOWNERS`

### Changed
- Updated `main.py` to use new map generation components
- Improved validation in `Simulation.py` for input types
- Expanded and improved tests in `test_regiment.py`
- Updated `README.md` to reflect Python as the main implementation language
- Expanded notes in `notes.md` for map and combat ideas
- Logging added to map generation and Voronoi modules

### Removed
- Deleted deprecated R scripts and old Python files from `archive/functions` and `archive/mapgen`
- Removed old test files: `tests/test_army.py`, `tests/test_combat_efficiency.py`, `tests/test_regiment.py`

## [0.1.0] - 2025-11-22

### Added
- New Python modules for core simulation:
  - **`imperial_generals.units`**: `Army.py`, `InfantryRegiment.py`, `Regiment.py`
  - **`imperial_generals.battles`**: `Simulation.py`
  - **`imperial_generals.utils`**: `closest_morale_stat.py`, `combat_efficiency.py`
- Main entry point: `main.py`
- Test suite: `tests/test_army.py`, `tests/test_combat_efficiency.py`, `tests/test_regiment.py`
- Documentation: `notes.md`, `simulation.log`
- Archive folder containing previous R scripts, notes, and map generation code

### Changed
- Updated `README.md` with new project title and documentation for map generation features
- Updated `.gitignore` to include `.vscode` folder

### Removed
- Deprecated R scripts and renv files from root and `functions/`, moved to `archive/`
- Old notes and renv configuration files from root and `notes/`, moved to `archive/`
- `.Rprofile` and `renv.lock` from root
