import pytest
from imperial_generals.units.Regiment import Regiment

class TestRegiment:
    def test_valid_init_ln(self):
        reg = Regiment(3000, '4/5/2/1', 'ln')
        assert reg.size == 3000
        assert reg.stats == (4, 5, 2, 1)
        assert reg.law == 'ln'
        assert isinstance(reg.coef, float)

    def test_valid_init_sq(self):
        reg = Regiment(1500, '2/3/1/0', 'sq')
        assert reg.size == 1500
        assert reg.stats == (2, 3, 1, 0)
        assert reg.law == 'sq'
        assert isinstance(reg.coef, float)

    def test_str_output(self):
        reg = Regiment(2000, '3/4/1/0', 'ln')
        s = str(reg)
        assert "Regiment:" in s
        assert "2000 men" in s
        assert "xp=3" in s
        assert "morale=4" in s
        assert "weapon=1" in s
        assert "melee=0" in s
        assert "Raw Morale=40.0" in s
        assert "Coef=" in s
        assert "Law=ln" in s

    def test_repr_output(self):
        reg = Regiment(1200, '1/2/3/4', 'sq')
        r = repr(reg)
        assert r.startswith("Regiment(")
        assert "size=1200" in r
        assert "stats=(1, 2, 3, 4)" in r
        assert "law='sq'" in r

    @pytest.mark.parametrize("law", ["invalid", "", None])
    def test_invalid_law(self, law):
        with pytest.raises(ValueError):
            Regiment(1000, '1/2/3/4', law)

    @pytest.mark.parametrize("stats", [
        '1/2/3',           # too few
        '1/2/3/abc',       # non-integer
        '1/2/3/4/5',       # too many
        '1/2/3/',          # trailing slash
        '////',            # all empty
        '',                # empty string
    ])
    def test_invalid_stats_format(self, stats):
        with pytest.raises(ValueError):
            Regiment(1000, stats, 'ln')

    def test_coef_calculation(self):
        reg = Regiment(1000, '4/4/4/4', 'ln')
        assert reg.coef > 0
        reg2 = Regiment(1000, '0/0/0/0', 'ln')
        assert reg2.coef >= 0
        assert reg2.coef < reg.coef

    def test_attribute_types(self):
        reg = Regiment(500, '1/2/3/4', 'sq')
        assert isinstance(reg.size, int)
        assert isinstance(reg.stats, tuple)
        assert all(isinstance(x, int) for x in reg.stats)
        assert isinstance(reg.coef, float)
        assert isinstance(reg.law, str)

    def test_update_size(self):
        reg = Regiment(1000, '2/2/2/2', 'ln')
        reg.update_size(800)
        assert reg.size == 800

    def test_update_stats_valid(self):
        reg = Regiment(1000, '2/2/2/2', 'ln')
        reg.update_stats('3/4/5/6')
        assert reg.stats == (3, 4, 5, 6)
        assert isinstance(reg.coef, float)

    @pytest.mark.parametrize("new_stats", [
        '1/2/3', '1/2/3/abc', '1/2/3/4/5', '1/2/3/', '////', ''
    ])
    def test_update_stats_invalid(self, new_stats):
        reg = Regiment(1000, '2/2/2/2', 'ln')
        with pytest.raises(ValueError):
            reg.update_stats(new_stats)

    def test_update_raw_morale_valid(self):
        reg = Regiment(1000, '2/2/2/2', 'ln')
        reg.update_raw_morale(25.0)
        # Should update raw_morale and stats[1] (morale)
        assert reg.raw_morale == 25.0
        assert isinstance(reg.stats, tuple)

    @pytest.mark.parametrize("bad_type", [25, "25.0", None, [25.0]])
    def test_update_raw_morale_typeerror(self, bad_type):
        reg = Regiment(1000, '2/2/2/2', 'ln')
        with pytest.raises(TypeError):
            reg.update_raw_morale(bad_type)

    def test_update_raw_morale_stats_update(self):
        reg = Regiment(1000, '2/2/2/2', 'ln')
        old_stats = reg.stats
        reg.update_raw_morale(40.0)
        # Should update morale stat to closest value
        assert reg.stats[1] != old_stats[1]

    def test_main_example(self):
        reg = Regiment(1000, "4/4/0/0", "ln")
        reg.update_size(800)
        assert reg.size == 800
        reg.update_stats("5/6/1/0")
        assert reg.stats == (5, 6, 1, 0)
        reg.update_raw_morale(55.0)
        assert reg.raw_morale == 55.0
