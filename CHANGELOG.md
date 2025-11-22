# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),  
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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