"""
ConfigLoader — loads simulation.yaml and provides typed access to all constants.

Usage:
    from imperial_generals.config import ConfigLoader

    config = ConfigLoader()                          # uses default path
    config = ConfigLoader('/path/to/simulation.yaml')  # explicit path

    config['combat']['xp_boost_per_level']           # subscript access
    config.get('combat', 'xp_boost_per_level')       # helper for one-level nesting
    'combat' in config                               # section existence check
"""

import yaml
from pathlib import Path
from typing import Any, Optional

# Default: config/simulation.yaml relative to the project root.
# loader.py lives at python/imperial_generals/config/loader.py,
# so four .parent calls reach the project root.
_DEFAULT_CONFIG_PATH = (
    Path(__file__).parent.parent.parent.parent / 'config' / 'simulation.yaml'
)


class ConfigLoader:
    """
    Loads and provides access to simulation.yaml.

    Parameters
    ----------
    path : str or Path, optional
        Path to the YAML config file. Defaults to config/simulation.yaml
        at the project root.

    Raises
    ------
    FileNotFoundError
        If the config file does not exist at the given path.
    """

    def __init__(self, path: Optional[Any] = None) -> None:
        resolved = Path(path) if path is not None else _DEFAULT_CONFIG_PATH
        if not resolved.exists():
            raise FileNotFoundError(f"Config file not found: {resolved}")
        with open(resolved, 'r') as f:
            self._data: dict = yaml.safe_load(f)

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
