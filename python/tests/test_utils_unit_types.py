import pytest
from imperial_generals.utils.unit_types import UNIT_SUBTYPES


def test_unit_subtypes_has_all_unit_types():
    assert 'inf' in UNIT_SUBTYPES
    assert 'cav' in UNIT_SUBTYPES
    assert 'art' in UNIT_SUBTYPES

def test_inf_subtypes():
    assert UNIT_SUBTYPES['inf'] == frozenset({'line', 'light', 'marine', 'pikes', 'irregulars'})

def test_cav_subtypes():
    assert UNIT_SUBTYPES['cav'] == frozenset({'light', 'heavy', 'dragoons'})

def test_art_subtypes():
    assert UNIT_SUBTYPES['art'] == frozenset({'battery', 'horse battery', 'siege battery'})
