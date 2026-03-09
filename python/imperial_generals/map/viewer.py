"""
Multi-view interactive map visualizer.

Views (toggled with ←/→):
  elevation     — continuous heatmap (matplotlib terrain colormap)
  terrain_type  — categorical, hex colours from visualization.yaml
  cover_value   — continuous heatmap (YlOrRd colormap)

All views share the same cell polygon geometry.
"""

import logging
from typing import List, Optional

import matplotlib.pyplot as plt
import matplotlib.cm as cm
from matplotlib.patches import Patch

from imperial_generals.map.generator import MapResult
from imperial_generals.config import get_config

logger = logging.getLogger(__name__)

# Module-level ordered list of view names
VIEWS: List[str] = ['elevation', 'terrain_type', 'cover_value']


class MapViewer:
    """Interactive multi-view visualizer for a MapResult."""

    def __init__(self, result: MapResult) -> None:
        if not isinstance(result, MapResult):
            raise TypeError(
                f"result must be a MapResult, got {type(result).__name__}"
            )
        if not result.cells:
            raise ValueError("result.cells must not be empty")

        self._result = result
        self._views: List[str] = VIEWS
        self._view_index: int = 0

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def current_view(self) -> str:
        """Return the name of the currently active view."""
        return self._views[self._view_index]

    # ------------------------------------------------------------------
    # View cycling
    # ------------------------------------------------------------------

    def next_view(self) -> str:
        """Advance to the next view (wraps around). Returns new current_view."""
        self._view_index = (self._view_index + 1) % len(self._views)
        return self.current_view

    def prev_view(self) -> str:
        """Go back to the previous view (wraps around). Returns new current_view."""
        self._view_index = (self._view_index - 1) % len(self._views)
        return self.current_view

    # ------------------------------------------------------------------
    # Color helpers
    # ------------------------------------------------------------------

    def get_terrain_color(self, terrain_type: str) -> str:
        """
        Return the hex color for a terrain type from visualization.yaml.
        Falls back to '#aaaaaa' for unknown types.
        """
        terrain_colors = get_config()['visualization']['terrain_colors']
        return terrain_colors.get(terrain_type, '#aaaaaa')

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def render_view(self, view_name: str, ax=None) -> None:
        """
        Render the named view onto ax.

        If ax is None, creates a new figure+ax.
        Raises ValueError for unknown view names.
        """
        if view_name not in self._views:
            raise ValueError(
                f"Unknown view '{view_name}'. Valid views: {self._views}"
            )

        if ax is None:
            _fig, ax = plt.subplots(figsize=(10, 10))

        cells = self._result.cells

        if view_name in ('elevation', 'cover_value'):
            cmap = cm.terrain if view_name == 'elevation' else cm.YlOrRd
            values = [getattr(cell, view_name) for cell in cells]
            min_val, max_val = min(values), max(values)
            if max_val > min_val:
                normalized = [(v - min_val) / (max_val - min_val) for v in values]
            else:
                normalized = [0.5] * len(values)

            for cell, norm_val in zip(cells, normalized):
                x, y = cell.polygon.exterior.xy
                ax.fill(x, y, alpha=0.7, edgecolor='black', linewidth=0.5,
                        facecolor=cmap(norm_val))

            sm = plt.cm.ScalarMappable(
                cmap=cmap,
                norm=plt.Normalize(vmin=min_val, vmax=max_val)
            )
            sm.set_array([])
            cbar = plt.colorbar(sm, ax=ax,
                                label=view_name.replace('_', ' ').title())
            cbar.ax.tick_params(labelsize=10)

        else:  # terrain_type
            for cell in cells:
                color = self.get_terrain_color(cell.terrain_type)
                x, y = cell.polygon.exterior.xy
                ax.fill(x, y, alpha=0.7, edgecolor='black', linewidth=0.5,
                        facecolor=color)

            # Build legend — one patch per unique terrain type
            seen = {}
            for cell in cells:
                tt = cell.terrain_type
                if tt not in seen:
                    seen[tt] = self.get_terrain_color(tt)

            handles = [Patch(facecolor=color, label=tt)
                       for tt, color in seen.items()]
            ax.legend(handles=handles,
                      title='Terrain Type',
                      loc='upper right',
                      fontsize=10)

        ax.set_xlim(0, self._result.voronoi.width)
        ax.set_ylim(0, self._result.voronoi.height)
        ax.set_aspect('equal')
        ax.set_title(
            f"Map — {view_name.replace('_', ' ').title()}",
            fontsize=14,
            fontweight='bold'
        )
        plt.tight_layout()

    # ------------------------------------------------------------------
    # Display
    # ------------------------------------------------------------------

    def view(self, view_name: str = None) -> None:
        """
        Render and display one or all views, each in its own figure.

        Args:
            view_name: Name of a specific view to display, or None to display
                       all views sequentially (one figure per view).

        Raises:
            ValueError: If view_name is given but not a valid view.
        """
        targets = [view_name] if view_name is not None else self._views
        for name in targets:
            self.render_view(name)
        plt.show()

    def show(self) -> None:
        """
        Create a figure, draw the current view, connect keyboard navigation,
        and call plt.show(). Under the Agg backend plt.show() is a no-op.
        """
        fig, ax = plt.subplots(figsize=(10, 10))
        self.render_view(self.current_view, ax=ax)

        def on_key(event):
            if event.key == 'right':
                self.next_view()
            elif event.key == 'left':
                self.prev_view()
            else:
                return
            ax.clear()
            self.render_view(self.current_view, ax=ax)
            fig.canvas.draw()

        fig.canvas.mpl_connect('key_press_event', on_key)
        plt.show()

    # ------------------------------------------------------------------
    # String representations
    # ------------------------------------------------------------------

    def __str__(self) -> str:
        return (
            f"MapViewer(view={self.current_view}, "
            f"cells={len(self._result.cells)})"
        )

    def __repr__(self) -> str:
        return (
            f"<MapViewer(current_view={self.current_view!r}, "
            f"n_cells={len(self._result.cells)}, "
            f"views={self._views!r})>"
        )
