"""
Parity fixtures for the TypeScript port (roadmap B2).

Each fixture is JSON the port must reproduce exactly: inputs plus the Python engine's outputs. They are committed
under ``test_cases/parity/`` and a test fails if one is out of date, so regenerate after changing the engine:

    python -m imperial_generals.parity

``fdlibm.json`` in the same folder is not generated: it holds V8's ``Math.log`` / ``Math.exp`` results, the
reference both languages are checked against.
"""

import json
from pathlib import Path

from imperial_generals.utils import Rng

PARITY_DIR = Path(__file__).resolve().parents[2] / 'test_cases' / 'parity'

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


def build(name: str) -> dict:
    """The fixture ``name`` as the Python engine computes it now."""
    return FIXTURES[name]()


def write_all(directory: Path = PARITY_DIR) -> None:
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    for name in FIXTURES:
        text = json.dumps(build(name), indent=2) + '\n'
        (directory / f'{name}.json').write_text(text, encoding='utf-8', newline='\n')


if __name__ == '__main__':  # pragma: no cover
    write_all()
