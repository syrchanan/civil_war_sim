"""
Tests for the admin config loader.

Verifies that simulation.yaml is well-formed and that ConfigLoader surfaces
all required sections and values correctly.
"""

import pytest
from pathlib import Path
from imperial_generals.config import ConfigLoader

CONFIG_PATH = Path(__file__).parent.parent.parent / 'config' / 'simulation.yaml'

EXPECTED_WEATHER_TYPES = ['clear', 'overcast', 'light_rain', 'heavy_rain', 'fog', 'storm', 'snow']
EXPECTED_SEASONS = ['spring', 'summer', 'autumn', 'winter']
EXPECTED_TERRAIN_PRESETS = ['flat', 'hills', 'mountains', 'coastal', 'forest', 'badlands']
EXPECTED_BIOME_PRESETS = ['mixed_battlefield', 'mountainous_region', 'coastal_landing', 'open_plains']
EXPECTED_TERRAIN_TYPES = ['open', 'forest', 'hill', 'rough', 'mountain', 'river', 'lake']
ELEVATION_PRESET_FIELDS = ['octaves', 'persistence', 'lacunarity', 'scale', 'base_elevation', 'elevation_range', 'exponent']
WEAPON_CODES = ['-2', '-1', '0', '1', '2']


# =============================================================================
# Loader construction
# =============================================================================

class TestConfigLoaderConstruction:
    def test_loads_from_explicit_path(self):
        loader = ConfigLoader(CONFIG_PATH)
        assert loader is not None

    def test_loads_from_default_path(self):
        loader = ConfigLoader()
        assert loader is not None

    def test_invalid_path_raises_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            ConfigLoader('/nonexistent/path/config.yaml')

    def test_top_level_sections_present(self):
        loader = ConfigLoader(CONFIG_PATH)
        for section in ['combat', 'morale', 'map', 'cover', 'weather', 'movement', 'visualization']:
            assert section in loader, f"Missing top-level section: {section}"


# =============================================================================
# Subscript and get access
# =============================================================================

class TestConfigLoaderAccess:
    def test_subscript_returns_section(self):
        loader = ConfigLoader(CONFIG_PATH)
        assert isinstance(loader['combat'], dict)

    def test_missing_section_raises_key_error(self):
        loader = ConfigLoader(CONFIG_PATH)
        with pytest.raises(KeyError):
            _ = loader['nonexistent_section']

    def test_get_returns_nested_value(self):
        loader = ConfigLoader(CONFIG_PATH)
        val = loader.get('combat', 'xp_boost_per_level')
        assert isinstance(val, float)
        assert val == 0.04

    def test_get_missing_key_raises_key_error(self):
        loader = ConfigLoader(CONFIG_PATH)
        with pytest.raises(KeyError):
            loader.get('combat', 'nonexistent_key')


# =============================================================================
# Combat section
# =============================================================================

class TestCombatSection:
    def test_weapon_multipliers_all_codes_present(self):
        loader = ConfigLoader(CONFIG_PATH)
        wm = loader['combat']['weapon_multipliers']
        for code in WEAPON_CODES:
            assert code in wm, f"Missing weapon code: {code}"

    def test_weapon_multipliers_are_positive_floats(self):
        loader = ConfigLoader(CONFIG_PATH)
        for code, val in loader['combat']['weapon_multipliers'].items():
            assert isinstance(val, (int, float)), f"Weapon multiplier {code} is not numeric"
            assert val > 0, f"Weapon multiplier {code} must be positive"

    def test_weapon_multipliers_increasing(self):
        loader = ConfigLoader(CONFIG_PATH)
        wm = loader['combat']['weapon_multipliers']
        vals = [wm[c] for c in WEAPON_CODES]
        assert vals == sorted(vals), "Weapon multipliers should be in ascending order by code"

    def test_xp_boost_per_level(self):
        loader = ConfigLoader(CONFIG_PATH)
        val = loader['combat']['xp_boost_per_level']
        assert 0 < val < 1

    def test_morale_boost_per_level(self):
        loader = ConfigLoader(CONFIG_PATH)
        val = loader['combat']['morale_boost_per_level']
        assert 0 < val < 1

    def test_melee_penalty_factor(self):
        loader = ConfigLoader(CONFIG_PATH)
        val = loader['combat']['melee_penalty_factor']
        assert 0 < val < 1


# =============================================================================
# Morale section
# =============================================================================

class TestMoraleSection:
    def test_required_keys_present(self):
        loader = ConfigLoader(CONFIG_PATH)
        morale = loader['morale']
        for key in ['min_raw', 'max_raw', 'raw_scale_factor',
                    'loss_constant_a', 'gain_constant_b',
                    'loss_constant_c', 'gain_constant_d']:
            assert key in morale, f"Missing morale key: {key}"

    def test_raw_bounds_valid(self):
        loader = ConfigLoader(CONFIG_PATH)
        morale = loader['morale']
        assert morale['min_raw'] < morale['max_raw']
        assert morale['min_raw'] > 0

    def test_constants_are_small_positives(self):
        loader = ConfigLoader(CONFIG_PATH)
        morale = loader['morale']
        for key in ['loss_constant_a', 'gain_constant_b', 'loss_constant_c', 'gain_constant_d']:
            assert morale[key] > 0, f"{key} must be positive"
            assert morale[key] < 1, f"{key} should be a small fractional value"


# =============================================================================
# Map section — defaults
# =============================================================================

class TestMapDefaults:
    def test_default_keys_present(self):
        loader = ConfigLoader(CONFIG_PATH)
        defaults = loader['map']['defaults']
        for key in ['width', 'height', 'min_distance', 'seed']:
            assert key in defaults, f"Missing map default: {key}"

    def test_default_dimensions_positive(self):
        loader = ConfigLoader(CONFIG_PATH)
        defaults = loader['map']['defaults']
        assert defaults['width'] > 0
        assert defaults['height'] > 0
        assert defaults['min_distance'] > 0


# =============================================================================
# Map section — terrain presets
# =============================================================================

class TestTerrainPresets:
    def test_all_presets_present(self):
        loader = ConfigLoader(CONFIG_PATH)
        presets = loader['map']['terrain_presets']
        for name in EXPECTED_TERRAIN_PRESETS:
            assert name in presets, f"Missing terrain preset: {name}"

    def test_preset_has_all_fields(self):
        loader = ConfigLoader(CONFIG_PATH)
        for name, preset in loader['map']['terrain_presets'].items():
            for field in ELEVATION_PRESET_FIELDS:
                assert field in preset, f"Terrain preset '{name}' missing field: {field}"

    def test_preset_values_in_valid_ranges(self):
        loader = ConfigLoader(CONFIG_PATH)
        for name, preset in loader['map']['terrain_presets'].items():
            assert 1 <= preset['octaves'] <= 8, f"'{name}' octaves out of range"
            assert 0.0 <= preset['persistence'] <= 1.0, f"'{name}' persistence out of range"
            assert 1.5 <= preset['lacunarity'] <= 4.0, f"'{name}' lacunarity out of range"
            assert preset['scale'] > 0, f"'{name}' scale must be positive"
            assert preset['elevation_range'] >= 0, f"'{name}' elevation_range must be non-negative"
            assert preset['exponent'] > 0, f"'{name}' exponent must be positive"


# =============================================================================
# Map section — biome presets
# =============================================================================

class TestBiomePresets:
    def test_all_presets_present(self):
        loader = ConfigLoader(CONFIG_PATH)
        presets = loader['map']['biome_presets']
        for name in EXPECTED_BIOME_PRESETS:
            assert name in presets, f"Missing biome preset: {name}"

    def test_preset_has_zone_scale_and_zones(self):
        loader = ConfigLoader(CONFIG_PATH)
        for name, preset in loader['map']['biome_presets'].items():
            assert 'zone_scale' in preset, f"Biome preset '{name}' missing zone_scale"
            assert 'zones' in preset, f"Biome preset '{name}' missing zones"
            assert len(preset['zones']) > 0, f"Biome preset '{name}' has no zones"

    def test_zone_percentages_sum_to_one(self):
        loader = ConfigLoader(CONFIG_PATH)
        for name, preset in loader['map']['biome_presets'].items():
            total = sum(z['percentage'] for z in preset['zones'])
            assert abs(total - 1.0) < 0.01, \
                f"Biome preset '{name}' zone percentages sum to {total:.3f}, expected 1.0"

    def test_zones_reference_valid_terrain_presets(self):
        loader = ConfigLoader(CONFIG_PATH)
        valid_presets = set(loader['map']['terrain_presets'].keys())
        for name, preset in loader['map']['biome_presets'].items():
            for zone in preset['zones']:
                assert zone['terrain_preset'] in valid_presets, \
                    f"Zone '{zone['name']}' in '{name}' references unknown preset '{zone['terrain_preset']}'"

    def test_zone_cover_values_in_range(self):
        loader = ConfigLoader(CONFIG_PATH)
        for name, preset in loader['map']['biome_presets'].items():
            for zone in preset['zones']:
                assert 0.0 <= zone['cover_value'] <= 1.0, \
                    f"Zone '{zone['name']}' in '{name}' cover_value out of range"


# =============================================================================
# Cover section
# =============================================================================

class TestCoverSection:
    def test_required_keys_present(self):
        loader = ConfigLoader(CONFIG_PATH)
        cover = loader['cover']
        for key in ['forest_penalty', 'rough_penalty', 'fence_on_cell_penalty', 'fence_on_ray_penalty']:
            assert key in cover, f"Missing cover key: {key}"

    def test_penalties_in_valid_range(self):
        loader = ConfigLoader(CONFIG_PATH)
        cover = loader['cover']
        for key, val in cover.items():
            assert 0.0 <= val <= 1.0, f"Cover penalty '{key}' = {val} is outside [0, 1]"


# =============================================================================
# Weather section
# =============================================================================

class TestWeatherSection:
    def test_visibility_modifiers_all_types_present(self):
        loader = ConfigLoader(CONFIG_PATH)
        vis = loader['weather']['visibility_modifiers']
        for weather in EXPECTED_WEATHER_TYPES:
            assert weather in vis, f"Missing visibility modifier for: {weather}"

    def test_visibility_modifiers_in_range(self):
        loader = ConfigLoader(CONFIG_PATH)
        for weather, val in loader['weather']['visibility_modifiers'].items():
            assert 0.0 < val <= 1.0, f"Visibility modifier for '{weather}' = {val} out of range"

    def test_clear_has_max_visibility(self):
        loader = ConfigLoader(CONFIG_PATH)
        vis = loader['weather']['visibility_modifiers']
        assert vis['clear'] == 1.0

    def test_season_weights_all_seasons_present(self):
        loader = ConfigLoader(CONFIG_PATH)
        weights = loader['weather']['season_weights']
        for season in EXPECTED_SEASONS:
            assert season in weights, f"Missing season weights for: {season}"

    def test_season_weights_all_weather_types_present(self):
        loader = ConfigLoader(CONFIG_PATH)
        for season, weights in loader['weather']['season_weights'].items():
            for weather in EXPECTED_WEATHER_TYPES:
                assert weather in weights, f"Season '{season}' missing weight for: {weather}"

    def test_season_weights_sum_to_one(self):
        loader = ConfigLoader(CONFIG_PATH)
        for season, weights in loader['weather']['season_weights'].items():
            total = sum(weights.values())
            assert abs(total - 1.0) < 0.001, \
                f"Season '{season}' weights sum to {total:.4f}, expected 1.0"

    def test_season_weights_non_negative(self):
        loader = ConfigLoader(CONFIG_PATH)
        for season, weights in loader['weather']['season_weights'].items():
            for weather, val in weights.items():
                assert val >= 0.0, f"Season '{season}' weight for '{weather}' is negative"


# =============================================================================
# Movement section
# =============================================================================

class TestMovementSection:
    def test_terrain_modifiers_all_types_present(self):
        loader = ConfigLoader(CONFIG_PATH)
        movement = loader['movement']['terrain_modifiers']
        for terrain in ['open', 'forest', 'hill', 'rough', 'road', 'river', 'lake']:
            assert terrain in movement, f"Missing movement modifier for: {terrain}"

    def test_modifiers_non_negative(self):
        loader = ConfigLoader(CONFIG_PATH)
        for terrain, val in loader['movement']['terrain_modifiers'].items():
            assert val >= 0.0, f"Movement modifier for '{terrain}' is negative"

    def test_lake_is_impassable(self):
        loader = ConfigLoader(CONFIG_PATH)
        assert loader['movement']['terrain_modifiers']['lake'] == 0.0

    def test_road_faster_than_open(self):
        loader = ConfigLoader(CONFIG_PATH)
        mods = loader['movement']['terrain_modifiers']
        assert mods['road'] > mods['open']

    def test_open_is_baseline(self):
        loader = ConfigLoader(CONFIG_PATH)
        assert loader['movement']['terrain_modifiers']['open'] == 1.0


# =============================================================================
# Visualization section
# =============================================================================

class TestVisualizationSection:
    def test_terrain_colors_all_types_present(self):
        loader = ConfigLoader(CONFIG_PATH)
        colors = loader['visualization']['terrain_colors']
        for terrain in EXPECTED_TERRAIN_TYPES:
            assert terrain in colors, f"Missing color for terrain: {terrain}"

    def test_colors_are_hex_strings(self):
        loader = ConfigLoader(CONFIG_PATH)
        for terrain, color in loader['visualization']['terrain_colors'].items():
            assert isinstance(color, str), f"Color for '{terrain}' is not a string"
            assert color.startswith('#'), f"Color for '{terrain}' is not a hex string: {color}"
            assert len(color) == 7, f"Color for '{terrain}' is not 6-digit hex: {color}"


def test_repr():
    loader = ConfigLoader(CONFIG_PATH)
    r = repr(loader)
    assert 'ConfigLoader' in r
    assert 'combat' in r
