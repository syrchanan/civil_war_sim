"""
Terrain (positions pass P4): the ground a battle is fought on, saved in the state file as a grid.

The client generates it (web/src/ui/terrainGen.ts); both engines only read it, so a saved battle replays exactly in
either language. A grid of ``columns`` × ``rows`` square cells, ``cell`` yards a side, starting at (0, 0):

- ``heights``: yards above the field's lowest ground, one per cell (row by row), taken at the cell's centre and
  interpolated between centres (bilinear); outside the outermost centres the ground holds level.
- ``ground``: one letter per cell: ``o`` open, ``f`` forest, ``r`` rough (see ``GROUND``).
- ``meta``: free-form (the preset and seed it was made from), round-tripped untouched.

Points off the grid take the nearest edge. Reading uses only + - * / and floor, so both engines agree bit for bit.
"""

import math
from dataclasses import dataclass, field

GROUND = {'o': 'open', 'f': 'forest', 'r': 'rough'}
KEYS = ('cell', 'columns', 'rows', 'heights', 'ground', 'meta')


def _whole(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def _number(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


@dataclass(frozen=True)
class Terrain:
    cell: float
    columns: int
    rows: int
    heights: tuple
    ground: str
    meta: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not (_number(self.cell) and self.cell > 0):
            raise ValueError("cell must be a positive number of yards.")
        for name in ('columns', 'rows'):
            if not (_whole(getattr(self, name)) and getattr(self, name) > 0):
                raise ValueError(f"{name} must be a positive whole number.")
        n = self.columns * self.rows
        if len(self.heights) != n or not all(_number(h) for h in self.heights):
            raise ValueError(f"heights must be {n} numbers (columns × rows, row by row).")
        if not isinstance(self.ground, str) or len(self.ground) != n or any(c not in GROUND for c in self.ground):
            raise ValueError(f"ground must be {n} letters, each one of {', '.join(GROUND)} (open, forest, rough).")
        if not isinstance(self.meta, dict):
            raise ValueError("meta must be a mapping.")

    @property
    def width(self) -> float:
        return self.columns * self.cell

    @property
    def height(self) -> float:
        return self.rows * self.cell

    def _h(self, column: int, row: int) -> float:
        return self.heights[row * self.columns + column]

    @staticmethod
    def _axis(v: float, cell: float, count: int) -> tuple:
        """(lower index, share towards the next) along one axis, between cell centres; level beyond them."""
        f = v / cell - 0.5
        if count == 1 or f <= 0:
            return 0, 0.0
        if f >= count - 1:
            return count - 2, 1.0
        i = math.floor(f)
        return i, f - i

    def height_at(self, x: float, y: float) -> float:
        """Yards above the lowest ground at (x, y), interpolated between cell centres."""
        i, tx = self._axis(x, self.cell, self.columns)
        j, ty = self._axis(y, self.cell, self.rows)
        i1 = min(i + 1, self.columns - 1)
        j1 = min(j + 1, self.rows - 1)
        a = self._h(i, j) + (self._h(i1, j) - self._h(i, j)) * tx
        b = self._h(i, j1) + (self._h(i1, j1) - self._h(i, j1)) * tx
        return a + (b - a) * ty

    def ground_at(self, x: float, y: float) -> str:
        """'open', 'forest' or 'rough': the cell containing (x, y); off the grid, the nearest edge cell."""
        column = min(self.columns - 1, max(0, math.floor(x / self.cell)))
        row = min(self.rows - 1, max(0, math.floor(y / self.cell)))
        return GROUND[self.ground[row * self.columns + column]]

    def to_dict(self) -> dict:
        return {'cell': self.cell, 'columns': self.columns, 'rows': self.rows, 'heights': list(self.heights),
                'ground': self.ground, 'meta': dict(self.meta)}

    @classmethod
    def from_dict(cls, data) -> 'Terrain':
        """
        Raises
        ------
        ValueError
            Naming what is missing or wrong.
        """
        if not isinstance(data, dict):
            raise ValueError('"terrain" must be a mapping (cell, columns, rows, heights, ground).')
        missing = [k for k in KEYS[:5] if k not in data]
        if missing:
            raise ValueError(f"terrain is missing {', '.join(missing)}.")
        heights = data['heights']
        if not isinstance(heights, list):
            raise ValueError("heights must be a list of numbers.")
        return cls(data['cell'], data['columns'], data['rows'], tuple(heights), data['ground'],
                   data.get('meta', {}))
