# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),  
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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