"""Finer battle outcomes: decisive / Pyrrhic / plain victory (and defeat) and draws, from losses and the field."""

import pytest

from imperial_generals import api
from imperial_generals.params import AftermathParams, BattleParams

P = AftermathParams()      # decisive: ratio 2, share 0.25; Pyrrhic: share 0.25, ratio 1


@pytest.mark.parametrize('holder, decided_by, casualties, started, verdicts', [
    (None, 'votes', [300, 100], [1000, 1000], ['draw', 'draw']),
    (0, 'admin', [100, 150], [1000, 1000], ['victory', 'defeat']),
    # the loser lost a quarter and at least twice the winner's casualties
    (0, 'votes', [100, 250], [1000, 1000], ['decisive victory', 'decisive defeat']),
    (1, 'votes', [500, 240], [2000, 1000], ['decisive defeat', 'decisive victory']),
    (0, 'votes', [100, 249], [1000, 1000], ['victory', 'defeat']),          # not a quarter
    (0, 'votes', [200, 399], [1000, 1000], ['victory', 'defeat']),          # not twice
    # the whole enemy army broken or wiped out
    (0, 'army_out', [100, 120], [1000, 1000], ['decisive victory', 'decisive defeat']),
    # the winner lost a quarter, and at least as many men as the loser
    (0, 'votes', [300, 300], [1000, 2000], ['Pyrrhic victory', 'defeat']),
    (1, 'army_out', [260, 400], [1000, 1000], ['defeat', 'Pyrrhic victory']),
    (0, 'votes', [299, 300], [1000, 2000], ['victory', 'defeat']),          # fewer than the loser
    (0, 'votes', [249, 200], [1000, 2000], ['victory', 'defeat']),
])
def test_verdicts(holder, decided_by, casualties, started, verdicts):
    assert api.verdicts(holder, decided_by, casualties, started, P) == verdicts


def test_verdict_thresholds_are_params():
    p = BattleParams().with_overrides({'aftermath': {'decisive_ratio': 1.2, 'pyrrhic_share': 0.5}}).aftermath
    assert api.verdicts(0, 'votes', [100, 250], [1000, 1000], p) == ['decisive victory', 'decisive defeat']
    assert api.verdicts(0, 'votes', [300, 300], [1000, 2000], p) == ['victory', 'defeat']
    assert api.verdicts(0, 'votes', [210, 250], [1000, 1000], p) == ['victory', 'defeat']


@pytest.mark.parametrize('change, message', [
    ({'decisive_ratio': 0.9}, 'decisive_ratio'), ({'decisive_share': 1.5}, 'decisive_share'),
    ({'pyrrhic_share': -0.1}, 'pyrrhic_share'), ({'pyrrhic_ratio': -1}, 'pyrrhic_ratio'),
])
def test_bad_verdict_params_are_refused(change, message):
    with pytest.raises(ValueError, match=message):
        AftermathParams(**change)


SETUP = {'seed': 7, 'sides': ['Union', 'Confederate'], 'units': [
    {'id': 'us', 'side': 0, 'size': 1000, 'stats': '6/6/1/0'}, {'id': 'cs', 'side': 1, 'size': 1000, 'stats': '4/4/0/0'}]}
FIRE = {'us': {'target': 'cs', 'mode': 'ranged'}, 'cs': {'target': 'us', 'mode': 'ranged'}}


def test_side_summary_gives_each_side_its_verdict():
    state, _, _ = api.run_scenario({**SETUP, 'rounds': [{'duration': 60, 'orders': FIRE}], 'finish': 'none'})
    assert [s['verdict'] for s in api.side_summary(state)] == ['draw', 'draw']
    state, _, _ = api.run_scenario({**SETUP, 'rounds': [{'duration': 600, 'orders': FIRE}], 'finish': True})
    union, confed = api.side_summary(state)
    expected = api.verdicts(0, state['result']['field_decided_by'], [union['casualties'], confed['casualties']],
                            [union['started'], confed['started']], AftermathParams())
    assert [union['verdict'], confed['verdict']] == expected and union['outcome'] == 'won'


def test_older_states_without_the_verdict_params_use_the_defaults():
    state, _, _ = api.run_scenario({**SETUP, 'rounds': [{'duration': 600, 'orders': FIRE}], 'finish': True})
    for key in ('decisive_ratio', 'decisive_share', 'pyrrhic_share', 'pyrrhic_ratio'):
        del state['params']['aftermath'][key]
    assert api.side_summary(state)[0]['verdict'] == 'decisive victory'
