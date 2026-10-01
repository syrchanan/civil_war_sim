import pytest

from imperial_generals import tuning, validation
from imperial_generals.battles.setup import SetupError

FIRE = {'target': None, 'mode': 'ranged'}


def scenario(expect=None, **changes):
    data = {
        'meta': {'name': 'Rout'},
        'sides': ['Blue', 'Red'],
        'units': [
            {'id': 'big', 'side': 'Blue', 'type': 'inf', 'subtype': 'line', 'size': 3000, 'stats': '7/7/1/0'},
            {'id': 'small', 'side': 'Red', 'type': 'inf', 'subtype': 'line', 'size': 300, 'stats': '2/2/0/0'},
        ],
        'rounds': [{'duration': 240, 'orders': {'big': {'target': 'small', 'mode': 'ranged'},
                                                'small': {'target': 'big', 'mode': 'ranged'}}}],
    }
    if expect is not None:
        data['expect'] = expect
    data.update(changes)
    return data


# =============================================================================
# Reading the expect block
# =============================================================================

def test_bands_parse_in_friendly_forms():
    assert validation.parse_band('25-35%') == (0.25, 0.35)
    assert validation.parse_band('25 – 35 %') == (0.25, 0.35)
    assert validation.parse_band('<10%') == (0.0, 0.10)
    assert validation.parse_band('>40%') == (0.40, 1.0)
    assert validation.parse_band('12%-25%') == (0.12, 0.25)
    for bad in ('lots', '35-25%', '5-150%', 30):
        with pytest.raises(ValueError):
            validation.parse_band(bad)


def test_expect_block_is_normalised():
    exp = validation.read_expect(scenario({
        'author': 'Jane', 'source': 'Fox 1889', 'confidence': 'High', 'notes': 'a rout',
        'field_held_by': 'Blue', 'breaks': ['small'], 'holds': ['big'],
        'casualties': {'Red': '>40%', 'winner': '<10%'},
    }))
    assert exp['author'] == 'Jane' and exp['confidence'] == 'high'
    assert exp['field_held_by'] == 0
    assert exp['breaks'] == ['small'] and exp['holds'] == ['big']
    assert exp['casualties'] == {1: (0.40, 1.0), 'winner': (0.0, 0.10)}
    assert validation.read_expect(scenario({'field_held_by': 'none'}))['field_held_by'] is None
    assert validation.read_expect(scenario()) is None


@pytest.mark.parametrize('expect, message', [
    ('Blue wins', 'expect must be a mapping (field_held_by, breaks, holds, casualties, ...).'),
    ({'winner': 'Blue'}, 'expect: unknown key "winner". Allowed: author, breaks, casualties, confidence, '
                         'field_held_by, holds, notes, source.'),
    ({'field_held_by': 'Green'}, 'expect.field_held_by must be a side name (Blue, Red), 0, 1 or none; '
                                 "got 'Green'."),
    ({'breaks': ['nobody']}, 'expect.breaks: unknown unit "nobody".'),
    ({'holds': 'big'}, 'expect.holds must be a list of unit ids.'),
    ({'breaks': ['big'], 'holds': ['big']}, 'expect: "big" can\'t both break and hold.'),
    ({'casualties': {'Green': '10-20%'}}, 'expect.casualties: "Green" must be a side name (Blue, Red), '
                                          'winner or loser.'),
    ({'casualties': {'Blue': 'lots'}}, 'expect.casualties.Blue: write a band like "25-35%", "<10%" or ">40%".'),
    ({'casualties': []}, 'expect.casualties must map sides to bands like "25-35%".'),
    ({'confidence': 'very'}, 'expect.confidence must be low, medium or high.'),
])
def test_expect_problems(expect, message):
    with pytest.raises(SetupError) as info:
        validation.read_expect(scenario(expect))
    assert message in info.value.errors


def test_expect_and_feedback_are_allowed_in_a_scenario():
    from imperial_generals.battles.setup import battle_from_setup
    battle_from_setup(scenario({'breaks': ['small']}, feedback=[]))


# =============================================================================
# Grading the engine against expectations
# =============================================================================

GOOD = {'field_held_by': 'Blue', 'breaks': ['small'], 'holds': ['big'],
        'casualties': {'winner': '<10%', 'loser': '>10%', 'Red': '>10%'}}


def test_check_grades_each_expectation():
    report = validation.check(scenario(GOOD), seeds=20)
    assert report['name'] == 'Rout' and report['seeds'] == 20
    assert report['engine'] == validation.engine_stamp()
    kinds = [e['kind'] for e in report['expectations']]
    assert kinds == ['field_held_by', 'breaks', 'holds', 'casualties', 'casualties', 'casualties']
    for e in report['expectations']:
        assert e['share'] == 1.0 and e['verdict'] == 'agrees'
        assert e['text'] and e['engine']
    assert report['agree'] == 6 and report['total'] == 6


def test_check_measures_how_often_the_engine_agrees():
    report = validation.check(scenario(GOOD), seeds=20)
    batch = tuning.run_batch(scenario(GOOD), seeds=20)
    red = [r['s1_casualty_share'] for r in batch.runs]
    (red_cas,) = [e for e in report['expectations'] if e['text'].startswith('Red casualties')]
    assert red_cas['share'] == sum(c > 0.10 for c in red) / 20
    assert red_cas['engine'] == f"typically {tuning.quantile(red, .5):.0%} (8 in 10 runs: " \
                                f"{tuning.quantile(red, .1):.0%}-{tuning.quantile(red, .9):.0%})"


def test_wrong_expectations_disagree():
    wrong = {'field_held_by': 'Red', 'breaks': ['big'], 'holds': ['small'], 'casualties': {'Blue': '>40%'}}
    report = validation.check(scenario(wrong), seeds=10)
    assert [e['verdict'] for e in report['expectations']] == ['disagrees'] * 4
    assert report['agree'] == 0


def test_verdict_thresholds():
    assert validation.verdict(0.6) == 'agrees'
    assert validation.verdict(0.59) == 'sometimes'
    assert validation.verdict(0.3) == 'sometimes'
    assert validation.verdict(0.29) == 'disagrees'


def test_winner_and_loser_skip_undecided_runs():
    # nobody breaks in 10 minutes: no winner or loser, so those expectations can't be graded
    calm = scenario({'casualties': {'winner': '<10%', 'loser': '>10%'}},
                    rounds=[{'duration': 10}])
    report = validation.check(calm, seeds=5)
    for e in report['expectations']:
        assert e['share'] is None and e['verdict'] == 'undecided'
        assert e['engine'] == 'no run had a clear winner'
    assert report['total'] == 0


def test_scenario_without_expectations_cannot_be_checked():
    with pytest.raises(SetupError) as info:
        validation.check(scenario(), seeds=2)
    assert info.value.errors == ['This scenario has no "expect" block: say what should happen.']


def test_engine_stamp_follows_the_tuning():
    from imperial_generals.params import BattleParams
    stamp = validation.engine_stamp()
    assert len(stamp) == 8 and stamp == validation.engine_stamp()
    tuned = BattleParams().with_overrides({'combat': {'ranged_kill_rate': 0.005}})
    assert validation.engine_stamp(tuned) != stamp


def test_side_summary_casualties():
    from imperial_generals import api
    state, _, _ = api.run_scenario({**scenario(), 'finish': True}, seed=1)
    for s in api.side_summary(state):
        assert s['casualties'] == s['killed'] + s['wounded'] + s['prisoners_lost']
        assert s['casualty_share'] == pytest.approx(s['casualties'] / s['started'])


def test_winner_by_men_broken_when_nobody_holds_the_field():
    # Red keeps an idle reserve, so the field isn't won outright; Blue still won (fewer of its men broke)
    data = scenario({'casualties': {'winner': '1-10%', 1: '>10%'}, 'field_held_by': 0})
    data['units'].append({'id': 'reserve', 'side': 'Red', 'size': 100, 'stats': '5/5/0/0'})
    report = validation.check(data, seeds=10)
    field, winner, red = report['expectations']
    assert field['share'] == 0 and 'nobody 100%' in field['engine']
    assert winner['text'] == 'Winner casualties 1%-10%' and winner['share'] is not None   # Blue won every run
    assert red['text'].startswith('Red casualties over 10%')


# =============================================================================
# Detail for players: how the battle usually went, unit by unit, charges, a typical run
# =============================================================================

CHARGE = scenario(GOOD, rounds=[
    {'duration': 60, 'orders': {'big': {'target': 'small', 'mode': 'ranged'}, 'small': {'target': 'big', 'mode': 'ranged'}}},
    {'duration': 30, 'orders': {'big': {'target': 'small', 'mode': 'melee'}}},
])


def test_batches_record_every_charge():
    batch = tuning.run_batch(CHARGE, seeds=6)
    assert len(batch.charge_runs) == sum(1 for r in batch.runs if r['first_charge'] is not None)
    for c in batch.charge_runs:
        assert (c['charger'], c['target'], c['round']) == ('big', 'small', 2)
        assert c['outcome'] in ('home', 'faltered', 'defender_broke', 'pursuit', 'target_broke', 'charger_broke')


def test_report_describes_each_side():
    report = validation.check(scenario(GOOD), seeds=12)
    batch = tuning.run_batch(scenario(GOOD), seeds=12)
    blue, red = report['sides']
    assert (blue['name'], red['name']) == ('Blue', 'Red')
    assert blue['men'] == 3000 and blue['units'] == 1
    shares = [r['s1_casualty_share'] for r in batch.runs]
    assert red['casualties'] == {'p10': tuning.quantile(shares, .1), 'p50': tuning.quantile(shares, .5),
                                 'p90': tuning.quantile(shares, .9)}
    assert red['units_out_mean'] == pytest.approx(sum(r['s1_units_out'] for r in batch.runs) / 12)
    assert blue['prisoners_taken_p50'] == tuning.quantile([r['s0_prisoners_taken'] for r in batch.runs], .5)
    assert blue['field_held'] == pytest.approx(sum(r['field_held_by'] == 0 for r in batch.runs) / 12)


def test_report_describes_each_unit():
    report = validation.check(scenario(GOOD), seeds=12)
    batch = tuning.run_batch(scenario(GOOD), seeds=12)
    big, small = report['units']
    assert (small['id'], small['name'], small['side']) == ('small', 'small', 'Red')
    rows = [u for u in batch.unit_runs if u['id'] == 'small']
    shares = [(u['hits'] + u['captured']) / u['started'] for u in rows]
    assert small['break_share'] == sum(u['broken'] or u['wiped_out'] for u in rows) / 12
    assert small['broke_at_p50'] == tuning.quantile([u['broke_at'] for u in rows if u['broke_at'] is not None], .5)
    assert small['casualties'] == {'p10': tuning.quantile(shares, .1), 'p50': tuning.quantile(shares, .5),
                                   'p90': tuning.quantile(shares, .9)}
    assert big['inflicted_p50'] == tuning.quantile([u['inflicted'] for u in batch.unit_runs if u['id'] == 'big'], .5)
    assert big['broke_at_p50'] is None


def test_report_describes_each_charge():
    report = validation.check(CHARGE, seeds=10)
    batch = tuning.run_batch(CHARGE, seeds=10)
    if not batch.charge_runs:
        assert report['charges'] == []
        return
    (charge,) = report['charges']
    outcomes = [c['outcome'] for c in batch.charge_runs]
    assert (charge['charger'], charge['target'], charge['round']) == ('big', 'small', 2)
    assert charge['made'] == len(outcomes) / 10
    assert charge['outcomes'] == {o: outcomes.count(o) / len(outcomes) for o in dict.fromkeys(outcomes)}
    assert validation.check(scenario(GOOD), seeds=3)['charges'] == []


def test_report_replays_a_typical_run():
    from imperial_generals import api
    report = validation.check(CHARGE, seeds=12)
    typical = report['typical']
    batch = tuning.run_batch(CHARGE, seeds=12)
    seed = typical['seed']
    assert seed in batch.seeds
    # the run whose casualties are closest to the usual ones, among runs with the usual field holder
    row = {r['seed']: r for r in batch.runs}[seed]
    state, reports, result = api.run_scenario({**CHARGE, 'finish': True}, seed=seed)
    assert typical['rounds'] == reports
    assert typical['result'] == api.side_summary(state)
    assert typical['units'] == {u['id']: u['name'] for u in state['units']}
    assert typical['field_held_by'] == result['field_held_by'] == row['field_held_by']
