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
        assert "Infantry Regiment" in s
        assert "size=2000" in s
        assert "stats=(3, 4, 1, 0)" in s
        assert "ln" in s

    def test_repr_output(self):
        reg = Regiment(1200, '1/2/3/4', 'sq')
        r = repr(reg)
        assert "InfReg" in r
        assert "size=1200" in r
        assert "stats=(1, 2, 3, 4)" in r
        assert "sq" in r

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

    def test_attribute_types(self):
        reg = Regiment(500, '1/2/3/4', 'sq')
        assert isinstance(reg.size, int)
        assert isinstance(reg.stats, tuple)
        assert all(isinstance(x, int) for x in reg.stats)
        assert isinstance(reg.coef, float)
        assert isinstance(reg.law, str)
