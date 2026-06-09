from imperial_generals.units import Regiment
from imperial_generals.utils.unit_types import UNIT_SUBTYPES


class InfantryRegiment(Regiment):
    """
    Represents an infantry regiment unit in the simulation.

    Inherits from Regiment. unit_type is 'inf'; subtype must be one of
    the values defined in config/unit_subtypes.yaml.
    """

    unit_type: str = "inf"

    def __init__(self, *args, subtype: str, **kwargs) -> None:
        if subtype not in UNIT_SUBTYPES['inf']:
            raise ValueError(
                f"subtype '{subtype}' is not valid for infantry. "
                f"Must be one of: {sorted(UNIT_SUBTYPES['inf'])}."
            )
        super().__init__(*args, **kwargs)
        self.subtype = subtype

    def __str__(self) -> str:
        return f"[type: {self.unit_type}/{self.subtype}] {super().__str__()}"

    def __repr__(self) -> str:
        return f"[type: {self.unit_type}/{self.subtype}] {super().__repr__()}"

    @classmethod
    def from_dict(cls, d: dict) -> 'InfantryRegiment':
        from imperial_generals.utils import Position
        position = Position.from_dict(d['position']) if 'position' in d else None
        return cls(size=d['size'], stats=d['stats'], subtype=d['subtype'], position=position)
