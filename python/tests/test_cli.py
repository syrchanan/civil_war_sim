import json

import pytest

from imperial_generals import api
from imperial_generals.battles.setup import load_setup_file
from imperial_generals.cli import main

SETUP_YAML = """\
meta: {name: Test Ridge}
seed: 7
sides: [Union, Confederate]
units:
  - {id: us_1mn, name: 1st Minnesota, side: Union, type: inf, subtype: line, size: 1000, stats: 6/6/1/0}
  - {id: cs_26nc, name: 26th North Carolina, side: Confederate, type: inf, subtype: line, size: 1000, stats: 3/3/0/0}
  - {id: cs_bat, name: Battery A, side: Confederate, type: art, subtype: battery, stats: 5/5/0/0}
"""
ORDERS_YAML = """\
us_1mn: {target: cs_26nc, mode: ranged}
cs_26nc: {target: us_1mn, mode: ranged}
cs_bat: {target: us_1mn, mode: ranged, ammo: shell}
"""
ORDERS = {'us_1mn': {'target': 'cs_26nc', 'mode': 'ranged'}, 'cs_26nc': {'target': 'us_1mn', 'mode': 'ranged'},
          'cs_bat': {'target': 'us_1mn', 'mode': 'ranged', 'ammo': 'shell'}}


@pytest.fixture
def files(tmp_path):
    (tmp_path / 'setup.yaml').write_text(SETUP_YAML, encoding='utf-8')
    (tmp_path / 'orders.yaml').write_text(ORDERS_YAML, encoding='utf-8')
    return tmp_path


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def run(capsys, *argv):
    code = main([str(a) for a in argv])
    out, err = capsys.readouterr()
    return code, out, err


def new(capsys, files):
    run(capsys, 'new', files / 'setup.yaml', '-o', files / 'state.json')


def test_new_writes_a_state_file(files, capsys):
    code, out, _ = run(capsys, 'new', files / 'setup.yaml', '-o', files / 'state.json')
    assert code == 0
    state = read(files / 'state.json')
    assert state['round'] == 0 and state['seed'] == 7
    assert 'state.json' in out and '3 units' in out
    run(capsys, 'new', files / 'setup.yaml', '-o', files / 's2.json', '--seed', 11)
    assert read(files / 's2.json')['seed'] == 11


def test_resolve_updates_the_state_in_place_and_prints_the_round(files, capsys):
    new(capsys, files)
    code, out, _ = run(capsys, 'resolve', files / 'state.json', '--duration', 90, '--orders', files / 'orders.yaml')
    assert code == 0
    expected_state, expected = api.step(api.new_battle(load_setup_file(files / 'setup.yaml')), 90, ORDERS)
    assert read(files / 'state.json') == expected_state
    assert 'Round 1' in out and '0-90 min' in out
    assert '1st Minnesota' in out and 'Union' in out and 'Confederate' in out
    assert str(expected['units']['us_1mn']['losses']) in out


def test_resolve_can_write_elsewhere_and_print_json(files, capsys):
    new(capsys, files)
    before = read(files / 'state.json')
    code, out, _ = run(capsys, 'resolve', files / 'state.json', '--duration', 60, '-o', files / 'next.json',
                       '--json', '--events')
    assert code == 0
    assert read(files / 'state.json') == before
    report = json.loads(out)
    assert report['round'] == 1 and report['orders'] == {}
    assert read(files / 'next.json')['round'] == 1


def test_breaks_and_wipe_outs_are_shown(files, capsys):
    new(capsys, files)
    out = ''
    for _ in range(6):
        _, out, _ = run(capsys, 'resolve', files / 'state.json', '--duration', 120, '--orders', files / 'orders.yaml')
        if 'broke at' in out:
            break
    assert 'broke at' in out
    state = read(files / 'state.json')
    state['units'][2]['size'] = 0
    (files / 'state.json').write_text(json.dumps(state), encoding='utf-8')
    _, out, _ = run(capsys, 'show', files / 'state.json')
    assert 'wiped out' in out and 'broken' in out


def test_preview_lists_engagements_without_changing_anything(files, capsys):
    new(capsys, files)
    before = read(files / 'state.json')
    code, out, _ = run(capsys, 'preview', files / 'state.json', '--orders', files / 'orders.yaml')
    assert code == 0
    assert read(files / 'state.json') == before
    assert '26th North Carolina -> 1st Minnesota' in out and 'ranged' in out and 'men/min' in out
    _, out, _ = run(capsys, 'preview', files / 'state.json', '--orders', files / 'orders.yaml', '--json')
    assert len(json.loads(out)) == 3
    _, out, _ = run(capsys, 'preview', files / 'state.json')
    assert 'No engagements' in out


def test_finish_settles_casualties(files, capsys):
    new(capsys, files)
    run(capsys, 'resolve', files / 'state.json', '--duration', 90, '--orders', files / 'orders.yaml')
    code, out, _ = run(capsys, 'finish', files / 'state.json', '--field', 'Union')
    assert code == 0
    state = read(files / 'state.json')
    assert state['finished'] and state['result']['field_held_by'] == 0
    assert 'Field held by: Union' in out and 'Killed' in out and 'Returned' in out
    # the final table adds up: Started - Killed - Wounded - Prisoners + Returned = Final
    header = out.splitlines()[1].split()
    assert header[2:] == ['Started', 'Killed', 'Wounded', 'Prisoners', 'Returned', 'Final', 'Inflicted', 'Guns', 'lost']
    for line in out.splitlines()[2:5]:
        started, killed, wounded, prisoners, returned, final, inflicted = (int(x) for x in line.split()[-7:])
        assert started - killed - wounded - prisoners + returned == final
    battery = [line for line in out.splitlines() if line.startswith('Battery A')][0]
    assert int(battery.split()[-1]) > 0                                     # the battery's casualties show
    assert 'Final = Started - Killed - Wounded - Prisoners + Returned' in out
    assert 'Side summary' in out
    _, out, _ = run(capsys, 'show', files / 'state.json')
    assert 'finished' in out and 'Side summary' in out


@pytest.mark.parametrize('field, holder', [('auto', None), ('none', None), ('0', 0), ('1', 1), ('Confederate', 1)])
def test_finish_field_choices(files, capsys, field, holder):
    new(capsys, files)
    code, out, _ = run(capsys, 'finish', files / 'state.json', '--field', field, '--json', '-o', files / 'end.json')
    assert code == 0
    assert json.loads(out)['field_held_by'] == holder
    assert not read(files / 'state.json')['finished'] and read(files / 'end.json')['finished']


def test_finish_reports_nobody_holding_the_field(files, capsys):
    new(capsys, files)
    _, out, _ = run(capsys, 'finish', files / 'state.json')
    assert 'Field held by: nobody' in out


def test_run_plays_a_scenario_file(files, capsys):
    orders = ''.join('      ' + line + '\n' for line in ORDERS_YAML.splitlines())
    scenario = SETUP_YAML + 'rounds:\n  - duration: 90\n    orders:\n' + orders + '  - duration: 60\nfinish: true\n'
    (files / 'scenario.yaml').write_text(scenario, encoding='utf-8')
    code, out, _ = run(capsys, 'run', files / 'scenario.yaml', '-o', files / 'state.json')
    assert code == 0 and 'Skipped' not in out
    assert 'Round 1' in out and 'Round 2' in out and 'Field held by' in out
    assert read(files / 'state.json')['finished']
    _, out, _ = run(capsys, 'run', files / 'scenario.yaml', '--json', '--seed', 3)
    data = json.loads(out)
    assert set(data) == {'reports', 'result', 'state'} and data['state']['seed'] == 3


def test_show_summarises_a_state(files, capsys):
    new(capsys, files)
    code, out, _ = run(capsys, 'show', files / 'state.json')
    assert code == 0
    assert 'Test Ridge' in out and 'round 0' in out and 'Battery A' in out and 'guns' in out
    assert 'Order of battle' in out and 'Side summary' not in out


def test_unnamed_sides_and_battles_still_print(tmp_path, capsys):
    (tmp_path / 's.yaml').write_text(
        'units:\n  - {id: a, side: 0, size: 100, stats: 5/5/0/0}\n  - {id: b, side: 1, size: 100, stats: 5/5/0/0}\n',
        encoding='utf-8')
    run(capsys, 'new', tmp_path / 's.yaml', '-o', tmp_path / 'state.json')
    _, out, _ = run(capsys, 'show', tmp_path / 'state.json')
    assert 'Side 0' in out and 'Side 1' in out


# =============================================================================
# Errors are readable and exit with code 2
# =============================================================================

def test_setup_problems_are_listed(tmp_path, capsys):
    (tmp_path / 'bad.yaml').write_text('units:\n  - {id: a, side: 3, size: 100}\n', encoding='utf-8')
    code, _, err = run(capsys, 'new', tmp_path / 'bad.yaml', '-o', tmp_path / 'state.json')
    assert code == 2
    assert 'Problems in bad.yaml:' in err
    assert '  - Unit 1 (a): side must be 0 or 1; got 3.' in err
    assert not (tmp_path / 'state.json').exists()


def test_bad_orders_and_files_are_reported(files, capsys):
    new(capsys, files)
    (files / 'bad_orders.yaml').write_text('us_1mn: {target: nobody, mode: ranged}\n', encoding='utf-8')
    code, _, err = run(capsys, 'resolve', files / 'state.json', '--duration', 60, '--orders', files / 'bad_orders.yaml')
    assert code == 2 and "error: 'us_1mn' targets unknown unit 'nobody'." in err
    (files / 'list_orders.yaml').write_text('- us_1mn\n', encoding='utf-8')
    code, _, err = run(capsys, 'preview', files / 'state.json', '--orders', files / 'list_orders.yaml')
    assert code == 2 and 'error: list_orders.yaml must map unit ids to orders.' in err
    code, _, err = run(capsys, 'resolve', files / 'missing.json', '--duration', 60)
    assert code == 2 and 'error:' in err and 'missing.json' in err
    code, _, err = run(capsys, 'resolve', files / 'setup.yaml', '--duration', 60)
    assert code == 2 and 'error: setup.yaml is not a battle state file' in err
    code, _, err = run(capsys, 'finish', files / 'state.json', '--field', 'Rebels')
    assert code == 2
    assert "error: --field must be auto, none, 0, 1 or a side name (Union, Confederate); got 'Rebels'." in err
    run(capsys, 'finish', files / 'state.json')
    code, _, err = run(capsys, 'resolve', files / 'state.json', '--duration', 60)
    assert code == 2 and 'error: This battle is finished.' in err


def test_bad_scenario_is_reported(tmp_path, capsys):
    (tmp_path / 'sc.json').write_text('{"units": [}', encoding='utf-8')
    code, _, err = run(capsys, 'run', tmp_path / 'sc.json')
    assert code == 2 and 'sc.json is not valid JSON' in err


def test_usage_errors_exit_2(capsys):
    with pytest.raises(SystemExit) as info:
        main([])
    assert info.value.code == 2


def test_empty_orders_file_means_all_idle(files, capsys):
    new(capsys, files)
    (files / 'empty.yaml').write_text('# nobody moves\n', encoding='utf-8')
    code, out, _ = run(capsys, 'preview', files / 'state.json', '--orders', files / 'empty.yaml')
    assert code == 0 and 'No engagements' in out


def test_captured_guns_are_shown(files, capsys):
    new(capsys, files)
    (files / 'charge.yaml').write_text('us_1mn: {target: cs_bat, mode: melee}\n', encoding='utf-8')
    _, out, _ = run(capsys, 'resolve', files / 'state.json', '--duration', 120, '--orders', files / 'charge.yaml')
    assert 'guns lost' in out


def test_module_entry_point_imports():
    import imperial_generals.__main__ as entry
    assert entry.main is main


def test_example_scenario_runs(capsys):
    import os
    path = os.path.join(os.path.dirname(__file__), '../../scenarios/example_ridge.yaml')
    code, out, err = run(capsys, 'run', path)
    assert code == 0, err
    assert '1st Minnesota' in out and 'Field held by' in out
    assert 'broke at' in out and 'Skipped orders' in out          # the example shows breaks and skipped orders
    # order of battle before the rounds, side summary after
    assert out.index('Order of battle') < out.index('Round 1') < out.index('Side summary')
    assert 'Infantry' in out and 'Artillery' in out and 'Exchange ratio' in out and 'Prisoners taken' in out


def test_run_lists_skipped_orders(tmp_path, capsys):
    import yaml
    from test_api import ROUT
    (tmp_path / 'rout.yaml').write_text(yaml.safe_dump(ROUT), encoding='utf-8')
    _, out, _ = run(capsys, 'run', tmp_path / 'rout.yaml')
    assert 'Skipped orders: cs (cs is broken)' in out
    assert 'Skipped orders: us (target cs is wiped out)' in out


# =============================================================================
# Tuning runs (A10)
# =============================================================================

GRID_YAML = """\
name: Basic
seeds: 4
rounds: [60]
units:
  line: {type: inf, subtype: line, size: 1000, stats: 5/5/0/0}
  heavy_cav: {type: cav, subtype: heavy, size: 500, stats: 5/5/0/1, attack: melee, defend: melee}
"""


def test_batch_prints_the_spread_of_outcomes(files, capsys):
    code, out, _ = run(capsys, 'batch', files / 'setup.yaml', '--seeds', 6, '--workers', 1)
    assert code == 0
    assert 'Test Ridge: 6 seeds (0-5)' in out
    assert 'Field held: Union' in out and 'nobody' in out
    assert 'Lost for good' in out and 'Exchange ratio' in out and 'First break' in out
    assert '1st Minnesota' in out and 'Breaks' in out


def test_batch_writes_csv_and_json_and_takes_overrides(files, capsys):
    (files / 'over.yaml').write_text('combat: {ranged_kill_rate: 0.000000001}\n', encoding='utf-8')
    code, out, _ = run(capsys, 'batch', files / 'setup.yaml', '--seeds', 3, '--seed-start', 5, '--workers', 1,
                       '--params', files / 'over.yaml', '--csv', files / 'runs.csv',
                       '--units-csv', files / 'units.csv', '--json')
    assert code == 0
    summary = json.loads(out)
    assert summary['seeds'] == 3
    runs = (files / 'runs.csv').read_text(encoding='utf-8').splitlines()
    assert len(runs) == 4 and runs[1].startswith('5,')
    assert len((files / 'units.csv').read_text(encoding='utf-8').splitlines()) == 1 + 3 * 3


def test_batch_with_default_workers(files, capsys):
    code, out, _ = run(capsys, 'batch', files / 'setup.yaml', '--seeds', 2)
    assert code == 0 and '2 seeds' in out


def test_batch_problems(files, capsys):
    (files / 'over.yaml').write_text('combat: {nope: 1}\n', encoding='utf-8')
    code, _, err = run(capsys, 'batch', files / 'setup.yaml', '--params', files / 'over.yaml')
    assert code == 2 and "overrides: Unknown combat parameter(s): ['nope']." in err
    (files / 'list.yaml').write_text('- 1\n', encoding='utf-8')
    code, _, err = run(capsys, 'batch', files / 'setup.yaml', '--params', files / 'list.yaml')
    assert code == 2 and 'error: list.yaml must map parameter sections to overrides.' in err
    code, _, err = run(capsys, 'batch', files / 'setup.yaml', '--seeds', 0)
    assert code == 2 and 'seeds must be a positive whole number' in err


def test_matchups_prints_matrices(tmp_path, capsys):
    (tmp_path / 'grid.yaml').write_text(GRID_YAML, encoding='utf-8')
    code, out, _ = run(capsys, 'matchups', tmp_path / 'grid.yaml', '--workers', 1)
    assert code == 0
    assert 'Basic (ranged): 4 seeds per cell, rounds 60 min' in out
    assert 'Attacker advantage' in out and 'Defender breaks' in out and 'Exchange ratio' in out
    assert 'heavy_cav' in out


def test_matchups_csv_plot_json(tmp_path, capsys):
    (tmp_path / 'grid.yaml').write_text(GRID_YAML, encoding='utf-8')
    code, out, _ = run(capsys, 'matchups', tmp_path / 'grid.yaml', '--seeds', 2, '--workers', 1, '--mode', 'orders',
                       '--csv', tmp_path / 'cells.csv', '--plot', tmp_path / 'grid.png', '--json')
    assert code == 0
    cells = json.loads(out)
    assert len(cells) == 4 and cells[0]['attacker'] == 'line'
    assert len((tmp_path / 'cells.csv').read_text(encoding='utf-8').splitlines()) == 5
    assert (tmp_path / 'grid.png').exists()


def test_matchups_problems(tmp_path, capsys):
    (tmp_path / 'grid.yaml').write_text('rounds: [60]\nunits: {}\n', encoding='utf-8')
    code, _, err = run(capsys, 'matchups', tmp_path / 'grid.yaml')
    assert code == 2 and 'Problems in grid.yaml:' in err


def test_starter_matchup_grid_is_valid():
    import os
    from imperial_generals import tuning
    path = os.path.join(os.path.dirname(__file__), '../../scenarios/matchups_basic.yaml')
    grid = tuning.matchup_grid(load_setup_file(path), seeds=1)
    assert len(grid.keys) >= 6


def test_matchups_default_to_ranged_and_melee_facets(tmp_path, capsys):
    (tmp_path / 'grid.yaml').write_text(GRID_YAML, encoding='utf-8')
    code, out, _ = run(capsys, 'matchups', tmp_path / 'grid.yaml', '--seeds', 2, '--workers', 1,
                       '--csv', tmp_path / 'cells.csv', '--plot', tmp_path / 'grid.png')
    assert code == 0
    assert out.index('Basic (ranged)') < out.index('Basic (melee)')
    assert (tmp_path / 'grid_ranged.png').exists() and (tmp_path / 'grid_melee.png').exists()
    lines = (tmp_path / 'cells.csv').read_text(encoding='utf-8').splitlines()
    assert len(lines) == 1 + 2 * 4 and lines[0].startswith('mode,')


def test_matchups_single_facet_or_file_orders(tmp_path, capsys):
    (tmp_path / 'grid.yaml').write_text(GRID_YAML, encoding='utf-8')
    _, out, _ = run(capsys, 'matchups', tmp_path / 'grid.yaml', '--seeds', 2, '--workers', 1, '--mode', 'orders')
    assert 'Basic (orders from the file)' in out and '(melee)' not in out
    _, out, _ = run(capsys, 'matchups', tmp_path / 'grid.yaml', '--seeds', 2, '--workers', 1, '--mode', 'melee',
                    '--json')
    assert {c['mode'] for c in json.loads(out)} == {'melee'}
