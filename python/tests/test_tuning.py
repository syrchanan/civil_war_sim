import csv
import os

import pytest

from imperial_generals import api, tuning
from imperial_generals.battles.setup import SetupError, load_setup_file

EXAMPLE = os.path.join(os.path.dirname(__file__), '../../scenarios/example_ridge.yaml')
SMALL = {
    'meta': {'name': 'Small fight'},
    'sides': ['Blue', 'Red'],
    'units': [
        {'id': 'b1', 'side': 'Blue', 'type': 'inf', 'subtype': 'line', 'size': 600, 'stats': '6/6/1/0'},
        {'id': 'r1', 'side': 'Red', 'type': 'inf', 'subtype': 'line', 'size': 500, 'stats': '3/3/0/0'},
        {'id': 'r2', 'side': 'Red', 'type': 'art', 'subtype': 'battery', 'stats': '5/5/0/0'},
    ],
    'rounds': [{'duration': 90, 'orders': {'b1': {'target': 'r1', 'mode': 'ranged'},
                                           'r1': {'target': 'b1', 'mode': 'ranged'},
                                           'r2': {'target': 'b1', 'mode': 'ranged'}}}] * 3,
}


# =============================================================================
# Quantiles
# =============================================================================

def test_quantile_interpolates():
    assert tuning.quantile([3, 1, 2], 0.5) == 2
    assert tuning.quantile([0, 10], 0.25) == 2.5
    assert tuning.quantile([4], 0.9) == 4
    assert tuning.quantile([], 0.5) is None


# =============================================================================
# Batches of seeds
# =============================================================================

def test_batch_runs_each_seed_like_run_scenario():
    batch = tuning.run_batch(SMALL, seeds=5, seed_start=10)
    assert batch.name == 'Small fight' and batch.sides == ['Blue', 'Red']
    assert [r['seed'] for r in batch.runs] == [10, 11, 12, 13, 14]
    state, reports, result = api.run_scenario({**SMALL, 'finish': True}, seed=12)
    blue, red = api.side_summary(state)
    row = batch.runs[2]
    assert row['field_held_by'] == result['field_held_by']
    assert row['end_time'] == state['time']
    assert (row['s0_started'], row['s0_final'], row['s0_hits_taken']) == (blue['started'], blue['final'],
                                                                         blue['hits_taken'])
    assert row['s1_loss_share'] == red['loss_share'] and row['s1_units_out'] == red['units_out']
    assert row['s0_units'] == 1 and row['s1_units'] == 2
    units = [u for u in batch.unit_runs if u['seed'] == 12]
    assert [u['id'] for u in units] == ['b1', 'r1', 'r2']
    r1 = units[1]
    assert r1['hits'] == state['units'][1]['losses'] and r1['inflicted'] == state['units'][1]['inflicted']
    broke = [rep['units']['r1']['broke_at'] for rep in reports if rep['units']['r1']['broke_at'] is not None]
    assert r1['broke_at'] == (broke[0] if broke else None)
    assert r1['broken'] == state['units'][1]['morale']['broken']


def test_first_break_is_the_sides_earliest_break():
    batch = tuning.run_batch(SMALL, seeds=8)
    for row in batch.runs:
        for side in (0, 1):
            times = [u['broke_at'] for u in batch.unit_runs
                     if u['seed'] == row['seed'] and u['side'] == side and u['broke_at'] is not None]
            assert row[f's{side}_first_break'] == (min(times) if times else None)


def test_batch_respects_the_scenarios_finish():
    batch = tuning.run_batch({**SMALL, 'finish': 'Red'}, seeds=3)
    assert all(r['field_held_by'] == 1 for r in batch.runs)


def test_parallel_batch_gives_identical_results():
    one = tuning.run_batch(SMALL, seeds=6, workers=1)
    two = tuning.run_batch(SMALL, seeds=6, workers=2)
    assert one.runs == two.runs and one.unit_runs == two.unit_runs


def test_overrides_reach_every_run():
    # musketry all but stops; the battery (per-gun rates) still fires
    calm = tuning.run_batch(SMALL, seeds=3, overrides={'combat': {'ranged_kill_rate': 1e-9}})
    assert all(u['hits'] == 0 for u in calm.unit_runs if u['id'] == 'r1')
    assert all(r['s1_hits_taken'] == 0 for r in calm.runs)
    assert any(u['hits'] > 0 for u in calm.unit_runs if u['id'] == 'b1')


def test_bad_scenarios_and_overrides_fail_before_running():
    with pytest.raises(SetupError):
        tuning.run_batch({**SMALL, 'units': []}, seeds=3)
    with pytest.raises(SetupError) as info:
        tuning.run_batch(SMALL, seeds=3, overrides={'combat': {'nope': 1}})
    assert info.value.errors == ["overrides: Unknown combat parameter(s): ['nope']."]
    with pytest.raises(SetupError):
        tuning.run_batch({**SMALL, 'rounds': [{'duration': -1}]}, seeds=3)
    with pytest.raises(ValueError, match='seeds'):
        tuning.run_batch(SMALL, seeds=0)
    with pytest.raises(ValueError, match='workers'):
        tuning.run_batch(SMALL, seeds=2, workers=0)


# =============================================================================
# Summaries
# =============================================================================

def test_summary_of_a_batch():
    batch = tuning.run_batch(SMALL, seeds=30)
    summary = tuning.summarize(batch)
    assert summary['name'] == 'Small fight' and summary['seeds'] == 30
    assert sum(summary['field'].values()) == pytest.approx(1.0)
    assert set(summary['field']) == {'Blue', 'Red', 'nobody'}
    held = sum(r['field_held_by'] == 0 for r in batch.runs) / 30
    assert summary['field']['Blue'] == pytest.approx(held)

    blue = summary['sides'][0]
    losses = [r['s0_loss_share'] for r in batch.runs]
    assert blue['name'] == 'Blue'
    assert blue['loss_share']['p50'] == tuning.quantile(losses, 0.5)
    assert blue['loss_share']['mean'] == pytest.approx(sum(losses) / 30)
    assert blue['units_out_mean'] == pytest.approx(sum(r['s0_units_out'] for r in batch.runs) / 30)
    assert blue['units'] == 1
    broke = [r['s0_first_break'] for r in batch.runs if r['s0_first_break'] is not None]
    assert blue['first_break']['share'] == pytest.approx(len(broke) / 30)
    assert blue['first_break']['p50'] == tuning.quantile(broke, 0.5)
    ratios = [r['s0_exchange_ratio'] for r in batch.runs if r['s0_exchange_ratio'] is not None]
    assert blue['exchange_ratio']['p50'] == tuning.quantile(ratios, 0.5)
    assert blue['prisoners_taken_mean'] == pytest.approx(sum(r['s0_prisoners_taken'] for r in batch.runs) / 30)
    assert blue['guns_taken_mean'] == pytest.approx(sum(r['s0_guns_taken'] for r in batch.runs) / 30)

    r1 = summary['units'][1]
    rows = [u for u in batch.unit_runs if u['id'] == 'r1']
    assert (r1['id'], r1['name'], r1['side']) == ('r1', 'r1', 1)
    assert r1['break_share'] == pytest.approx(sum(u['broken'] for u in rows) / 30)
    assert r1['hit_share']['p50'] == tuning.quantile([u['hits'] / u['started'] for u in rows], 0.5)
    assert r1['inflicted_mean'] == pytest.approx(sum(u['inflicted'] for u in rows) / 30)


def test_summary_when_nothing_breaks():
    calm = {**SMALL, 'rounds': [{'duration': 5}]}
    summary = tuning.summarize(tuning.run_batch(calm, seeds=3))
    blue = summary['sides'][0]
    assert blue['first_break'] == {'share': 0.0, 'p50': None}
    assert blue['exchange_ratio'] == {'mean': None, 'p10': None, 'p50': None, 'p90': None}
    assert summary['units'][0]['broke_at_p50'] is None
    assert summary['field'] == {'Blue': 0.0, 'Red': 0.0, 'nobody': 1.0}


def test_runs_write_to_csv(tmp_path):
    batch = tuning.run_batch(SMALL, seeds=3)
    path = tmp_path / 'runs.csv'
    tuning.write_csv(batch.runs, path)
    with open(path, newline='', encoding='utf-8') as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 3 and rows[0]['seed'] == '0'
    assert set(rows[0]) == set(batch.runs[0])


def test_example_scenario_batch():
    summary = tuning.summarize(tuning.run_batch(load_setup_file(EXAMPLE), seeds=4))
    assert [s['name'] for s in summary['sides']] == ['Union', 'Confederate']
    assert len(summary['units']) == 7


# =============================================================================
# Matchup grid
# =============================================================================

GRID = {
    'name': 'Basic',
    'seeds': 6,
    'rounds': [60, 60],
    'units': {
        'line': {'type': 'inf', 'subtype': 'line', 'size': 1000, 'stats': '5/5/0/0'},
        'heavy_cav': {'type': 'cav', 'subtype': 'heavy', 'size': 500, 'stats': '5/5/0/1', 'attack': 'melee',
                      'defend': 'melee'},
        'battery': {'type': 'art', 'subtype': 'battery', 'stats': '5/5/0/0',
                    'attack': {'mode': 'ranged', 'ammo': 'canister'}},
    },
}


def test_matchup_grid_cells():
    grid = tuning.matchup_grid(GRID)
    assert grid.name == 'Basic' and grid.keys == ['line', 'heavy_cav', 'battery'] and grid.seeds == 6
    assert set(grid.cells) == {(a, d) for a in grid.keys for d in grid.keys}
    for cell in grid.cells.values():
        assert cell['advantage'] == pytest.approx(cell['attacker_wins'] - cell['defender_wins'])
        assert 0 <= cell['attacker_wins'] <= cell['defender_breaks'] <= 1
        assert 0 <= cell['defender_wins'] <= cell['attacker_breaks'] <= 1


def test_matchup_cell_is_a_two_unit_scenario():
    grid = tuning.matchup_grid(GRID)
    cav, line = GRID['units']['heavy_cav'], GRID['units']['line']
    scenario = tuning.matchup_scenario(GRID, 'heavy_cav', 'line')
    assert scenario['units'][0] == {'id': 'attacker', 'name': 'heavy_cav', 'side': 0, 'type': 'cav',
                                    'subtype': 'heavy', 'size': 500, 'stats': '5/5/0/1'}
    assert scenario['units'][1]['name'] == 'line' and scenario['units'][1]['side'] == 1
    assert scenario['rounds'] == [{'duration': 60, 'orders': {
        'attacker': {'target': 'defender', 'mode': 'melee'},
        'defender': {'target': 'attacker', 'mode': 'ranged'}}}] * 2
    batch = tuning.run_batch(scenario, seeds=6)
    attacker_wins = sum(r['s1_units_out'] == 1 and r['s0_units_out'] == 0 for r in batch.runs) / 6
    assert grid.cells[('heavy_cav', 'line')]['attacker_wins'] == pytest.approx(attacker_wins)
    hits = [u['hits'] / u['started'] for u in batch.unit_runs if u['id'] == 'defender']
    assert grid.cells[('heavy_cav', 'line')]['defender_hit_share'] == pytest.approx(sum(hits) / 6)
    assert cav and line


def test_matchup_orders_can_be_idle_and_carry_ammo():
    battery_vs_line = tuning.matchup_scenario(GRID, 'battery', 'line')
    assert battery_vs_line['rounds'][0]['orders']['attacker'] == {'target': 'defender', 'mode': 'ranged',
                                                                  'ammo': 'canister'}
    spec = {**GRID, 'units': {**GRID['units'], 'line': {**GRID['units']['line'], 'defend': 'idle'}}}
    assert tuning.matchup_scenario(spec, 'battery', 'line')['rounds'][0]['orders'] == {
        'attacker': {'target': 'defender', 'mode': 'ranged', 'ammo': 'canister'}}


def test_exchange_ratio_is_none_when_the_attacker_is_never_hit():
    spec = {'seeds': 2, 'rounds': [30], 'units': {
        'line': {'type': 'inf', 'subtype': 'line', 'size': 1000, 'stats': '5/5/0/0', 'defend': 'idle'}}}
    cell = tuning.matchup_grid(spec).cells[('line', 'line')]
    assert cell['exchange_ratio'] is None


def test_matchup_grid_seeds_and_parallel():
    grid = tuning.matchup_grid(GRID, seeds=3)
    assert grid.seeds == 3
    assert tuning.matchup_grid(GRID, seeds=3, workers=2).cells == grid.cells


@pytest.mark.parametrize('changes, message', [
    ({'units': {}}, '"units" must map names to unit specs (type, subtype, size, stats, attack, defend).'),
    ({'rounds': []}, '"rounds" must be a list of round lengths in minutes, e.g. [90, 90].'),
    ({'rounds': [0]}, '"rounds" must be a list of round lengths in minutes, e.g. [90, 90].'),
    ({'seeds': 0}, '"seeds" must be a positive whole number.'),
    ({'turns': 3}, 'Unknown key "turns". Allowed: name, params, rounds, seeds, units.'),
    ({'units': {'x': {'size': 10, 'stats': '5/5/0/0', 'attack': 'charge'}}},
     'units.x: attack must be ranged, melee, idle or {mode, ammo}; got \'charge\'.'),
    ({'units': {'x': {'size': 10, 'stats': '5/5/0/0', 'defend': {'mode': 'ranged', 'aim': 1}}}},
     'units.x: defend must be ranged, melee, idle or {mode, ammo}; got {\'mode\': \'ranged\', \'aim\': 1}.'),
    ({'units': {'x': {'size': 10, 'stats': '5/5/x/0'}}},
     'units.x: stats must be four whole numbers like "5/5/0/0" (experience/morale/weapon/melee-only); got \'5/5/x/0\'.'),
    ({'units': {'x': {'size': 10, 'stats': '5/5/0/0', 'side': 0}}},
     'units.x: unknown key "side". Allowed: attack, defend, front_size, guns, meta, size, stats, subtype, type.'),
    ({'params': {'combat': {'nope': 1}}}, "params: Unknown combat parameter(s): ['nope']."),
])
def test_matchup_spec_problems(changes, message):
    with pytest.raises(SetupError) as info:
        tuning.matchup_grid({**GRID, **changes})
    assert message in info.value.errors


def test_matchup_spec_must_be_a_mapping():
    with pytest.raises(SetupError) as info:
        tuning.matchup_grid([])
    assert info.value.errors == ['The matchup file must be a mapping with "units" and "rounds".']


def test_matchup_heatmap_and_csv(tmp_path):
    grid = tuning.matchup_grid(GRID, seeds=3)
    tuning.plot_matchups(grid, tmp_path / 'grid.png')
    assert (tmp_path / 'grid.png').stat().st_size > 1000
    tuning.write_csv(grid.rows(), tmp_path / 'grid.csv')
    with open(tmp_path / 'grid.csv', newline='', encoding='utf-8') as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 9 and rows[0]['attacker'] == 'line' and rows[0]['defender'] == 'line'
    assert 'advantage' in rows[0]


def test_matchup_unit_spec_must_be_a_mapping():
    with pytest.raises(SetupError) as info:
        tuning.matchup_grid({**GRID, 'units': {'x': 'line'}})
    assert info.value.errors == ['units.x: must be a mapping.']


def test_matchup_params_reach_each_cell():
    spec = {**GRID, 'params': {'combat': {'ranged_kill_rate': 0.01}}}
    assert tuning.matchup_scenario(spec, 'line', 'line')['params'] == {'combat': {'ranged_kill_rate': 0.01}}
    assert 'params' not in tuning.matchup_scenario(GRID, 'line', 'line')


def test_share_heatmap(tmp_path):
    grid = tuning.matchup_grid(GRID, seeds=2)
    tuning.plot_matchups(grid, tmp_path / 'breaks.png', metric='defender_breaks')
    assert (tmp_path / 'breaks.png').stat().st_size > 1000


def test_default_workers_is_the_cpu_count():
    assert tuning.default_workers() == (os.cpu_count() or 1)


# =============================================================================
# Faceted grids: everyone fires, or everyone fights hand to hand
# =============================================================================

def test_ranged_facet_overrides_orders_but_keeps_ammo():
    cav_v_battery = tuning.matchup_scenario(GRID, 'heavy_cav', 'battery', mode='ranged')
    assert cav_v_battery['rounds'][0]['orders'] == {
        'attacker': {'target': 'defender', 'mode': 'ranged'},
        'defender': {'target': 'attacker', 'mode': 'ranged'}}            # battery's defend has no ammo: default
    battery_v_line = tuning.matchup_scenario(GRID, 'battery', 'line', mode='ranged')
    assert battery_v_line['rounds'][0]['orders']['attacker'] == {'target': 'defender', 'mode': 'ranged',
                                                                 'ammo': 'canister'}
    spec = {**GRID, 'units': {**GRID['units'], 'line': {**GRID['units']['line'], 'defend': 'idle'}}}
    assert tuning.matchup_scenario(spec, 'battery', 'line', mode='ranged')['rounds'][0]['orders']['defender'] == {
        'target': 'attacker', 'mode': 'ranged'}


def test_melee_facet_is_melee_both_ways():
    orders = tuning.matchup_scenario(GRID, 'battery', 'line', mode='melee')['rounds'][0]['orders']
    assert orders == {'attacker': {'target': 'defender', 'mode': 'melee'},
                      'defender': {'target': 'attacker', 'mode': 'melee'}}


def test_faceted_grids():
    # melee-only is the stats flag (x/x/x/1), not the subtype: any such unit inflicts nothing at range
    spec = {**GRID, 'units': {**GRID['units'],
                              'pikes': {'type': 'inf', 'subtype': 'pikes', 'size': 1000, 'stats': '5/5/-2/1'},
                              'warband': {'type': 'inf', 'subtype': 'irregulars', 'size': 1000, 'stats': '5/5/0/1'}}}
    ranged = tuning.matchup_grid(spec, mode='ranged', seeds=3)
    assert ranged.mode == 'ranged' and ranged.rows()[0]['mode'] == 'ranged'
    melee_only = [k for k, u in spec['units'].items() if u['stats'].endswith('/1')]
    assert set(melee_only) == {'heavy_cav', 'pikes', 'warband'}
    for a in melee_only:
        for d in ranged.keys:
            cell = ranged.cells[(a, d)]
            assert cell['defender_hit_share'] == 0 and cell['attacker_wins'] == 0
            assert cell['exchange_ratio'] in (0, None)          # None: neither side could fire
    assert ranged.cells[('line', 'warband')]['defender_hit_share'] > 0
    melee = tuning.matchup_grid(spec, mode='melee', seeds=3)
    assert melee.mode == 'melee'
    assert tuning.matchup_grid(GRID, seeds=3).mode == 'orders'
    with pytest.raises(ValueError, match='mode'):
        tuning.matchup_grid(GRID, mode='charge')


def test_heatmap_title_names_the_facet(tmp_path):
    grid = tuning.matchup_grid(GRID, mode='melee', seeds=2)
    tuning.plot_matchups(grid, tmp_path / 'm.png')
    assert (tmp_path / 'm.png').exists()


# =============================================================================
# Artillery at long range: only other batteries can reply
# =============================================================================

def test_artillery_facet_scenarios():
    battery_v_line = tuning.matchup_scenario(GRID, 'battery', 'line', mode='artillery')
    assert battery_v_line['rounds'][0]['orders'] == {
        'attacker': {'target': 'defender', 'mode': 'ranged', 'ammo': 'canister'}}     # unreturned fire
    battery_v_battery = tuning.matchup_scenario(GRID, 'battery', 'battery', mode='artillery')
    assert battery_v_battery['rounds'][0]['orders']['defender'] == {'target': 'attacker', 'mode': 'ranged'}


def test_artillery_facet_grid_has_artillery_rows_only():
    grid = tuning.matchup_grid(GRID, mode='artillery', seeds=3)
    assert grid.attackers == ['battery'] and grid.keys == ['line', 'heavy_cav', 'battery']
    assert set(grid.cells) == {('battery', d) for d in grid.keys}
    assert [r['attacker'] for r in grid.rows()] == ['battery'] * 3
    for d in ('line', 'heavy_cav'):
        assert grid.cells[('battery', d)]['attacker_hit_share'] == 0
    assert tuning.matchup_grid(GRID, mode='ranged', seeds=2).attackers == grid.keys


def test_artillery_facet_needs_artillery():
    spec = {**GRID, 'units': {'line': GRID['units']['line']}}
    with pytest.raises(ValueError, match='artillery'):
        tuning.matchup_grid(spec, mode='artillery')


def test_artillery_heatmap(tmp_path):
    tuning.plot_matchups(tuning.matchup_grid(GRID, mode='artillery', seeds=2), tmp_path / 'a.png')
    assert (tmp_path / 'a.png').exists()
