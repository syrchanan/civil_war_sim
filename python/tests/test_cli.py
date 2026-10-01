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
    assert code == 0
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
