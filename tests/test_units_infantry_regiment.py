import pytest
from imperial_generals.units.InfantryRegiment import InfantryRegiment

class TestInfantryRegiment:
    def test_init_and_inheritance(self):
        reg = InfantryRegiment(1200, '3/4/2/1', 'ln')
        assert isinstance(reg, InfantryRegiment)
        assert hasattr(reg, 'unit_type')
        assert reg.unit_type == 'inf'
        assert reg.size == 1200
        assert reg.stats == (3, 4, 2, 1)
        assert reg.law == 'ln'
        assert isinstance(reg.coef, float)

    def test_str_output(self):
        reg = InfantryRegiment(1000, '2/3/1/0', 'sq')
        s = str(reg)
        assert s.startswith('[type: inf]')
        assert 'Regiment:' in s
        assert '1000 men' in s
        assert 'xp=2' in s
        assert 'morale=3' in s
        assert 'weapon=1' in s
        assert 'melee=0' in s
        assert 'Law=sq' in s

    def test_repr_output(self):
        reg = InfantryRegiment(800, '1/2/3/4', 'ln')
        r = repr(reg)
        assert r.startswith('[type: inf]')
        assert 'Regiment(size=800, stats=(1, 2, 3, 4), law=' in r

    def test_print_type(self):
        reg = InfantryRegiment(500, '1/1/1/1', 'ln')
        assert reg.print_type() == 'inf'

    def test_update_size(self):
        reg = InfantryRegiment(1000, '2/2/2/2', 'ln')
        reg.update_size(750)
        assert reg.size == 750

    def test_update_stats_valid(self):
        reg = InfantryRegiment(1000, '2/2/2/2', 'ln')
        reg.update_stats('3/4/5/6')
        assert reg.stats == (3, 4, 5, 6)
        assert isinstance(reg.coef, float)

    @pytest.mark.parametrize("new_stats", [
        '1/2/3', '1/2/3/abc', '1/2/3/4/5', '1/2/3/', '////', ''
    ])
    def test_update_stats_invalid(self, new_stats):
        reg = InfantryRegiment(1000, '2/2/2/2', 'ln')
        with pytest.raises(ValueError):
            reg.update_stats(new_stats)

    def test_update_raw_morale_valid(self):
        reg = InfantryRegiment(1000, '2/2/2/2', 'ln')
        reg.update_raw_morale(25.0)
        assert reg.raw_morale == 25.0
        assert isinstance(reg.stats, tuple)

    @pytest.mark.parametrize("bad_type", [25, "25.0", None, [25.0]])
    def test_update_raw_morale_typeerror(self, bad_type):
        reg = InfantryRegiment(1000, '2/2/2/2', 'ln')
        with pytest.raises(TypeError):
            reg.update_raw_morale(bad_type)

    def test_update_raw_morale_stats_update(self):
        reg = InfantryRegiment(1000, '2/2/2/2', 'ln')
        old_stats = reg.stats
        reg.update_raw_morale(40.0)
        assert reg.stats[1] != old_stats[1]

    def test_main_example(self):
        reg = InfantryRegiment(1000, "4/4/0/0", "ln")
        reg.update_size(800)
        assert reg.size == 800
        reg.update_stats("5/6/1/0")
        assert reg.stats == (5, 6, 1, 0)
        reg.update_raw_morale(55.0)
        assert reg.raw_morale == 55.0
