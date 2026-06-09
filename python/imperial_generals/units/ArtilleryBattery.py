from imperial_generals.units import Regiment
from imperial_generals.utils import Position
from imperial_generals.utils.unit_types import UNIT_SUBTYPES


class ArtilleryBattery(Regiment):
    """
    Represents an artillery battery in the simulation.

    Inherits from Regiment where size = crew (number of men).
    Tracks guns (cannons) separately. Effective firepower is limited
    by whichever is the bottleneck: guns available or crew to man them.

    Parameters
    ----------
    size : int
        Number of crew members.
    stats : str
        Slash-separated string of four integers: experience/morale/weapon/melee.
    guns : int
        Number of cannons.
    position : Position | None
        Optional starting position.
    """

    unit_type: str = "art"
    MIN_CREW_PER_GUN: int = 7

    def __init__(self, size: int, stats: str, guns: int, *, subtype: str, position: Position | None = None) -> None:
        if not isinstance(guns, int):
            raise TypeError(f"guns must be an int, got {type(guns).__name__}.")
        if guns < 0:
            raise ValueError(f"guns must be >= 0, got {guns}.")
        if subtype not in UNIT_SUBTYPES['art']:
            raise ValueError(
                f"subtype '{subtype}' is not valid for artillery. "
                f"Must be one of: {sorted(UNIT_SUBTYPES['art'])}."
            )
        super().__init__(size, stats, position=position)
        self.guns: int = guns
        self.subtype: str = subtype

    @property
    def effective_guns(self) -> int:
        """Guns that can actually be manned given current crew."""
        return min(self.guns, self.size // self.MIN_CREW_PER_GUN)

    def update_guns(self, new_guns: int) -> None:
        """
        Update the number of guns in the battery.

        Parameters
        ----------
        new_guns : int
            New gun count, must be >= 0.

        Raises
        ------
        TypeError
            If new_guns is not an int.
        ValueError
            If new_guns is negative.
        """
        if not isinstance(new_guns, int):
            raise TypeError(f"guns must be an int, got {type(new_guns).__name__}.")
        if new_guns < 0:
            raise ValueError(f"guns must be >= 0, got {new_guns}.")
        self.guns = new_guns

    def __str__(self) -> str:
        base = super().__str__()
        return (
            f"[type: {self.unit_type}/{self.subtype}] {base} | "
            f"Guns={self.guns} | Effective={self.effective_guns}"
        )

    def __repr__(self) -> str:
        base = super().__repr__()
        return f"[type: {self.unit_type}/{self.subtype}] {base} | guns={self.guns}"

    @classmethod
    def from_dict(cls, d: dict) -> 'ArtilleryBattery':
        position = Position.from_dict(d['position']) if 'position' in d else None
        return cls(size=d['size'], stats=d['stats'], guns=d['guns'], subtype=d['subtype'], position=position)
