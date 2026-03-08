from .loader import ConfigLoader
from typing import Optional

_instance: Optional[ConfigLoader] = None


def get_config() -> ConfigLoader:
    """
    Return the global ConfigLoader singleton.

    Loads simulation.yaml on first call and caches it for the process lifetime.
    """
    global _instance
    if _instance is None:
        _instance = ConfigLoader()
    return _instance


__all__ = ['ConfigLoader', 'get_config']
