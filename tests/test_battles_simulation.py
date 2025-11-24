import pytest
import numpy as np
import pandas as pd
from imperial_generals.units.Regiment import Regiment
from imperial_generals.battles.Simulation import Simulation

def make_regiments():
    reg1 = Regiment(1000, '4/5/2/1', 'sq')
    reg2 = Regiment(200, '3/6/1/0', 'sq')
    return reg1, reg2

class TestSimulation:
    def test_init_attributes(self):
        reg1, reg2 = make_regiments()
        sim = Simulation((reg1, reg2))
        assert isinstance(sim.forces, tuple)
        assert sim.forces[0] is reg1
        assert sim.forces[1] is reg2
        assert 'initial_size' in sim.casualties
        assert 'losses' in sim.casualties
        assert 'morale' in sim.casualties
        assert isinstance(sim.sim_output, pd.DataFrame)

    def test_str_and_repr(self):
        reg1, reg2 = make_regiments()
        sim = Simulation((reg1, reg2))
        s = str(sim)
        r = repr(sim)
        assert 'Simulation(' in s
        assert 'forces=' in r
        assert 'losses=' in s

    def test_build_lanch_diffeq(self):
        reg1, reg2 = make_regiments()
        sim = Simulation((reg1, reg2))
        sim.build_lanch_diffeq()
        assert sim.rate_funcs is not None
        assert callable(sim.rate_funcs[0])
        assert callable(sim.rate_funcs[1])

    def test_build_lanch_diffeq_invalid(self):
        reg1 = Regiment(1000, '4/5/2/1', 'sq')
        # Not a tuple
        with pytest.raises(ValueError):
            Simulation([reg1, reg1]).build_lanch_diffeq()
        # Wrong length
        with pytest.raises(ValueError):
            Simulation((reg1,)).build_lanch_diffeq()
        # Not Regiment
        with pytest.raises(ValueError):
            Simulation((reg1, object())).build_lanch_diffeq()

    def test_update_morale_losses(self):
        reg1, reg2 = make_regiments()
        sim = Simulation((reg1, reg2))
        sim.casualties['losses'] = np.array([10, 20])
        old_morale = sim.casualties['morale'].copy()
        sim.update_morale_losses(1.0)
        # Morale should change
        assert not np.array_equal(sim.casualties['morale'], old_morale)
        # Regiment morale should update
        assert reg1.raw_morale == sim.casualties['morale'][0]
        assert reg2.raw_morale == sim.casualties['morale'][1]

    def test_run_simulation_short(self):
        reg1, reg2 = make_regiments()
        sim = Simulation((reg1, reg2))
        sim.run_simulation(time=0.1)
        # Should have more than one row in output
        assert len(sim.sim_output) >= 1
        # Sizes and morale should be present
        assert 'size_1' in sim.sim_output.columns
        assert 'size_2' in sim.sim_output.columns
        assert 'morale_1' in sim.sim_output.columns
        assert 'morale_2' in sim.sim_output.columns

    def test_run_simulation_ends_on_zero(self):
        reg1 = Regiment(1, '4/5/2/1', 'ln')
        reg2 = Regiment(1, '3/6/1/0', 'ln')
        sim = Simulation((reg1, reg2))
        sim.run_simulation(time=10)
        # Should end early due to wipeout
        assert np.any(sim.sim_output['size_1'] == 0) or np.any(sim.sim_output['size_2'] == 0)

    def test_run_simulation_ends_on_low_morale(self):
        reg1 = Regiment(10, '4/5/2/1', 'ln')
        reg2 = Regiment(10, '3/1/1/0', 'sq')  # low morale
        sim = Simulation((reg1, reg2))
        sim.run_simulation(time=10)
        # Should end early due to morale
        assert np.any(sim.sim_output['morale_1'] <= 10) or np.any(sim.sim_output['morale_2'] <= 10)
