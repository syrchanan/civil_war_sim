"""Parity fixtures (roadmap B2): JSON the TypeScript port must reproduce exactly."""
import json
import os

import pytest

from imperial_generals import parity

PARITY_DIR = os.path.join(os.path.dirname(__file__), '../../test_cases/parity')


@pytest.mark.parametrize("name", sorted(parity.FIXTURES))
def test_committed_fixture_is_up_to_date(name):
    # regenerate with: python -m imperial_generals.parity
    with open(os.path.join(PARITY_DIR, f'{name}.json'), encoding='utf-8') as f:
        assert json.load(f) == parity.build(name)


def test_rng_fixture_covers_seeds_draws_and_state():
    data = parity.build('rng')
    case = data['cases'][0]
    assert set(case) == {'seed', 'state', 'u32', 'random', 'exponential', 'state_after'}
    assert case['exponential']['rate'] > 0 and len(case['exponential']['values']) > 0
    assert any(c['seed'] == 0 for c in data['cases']) and any(c['seed'] == 2**32 - 1 for c in data['cases'])


def test_write_all_writes_every_fixture(tmp_path):
    parity.write_all(tmp_path)
    assert sorted(p.stem for p in tmp_path.iterdir()) == sorted(parity.FIXTURES)


def test_unknown_fixture_raises():
    with pytest.raises(KeyError):
        parity.build('nope')
