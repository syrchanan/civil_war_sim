from imperial_generals.utils import get_closest_morale_stat, get_combat_efficiency, Position
from imperial_generals.config import get_config

class Regiment:

    VALID_COMBAT_MODES: frozenset = frozenset({'idle', 'ranged', 'melee'})
    """
    Represents a discrete regiment unit on the battlefield.

    Parameters
    ----------
    size : int
        Number of soldiers in the regiment.
    stats : str
        Slash-separated string of four integers: experience/morale/weapon/melee.

    Attributes
    ----------
    size : int
        Number of soldiers.
    stats : tuple[int, int, int, int]
        (experience, morale, weapon, melee).
    raw_morale : float
        Raw morale value calculated as morale * raw_scale_factor.
    coef : float
        Combat efficiency coefficient (property, dynamic based on combat_mode).
    effective_law : str
        Lanchester law to use at simulation time (property, dynamic based on combat_mode).
    """

    def __init__(self, size: int, stats: str, position: Position | None = None, front_size: int | None = None) -> None:
        """
        Initialize a regiment.

        Args:
            size (int): Number of soldiers in the regiment.
            stats (str): Slash-separated string of four integers (e.g., '4/4/0/0').

        Raises:
            ValueError: If stats is not four integers, or front_size is not a positive int.
        """
        stats_split = stats.split('/')
        if len(stats_split) != 4 or not all(s.isdigit() for s in stats_split):
            raise ValueError("Stats must be a slash-separated string of four integers (e.g., '4/4/0/0').")
        _front_size = front_size if front_size is not None else size
        if not isinstance(_front_size, int):
            raise TypeError(f"front_size must be an int, got {type(_front_size).__name__}.")
        if _front_size < 0:
            raise ValueError(f"front_size must be non-negative, got {_front_size}.")
        self.size: int = size
        self.stats: tuple[int, int, int, int] = tuple(int(d) for d in stats_split)
        self._base_coef: float = get_combat_efficiency(self.stats[0], self.stats[1], self.stats[2], 0)
        scale = get_config()['morale']['raw_scale_factor']
        self.raw_morale: float = float(self.stats[1] * scale)
        self.position: Position | None = position
        self.combat_mode: str = 'idle'
        self.front_size: int = _front_size

    @property
    def coef(self) -> float:
        """
        Combat efficiency coefficient, adjusted for current combat mode.

        - Melee-only unit firing at range: 0.0 (cannot shoot).
        - Ranged unit in melee: base coef * melee_penalty_factor.
        - All other modes: base coef.
        """
        if self.is_melee_only and self.combat_mode == 'ranged':
            return 0.0
        if not self.is_melee_only and self.combat_mode == 'melee':
            return self._base_coef * get_config()['combat']['melee_penalty_factor']
        return self._base_coef

    @property
    def effective_law(self) -> str:
        """Lanchester law to apply at simulation time: 'ln' in melee, 'sq' at range."""
        return 'ln' if self.combat_mode == 'melee' else 'sq'

    @property
    def is_melee_only(self) -> bool:
        """True if this unit can only fight in melee (stats[3] == 1)."""
        return self.stats[3] == 1

    def set_combat_mode(self, mode: str) -> None:
        """
        Set the current combat engagement mode.

        Parameters
        ----------
        mode : str
            One of 'idle', 'ranged', or 'melee'.

        Raises
        ------
        ValueError
            If mode is not a valid combat mode.
        """
        if mode not in self.VALID_COMBAT_MODES:
            raise ValueError(
                f"combat_mode '{mode}' is not valid. "
                f"Must be one of: {sorted(self.VALID_COMBAT_MODES)}."
            )
        self.combat_mode = mode

    def set_front_size(self, front_size: int) -> None:
        """
        Set the number of men forming the front line.

        Parameters
        ----------
        front_size : int
            Must be a positive integer.

        Raises
        ------
        TypeError
            If front_size is not an int.
        ValueError
            If front_size is not positive.
        """
        if not isinstance(front_size, int):
            raise TypeError(f"front_size must be an int, got {type(front_size).__name__}.")
        if front_size < 0:
            raise ValueError(f"front_size must be non-negative, got {front_size}.")
        self.front_size = front_size

    def __str__(self) -> str:
        return (
            f"Regiment: {self.size} men | "
            f"Stats: xp={self.stats[0]}, morale={self.stats[1]}, weapon={self.stats[2]}, melee={self.stats[3]} | "
            f"Raw Morale={self.raw_morale} | "
            f"Coef={self.coef:.4f} | EffectiveLaw={self.effective_law} | Mode={self.combat_mode} | "
            f"FrontSize={self.front_size}"
        )

    def __repr__(self) -> str:
        return (
            f"Regiment(size={self.size}, stats={self.stats})"
        )

    def deploy(self, position: Position) -> None:
        """
        Place or move the regiment to a new position on the battlefield.

        Parameters
        ----------
        position : Position
            The new battlefield position.

        Raises
        ------
        TypeError
            If position is not a Position instance.
        """
        if not isinstance(position, Position):
            raise TypeError(f"position must be a Position instance, got {type(position).__name__}.")
        self.position = position

    def _require_positions(self, other: 'Regiment') -> None:
        if self.position is None or other.position is None:
            raise ValueError("Both regiments must have a position before calculating distance.")

    def flat_distance_to(self, other: 'Regiment') -> float:
        """Flat (x/y) distance to another regiment."""
        self._require_positions(other)
        return self.position.flat_distance_to(other.position)

    def true_distance_to(self, other: 'Regiment') -> float:
        """3D distance to another regiment, including elevation."""
        self._require_positions(other)
        return self.position.true_distance_to(other.position)

    def elevation_difference_to(self, other: 'Regiment') -> float:
        """Signed elevation difference to another regiment (positive means other is higher)."""
        self._require_positions(other)
        return self.position.elevation_difference_to(other.position)

    def update_size(self, new_size: int) -> None:
        """
        Update the regiment's size.

        Parameters
        ----------
        new_size : int
            The new size of the regiment.
        """
        self.size = new_size

    def update_stats(self, new_stats: str) -> None:
        """
        Update the regiment's stats and recalculate the combat efficiency coefficient.

        Parameters
        ----------
        new_stats : str
            Slash-separated string of four integers (e.g., '5/6/1/0').

        Raises
        ------
        ValueError
            If new_stats is not four integers.
        """
        stats_split = new_stats.split('/')
        if len(stats_split) != 4 or not all(s.isdigit() for s in stats_split):
            raise ValueError("New stats must be a slash-separated string of four integers (e.g., '5/6/1/0').")
        self.stats = tuple(int(d) for d in stats_split)
        self._base_coef = get_combat_efficiency(self.stats[0], self.stats[1], self.stats[2], 0)

    def update_raw_morale(self, new_morale: float) -> None:
        """
        Update the regiment's raw morale.

        Parameters
        ----------
        new_morale : float
            The new raw morale value.

        Raises
        ------
        TypeError
            If new_morale is not a float.
        """
        if not isinstance(new_morale, float):
            raise TypeError("new_morale must be a float.")

        # update raw morale and get closest morale stat
        self.raw_morale = new_morale
        new_stat = get_closest_morale_stat(new_morale)

        # update stats & coef
        self.update_stats(f"{self.stats[0]}/{new_stat}/{self.stats[2]}/{self.stats[3]}")

    def deploy_to_cell(self, cell) -> None:
        """Deploy regiment to a map Cell, deriving position from cell data."""
        self.deploy(Position.from_cell(cell))

    @classmethod
    def from_dict(cls, d: dict) -> 'Regiment':
        position = Position.from_dict(d['position']) if 'position' in d else None
        front_size = d.get('front_size', None)
        return cls(size=d['size'], stats=d['stats'], position=position, front_size=front_size)

if __name__ == "__main__":  # pragma: no cover
    regiment = Regiment(1000, "4/4/0/0")
    print(regiment)
    regiment.update_size(800)
    print(regiment)
    regiment.update_stats("5/6/1/0")
    print(regiment)
    regiment.update_raw_morale(55.0)
    print(regiment)
