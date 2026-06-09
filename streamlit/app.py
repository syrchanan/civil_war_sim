import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "python"))

import io
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.cm as cm
from matplotlib.patches import Patch
import streamlit as st

from imperial_generals.config import get_config
from imperial_generals.map.generator import MapGenerator, MapConfig
from imperial_generals.map.biome import BiomePresets
from imperial_generals.units import Regiment
from imperial_generals.battles.Simulation import Simulation

# ---------------------------------------------------------------------------
# Page config & CSS
# ---------------------------------------------------------------------------

st.set_page_config(page_title="Imperial Generals", layout="wide",
                   initial_sidebar_state="collapsed")

st.markdown("""
<style>
  /* Clear Streamlit's fixed toolbar (~3.5rem) then keep sides/bottom tight */
  .block-container { padding: 3.5rem 1.5rem 1rem 1.5rem !important; }

  /* Compact headings */
  h1 { font-size: 1.3rem !important; margin-bottom: 0.4rem !important; }
  h2 { font-size: 1.05rem !important; margin-bottom: 0.25rem !important; }
  h3 { font-size: 0.9rem !important; margin-bottom: 0.15rem !important; }

  /* Smaller widget labels */
  .stSelectbox label, .stNumberInput label,
  .stSlider label, .stCheckbox label { font-size: 0.78rem !important; }

  /* Tighter column gaps */
  [data-testid="column"] { padding: 0 0.4rem !important; }

  /* Slim dividers */
  hr { margin: 0.5rem 0 !important; }

  /* Compact metric cards */
  [data-testid="metric-container"] { padding: 0.4rem 0.6rem !important; }
  [data-testid="stMetricLabel"]  { font-size: 0.75rem !important; }
  [data-testid="stMetricValue"]  { font-size: 1.1rem !important; }

  /* Nav button row */
  .nav-row { display: flex; gap: 0.4rem; margin-bottom: 0.6rem; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------

if "page" not in st.session_state:
    st.session_state.page = "Setup"
if "results" not in st.session_state:
    st.session_state.results = None

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BIOME_PRESETS = {
    "Mixed Battlefield":  "mixed_battlefield",
    "Open Plains":        "open_plains",
    "Mountainous Region": "mountainous_region",
    "Coastal Landing":    "coastal_landing",
    "Cliffs & Valleys":   "cliffs_and_valleys",
}

_VIEW_KEYS = {
    "Terrain":   "terrain_type",
    "Elevation": "elevation",
    "Cover":     "cover_value",
}

_FEATURE_TERRAIN = {"river"}

# ---------------------------------------------------------------------------
# Header + nav
# ---------------------------------------------------------------------------

title_col, nav_col = st.columns([6, 1])
title_col.markdown("## Imperial Generals — Battle Simulator")

with nav_col:
    nc1, nc2 = st.columns(2)
    if nc1.button("Setup", use_container_width=True,
                  type="primary" if st.session_state.page == "Setup" else "secondary"):
        st.session_state.page = "Setup"
        st.rerun()
    if nc2.button("Results", use_container_width=True,
                  type="primary" if st.session_state.page == "Results" else "secondary",
                  disabled=st.session_state.results is None):
        st.session_state.page = "Results"
        st.rerun()

st.divider()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def render_map(result, view: str = "terrain_type") -> io.BytesIO:
    terrain_colors = get_config()["visualization"]["terrain_colors"]
    cells = result.cells

    fig, ax = plt.subplots(figsize=(5, 5))

    if view == "terrain_type":
        for cell in cells:
            color = terrain_colors.get(cell.terrain_type, "#aaaaaa")
            x, y = cell.polygon.exterior.xy
            ax.fill(x, y, alpha=0.7, edgecolor="black", linewidth=0.3,
                    facecolor=color, zorder=2)
        for cell in cells:
            if cell.terrain_type in _FEATURE_TERRAIN:
                color = terrain_colors.get(cell.terrain_type, "#aaaaaa")
                x, y = cell.polygon.exterior.xy
                ax.fill(x, y, alpha=1.0, edgecolor=color, linewidth=1.0,
                        facecolor=color, zorder=3)
        seen = {}
        for cell in cells:
            if cell.terrain_type not in seen:
                seen[cell.terrain_type] = terrain_colors.get(cell.terrain_type, "#aaaaaa")
        handles = [Patch(facecolor=c, label=t) for t, c in seen.items()]
        ax.legend(handles=handles, title="Terrain", loc="upper right", fontsize=7,
                  title_fontsize=7)
        ax.set_title("Terrain Type", fontsize=10, fontweight="bold")

    elif view == "elevation":
        values = [cell.elevation for cell in cells]
        lo, hi = min(values), max(values)
        norms = [(v - lo) / (hi - lo) if hi > lo else 0.5 for v in values]
        cmap = cm.terrain
        for cell, nv in zip(cells, norms):
            x, y = cell.polygon.exterior.xy
            ax.fill(x, y, alpha=0.8, edgecolor="black", linewidth=0.3, facecolor=cmap(nv))
        sm = plt.cm.ScalarMappable(cmap=cmap, norm=plt.Normalize(vmin=lo, vmax=hi))
        sm.set_array([])
        plt.colorbar(sm, ax=ax, label="Elevation", shrink=0.8)
        ax.set_title("Elevation", fontsize=10, fontweight="bold")

    elif view == "cover_value":
        values = [cell.cover_value for cell in cells]
        lo, hi = min(values), max(values)
        norms = [(v - lo) / (hi - lo) if hi > lo else 0.5 for v in values]
        cmap = cm.YlOrRd
        for cell, nv in zip(cells, norms):
            x, y = cell.polygon.exterior.xy
            ax.fill(x, y, alpha=0.8, edgecolor="black", linewidth=0.3, facecolor=cmap(nv))
        sm = plt.cm.ScalarMappable(cmap=cmap, norm=plt.Normalize(vmin=lo, vmax=hi))
        sm.set_array([])
        plt.colorbar(sm, ax=ax, label="Cover", shrink=0.8)
        ax.set_title("Cover Value", fontsize=10, fontweight="bold")

    ax.set_xlim(0, result.voronoi.width)
    ax.set_ylim(0, result.voronoi.height)
    ax.set_aspect("equal")
    ax.tick_params(labelsize=7)
    plt.tight_layout(pad=0.5)

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=110)
    plt.close(fig)
    buf.seek(0)
    return buf


def plot_battle(df, label1: str, label2: str) -> bytes:
    """Render size + morale as a single two-subplot figure."""
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(5, 3.6), sharex=True)

    ax1.plot(df["time"], df["size_1"],   label=label1, color="#2271B3", linewidth=1.2)
    ax1.plot(df["time"], df["size_2"],   label=label2, color="#E66100", linewidth=1.2)
    ax1.set_ylabel("Troops", fontsize=8)
    ax1.set_title("Size & Morale over time", fontsize=9, fontweight="bold")
    ax1.tick_params(labelsize=7)
    ax1.legend(fontsize=6)

    ax2.plot(df["time"], df["morale_1"], label=label1, color="#2271B3", linewidth=1.2)
    ax2.plot(df["time"], df["morale_2"], label=label2, color="#E66100", linewidth=1.2)
    ax2.set_xlabel("Time", fontsize=8)
    ax2.set_ylabel("Morale", fontsize=8)
    ax2.tick_params(labelsize=7)

    plt.tight_layout(pad=0.5)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=110)
    plt.close(fig)
    return buf.getvalue()


def stat_inputs(prefix: str, defaults: tuple) -> tuple:
    """Render four compact stat number inputs; return (xp, morale, weapon, melee)."""
    xp_d, mo_d, wp_d, ml_d = defaults
    st.caption("Stats — XP / Morale / Weapon / Melee")
    c1, c2, c3, c4 = st.columns(4)
    xp = c1.number_input("XP",     0, 10, xp_d, key=f"{prefix}_xp")
    mo = c2.number_input("Morale", 0, 10, mo_d, key=f"{prefix}_mo")
    wp = c3.number_input("Weapon", 0, 10, wp_d, key=f"{prefix}_wp")
    ml = c4.number_input("Melee",  0,  1, ml_d, key=f"{prefix}_ml",
                          help="1 = melee-only unit")
    return int(xp), int(mo), int(wp), int(ml)


# ---------------------------------------------------------------------------
# SETUP PAGE
# ---------------------------------------------------------------------------

if st.session_state.page == "Setup":
    left, right = st.columns([4, 6])

    # --- Map config + run controls ---
    with left:
        st.subheader("Map")
        r1c1, r1c2 = st.columns(2)
        biome_label   = r1c1.selectbox("Preset", list(BIOME_PRESETS.keys()))
        seed          = int(r1c2.number_input("Seed", 0, 99999, 42, 1))
        r2c1, r2c2, r2c3 = st.columns(3)
        width         = int(r2c1.number_input("Width",    50, 500, 200, 10))
        height        = int(r2c2.number_input("Height",   50, 500, 200, 10))
        min_distance  = int(r2c3.number_input("Min dist",  1,  20,   5,  1))
        num_rivers    = st.slider("Rivers", 0, 5, 2)

        st.divider()
        st.subheader("Simulation")
        sim_time = int(st.number_input("Turns", min_value=1, max_value=10000,
                                        value=1, step=1,
                                        help="1 turn = 1 battle tick"))
        run = st.button("Run Battle", type="primary", use_container_width=True)

    # --- Army builder ---
    with right:
        st.subheader("Army Builder")
        s1col, s2col = st.columns(2)

        with s1col:
            st.markdown("**:blue[Side 1]**")
            s1_size  = int(st.number_input("Size",  1, 50000, 4000, 100, key="s1_size"))
            s1_front = int(st.number_input("Front", 1, 50000,  500,  50, key="s1_front",
                                            help="Men on the firing line"))
            s1_mode  = st.selectbox("Mode", ["Ranged", "Melee"], key="s1_mode")
            s1_stats = stat_inputs("s1", (4, 4, 0, 0))

        with s2col:
            st.markdown("**:orange[Side 2]**")
            s2_size  = int(st.number_input("Size",  1, 50000, 3500, 100, key="s2_size"))
            s2_front = int(st.number_input("Front", 1, 50000,  500,  50, key="s2_front",
                                            help="Men on the firing line"))
            s2_mode  = st.selectbox("Mode", ["Ranged", "Melee"], key="s2_mode")
            s2_stats = stat_inputs("s2", (4, 6, 1, 0))

    # --- Run ---
    if run:
        with st.spinner("Generating map and running simulation…"):
            try:
                biome_cfg = BiomePresets._from_config(BIOME_PRESETS[biome_label], seed)
                cfg = MapConfig(
                    width=width, height=height, min_distance=min_distance,
                    biome_config=biome_cfg, num_rivers=num_rivers,
                )
                map_result = MapGenerator(cfg).generate_map()

                stats_str1 = "/".join(str(v) for v in s1_stats)
                stats_str2 = "/".join(str(v) for v in s2_stats)

                reg1 = Regiment(s1_size, stats_str1, front_size=min(s1_front, s1_size))
                reg1.set_combat_mode(s1_mode.lower())
                reg2 = Regiment(s2_size, stats_str2, front_size=min(s2_front, s2_size))
                reg2.set_combat_mode(s2_mode.lower())

                sim = Simulation((reg1, reg2))
                sim.run_simulation(time=sim_time)

                label1 = f"Side 1 ({s1_size:,}; {stats_str1})"
                label2 = f"Side 2 ({s2_size:,}; {stats_str2})"

                # Pre-render everything so Results page has zero recompute
                map_bufs = {
                    view_key: render_map(map_result, view=view_key).getvalue()
                    for view_key in _VIEW_KEYS.values()
                }
                plot_buf = plot_battle(sim.sim_output, label1, label2)

                st.session_state.results = {
                    "map_bufs":  map_bufs,
                    "plot_buf":  plot_buf,
                    "sim_output": sim.sim_output,
                    "label1":    label1,
                    "label2":    label2,
                }
                st.session_state.page = "Results"
                st.rerun()

            except Exception as ex:
                st.error(f"Error: {ex}")


# ---------------------------------------------------------------------------
# RESULTS PAGE
# ---------------------------------------------------------------------------

elif st.session_state.page == "Results":
    r          = st.session_state.results
    map_bufs   = r["map_bufs"]
    plot_buf   = r["plot_buf"]
    sim_output = r["sim_output"]
    label1     = r["label1"]
    label2     = r["label2"]

    map_col, data_col = st.columns([55, 45])

    # --- Map ---
    with map_col:
        map_view = st.radio("Layer", list(_VIEW_KEYS.keys()), horizontal=True)
        st.image(map_bufs[_VIEW_KEYS[map_view]], use_container_width=True)

    # --- Outcome + plots ---
    with data_col:
        final  = sim_output.iloc[-1]
        final1 = int(final["size_1"])
        final2 = int(final["size_2"])

        if final1 == 0 and final2 == 0:
            outcome = "Draw"
        elif final1 == 0:
            outcome = "Side 2 wins"
        elif final2 == 0:
            outcome = "Side 1 wins"
        else:
            outcome = "No decision"

        mc1, mc2, mc3 = st.columns(3)
        mc1.metric("Result",  outcome)
        mc2.metric("Side 1",  f"{final1:,}")
        mc3.metric("Side 2",  f"{final2:,}")

        st.image(plot_buf, use_container_width=True)
