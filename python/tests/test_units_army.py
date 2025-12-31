import pytest
from imperial_generals.units.Army import Army
from imperial_generals.units.Regiment import Regiment

class TestArmy:
    def test_init(self):
        army = Army("Union")
        assert army.faction == "Union"
        assert isinstance(army.forces, dict)
        assert len(army.forces) == 0

    def test_add_regiment_valid(self):
        army = Army("Confederate")
        reg = Regiment(1000, '2/3/1/0', 'ln')
        army.add_regiment("1st VA", reg)
        assert "1st VA" in army.forces
        assert army.forces["1st VA"] is reg

    def test_add_regiment_invalid_type(self):
        army = Army("Union")
        with pytest.raises(TypeError):
            army.add_regiment("bad", "not_a_regiment")
        with pytest.raises(TypeError):
            army.add_regiment("bad", 123)
        with pytest.raises(TypeError):
            army.add_regiment("bad", None)

    def test_str_output(self):
        army = Army("Union")
        reg = Regiment(800, '1/1/1/1', 'sq')
        army.add_regiment("test", reg)
        s = str(army)
        assert "Army(faction=Union" in s
        assert "test" in s

    def test_repr_output(self):
        army = Army("Union")
        reg = Regiment(900, '2/2/2/2', 'ln')
        army.add_regiment("test", reg)
        r = repr(army)
        assert "Army(faction='Union'" in r
        assert "test" in r
        assert "Regiment" in r or "InfReg" in r

    def test_multiple_regiments(self):
        army = Army("Union")
        reg1 = Regiment(1000, '1/2/3/4', 'ln')
        reg2 = Regiment(1200, '4/3/2/1', 'sq')
        army.add_regiment("A", reg1)
        army.add_regiment("B", reg2)
        assert len(army.forces) == 2
        assert army.forces["A"] is reg1
        assert army.forces["B"] is reg2

    def test_overwrite_regiment(self):
        army = Army("Union")
        reg1 = Regiment(1000, '1/2/3/4', 'ln')
        reg2 = Regiment(1200, '4/3/2/1', 'sq')
        army.add_regiment("A", reg1)
        army.add_regiment("A", reg2)
        assert len(army.forces) == 1
        assert army.forces["A"] is reg2
