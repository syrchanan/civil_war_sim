from imperial_generals.utils import get_closest_morale_stat, get_combat_efficiency, Position
from imperial_generals.config import get_config

class Regiment:
    """
    Represents a discrete regiment unit on the battlefield.

    Parameters
    ----------
    size : int
        Number of soldiers in the regiment.
    stats : str
        Slash-separated string of four integers: experience/morale/weapon/melee.
    law : str
        Combat law, either 'ln' (Linear) or 'sq' (Square).

    Attributes
    ----------
    size : int
        Number of soldiers.
    stats : tuple[int, int, int, int]
        (experience, morale, weapon, melee).
    raw_morale : int
        Raw morale value calculated as morale * raw_scale_factor.
    coef : float
        Combat efficiency coefficient.
    law : str
        Combat law used.
    """

    def __init__(self, size: int, stats: str, law: str, position: Position | None = None) -> None:
        """
        Initialize a regiment.

        Args:
            size (int): Number of soldiers in the regiment.
            stats (str): Slash-separated string of four integers (e.g., '4/4/0/0').
            law (str): Combat law, must be either 'ln' (Linear) or 'sq' (Square).

        Raises:
            ValueError: If law is not 'ln' or 'sq', or stats is not four integers.
        """
        if law not in ('ln', 'sq'):
            raise ValueError("Law must be either 'ln' (Linear) or 'sq' (Square).")
        stats_split = stats.split('/')
        if len(stats_split) != 4 or not all(s.isdigit() for s in stats_split):
            raise ValueError("Stats must be a slash-separated string of four integers (e.g., '4/4/0/0').")
        self.size: int = size
        self.stats: tuple[int, int, int, int] = tuple(int(d) for d in stats_split)
        self.coef: float = get_combat_efficiency(*self.stats)
        scale = get_config()['morale']['raw_scale_factor']
        self.raw_morale: float = float(self.stats[1] * scale)
        self.law: str = law
        self.position: Position | None = position

    def __str__(self) -> str:
        return (
            f"Regiment: {self.size} men | "
            f"Stats: xp={self.stats[0]}, morale={self.stats[1]}, weapon={self.stats[2]}, melee={self.stats[3]} | "
            f"Raw Morale={self.raw_morale} | "
            f"Coef={self.coef:.4f} | Law={self.law}"
        )

    def __repr__(self) -> str:
        return (
            f"Regiment(size={self.size}, stats={self.stats}, law='{self.law}')"
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
        self.coef = get_combat_efficiency(*self.stats)

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

    @classmethod
    def from_dict(cls, d: dict) -> 'Regiment':
        position = Position.from_dict(d['position']) if 'position' in d else None
        return cls(size=d['size'], stats=d['stats'], law=d['law'], position=position)

if __name__ == "__main__":  # pragma: no cover
    regiment = Regiment(1000, "4/4/0/0", "ln")
    print(regiment)
    regiment.update_size(800)
    print(regiment)
    regiment.update_stats("5/6/1/0")
    print(regiment)
    regiment.update_raw_morale(55.0)
    print(regiment)
