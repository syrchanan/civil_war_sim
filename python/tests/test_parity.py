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


# =============================================================================
# Engine defaults for the TypeScript port (generated from config/*.yaml)
# =============================================================================

def test_committed_defaults_are_up_to_date():
    with open(parity.DEFAULTS_PATH, encoding='utf-8') as f:
        assert json.load(f) == parity.defaults()


def test_defaults_carry_params_and_the_tables_units_read():
    from imperial_generals.config import get_config
    from imperial_generals.params import BattleParams
    data = parity.defaults()
    assert data['params'] == BattleParams().to_dict()
    cfg = get_config()
    assert data['morale_scale'] == {k: cfg['morale'][k] for k in ('min_raw', 'max_raw', 'raw_scale_factor')}
    assert data['artillery'] == dict(cfg['artillery'])
    assert data['unit_subtypes'] == {'inf': ['irregulars', 'light', 'line', 'marine', 'pikes'],
                                     'cav': ['dragoons', 'heavy', 'light'],
                                     'art': ['battery', 'horse battery', 'siege battery']}


def test_write_all_writes_the_defaults(tmp_path):
    target = tmp_path / 'defaults.json'
    parity.write_all(tmp_path / 'fixtures', defaults_path=target)
    assert json.loads(target.read_text(encoding='utf-8')) == parity.defaults()


@pytest.mark.parametrize("overrides", parity.INVALID_OVERRIDES)
def test_invalid_overrides_in_the_params_fixture_are_rejected(overrides):
    from imperial_generals.params import BattleParams
    with pytest.raises(ValueError):
        BattleParams().with_overrides(overrides)


@pytest.mark.parametrize("stats", parity.STATS_INVALID)
def test_invalid_stats_in_the_units_fixture_are_rejected(stats):
    from imperial_generals.units import Regiment
    with pytest.raises(ValueError):
        Regiment(10, stats)
