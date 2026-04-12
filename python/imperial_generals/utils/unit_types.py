import yaml
from pathlib import Path

_CONFIG_PATH = Path(__file__).parents[3] / 'config' / 'unit_subtypes.yaml'

def _load_unit_subtypes() -> dict[str, frozenset[str]]:
    with open(_CONFIG_PATH) as f:
        raw = yaml.safe_load(f)
    return {unit_type: frozenset(subtypes) for unit_type, subtypes in raw.items()}

UNIT_SUBTYPES: dict[str, frozenset[str]] = _load_unit_subtypes()
