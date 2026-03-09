"""
ConfigLoader — loads simulation config from a directory of YAML files (or a single file)
and provides typed access to all constants.

Usage:
    from imperial_generals.config import ConfigLoader

    config = ConfigLoader()                        # uses default config/ directory
    config = ConfigLoader('/path/to/config/')      # explicit directory
    config = ConfigLoader('/path/to/combat.yaml')  # single file

    config['combat']['xp_boost_per_level']         # subscript access
    config.get('combat', 'xp_boost_per_level')     # helper for one-level nesting
    'combat' in config                             # section existence check
"""

import yaml
from pathlib import Path
from typing import Any, Optional

# Default: config/ directory relative to the project root.
# loader.py lives at python/imperial_generals/config/loader.py,
# so four .parent calls reach the project root.
_DEFAULT_CONFIG_PATH = (
    Path(__file__).parent.parent.parent.parent / 'config'
)


class ConfigLoader:
    """
    Loads and provides access to simulation config YAML files.

    If the path is a directory, all .yaml files in it are loaded and merged
    alphabetically into one dict. If the path is a file, it is loaded directly.

    Parameters
    ----------
    path : str or Path, optional
        Path to a YAML config file or directory. Defaults to config/ directory
        at the project root.

    Raises
    ------
    FileNotFoundError
        If the path does not exist.
    """

    def __init__(self, path: Optional[Any] = None) -> None:
        resolved = Path(path) if path is not None else _DEFAULT_CONFIG_PATH
        if not resolved.exists():
            raise FileNotFoundError(f"Config path not found: {resolved}")
        if resolved.is_dir():
            self._data = self._load_directory(resolved)
        else:
            with open(resolved, 'r') as f:
                self._data: dict = yaml.safe_load(f) or {}

    @staticmethod
    def _load_directory(directory: Path) -> dict:
        """Load and merge all .yaml files in a directory (sorted alphabetically)."""
        merged: dict = {}
        for yaml_file in sorted(directory.glob('*.yaml')):
            with open(yaml_file, 'r') as f:
                data = yaml.safe_load(f) or {}
            merged.update(data)
        return merged

    def __getitem__(self, section: str) -> Any:
        """Return a top-level config section by name."""
        if section not in self._data:
            raise KeyError(f"Config section '{section}' not found.")
        return self._data[section]

    def __contains__(self, section: str) -> bool:
        """Support `'section' in config` checks."""
        return section in self._data

    def get(self, section: str, key: str) -> Any:
        """
        Return a single value from a top-level section.

        Parameters
        ----------
        section : str
            Top-level section name (e.g. 'combat').
        key : str
            Key within that section (e.g. 'xp_boost_per_level').

        Raises
        ------
        KeyError
            If the section or key does not exist.
        """
        return self[section][key]

    def __repr__(self) -> str:
        sections = list(self._data.keys())
        return f"ConfigLoader(sections={sections})"
