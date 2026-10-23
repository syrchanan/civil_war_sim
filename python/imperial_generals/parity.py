"""
Parity fixtures for the TypeScript port (roadmap B2).

Each fixture is JSON the port must reproduce exactly: inputs plus the Python engine's outputs. They are committed
under ``test_cases/parity/`` and a test fails if one is out of date, so regenerate after changing the engine:

    python -m imperial_generals.parity

``fdlibm.json`` in the same folder is not generated: it holds V8's ``Math.log`` / ``Math.exp`` results, the
reference both languages are checked against.

The same command writes ``web/src/engine/defaults.json``, the engine defaults the port runs on: ``config/*.yaml``
stays the one source.
"""

import json
from pathlib import Path

from imperial_generals.config import get_config
from imperial_generals.params import BattleParams
from imperial_generals.utils import Rng
from imperial_generals.utils.unit_types import UNIT_SUBTYPES

ROOT = Path(__file__).resolve().parents[2]
PARITY_DIR = ROOT / 'test_cases' / 'parity'
DEFAULTS_PATH = ROOT / 'web' / 'src' / 'engine' / 'defaults.json'

DRAWS = 8


def _rng_case(seed: int, rate: float) -> dict:
    """One generator, drawn in order: u32s, then uniforms, then exponentials, then its state."""
    rng = Rng(seed)
    state = rng.state
    u32 = [rng.next_u32() for _ in range(DRAWS)]
    uniform = [rng.random() for _ in range(DRAWS)]
    exponential = [rng.exponential(rate) for _ in range(DRAWS)]
    return {'seed': seed, 'state': state, 'u32': u32, 'random': uniform,
            'exponential': {'rate': rate, 'values': exponential}, 'state_after': rng.state}


def rng_fixture() -> dict:
    cases = [(0, 1.0), (1, 0.37), (42, 12.5), (123456789, 0.004), (2**32 - 1, 250.0)]
    return {'description': 'Rng(seed): state, then in order next_u32 x8, random x8, exponential(rate) x8, '
                           'and the state after.',
            'cases': [_rng_case(seed, rate) for seed, rate in cases]}


FIXTURES = {
    'rng': rng_fixture,
}


def defaults() -> dict:
    """Everything the engine reads from config: battle params, the morale scale, unit subtypes, the battery template."""
    cfg = get_config()
    return {
        'description': 'Engine defaults from config/*.yaml. Generated: python -m imperial_generals.parity',
        'params': BattleParams().to_dict(),
        'morale_scale': {k: cfg['morale'][k] for k in ('min_raw', 'max_raw', 'raw_scale_factor')},
        'unit_subtypes': {unit_type: sorted(subtypes) for unit_type, subtypes in UNIT_SUBTYPES.items()},
        'artillery': dict(cfg['artillery']),
    }


def build(name: str) -> dict:
    """The fixture ``name`` as the Python engine computes it now."""
    return FIXTURES[name]()


def _write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8', newline='\n')


def write_all(directory: Path = PARITY_DIR, defaults_path: Path = DEFAULTS_PATH) -> None:
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    for name in FIXTURES:
        _write_json(directory / f'{name}.json', build(name))
    _write_json(Path(defaults_path), defaults())


if __name__ == '__main__':  # pragma: no cover
    write_all()
