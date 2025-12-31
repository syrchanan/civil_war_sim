from typing import Dict
from imperial_generals.units.Regiment import Regiment

class Army:
    """
    Represents an army composed of regiments and other subunits.

    Attributes:
        faction (str): The faction or side the army belongs to.
        forces (Dict[str, Regiment]): Dictionary mapping regiment names to Regiment instances.
    """

    def __init__(self, faction: str) -> None:
        """
        Initialize an Army instance.

        Args:
            faction (str): The faction or side the army belongs to.
        """
        self.faction: str = faction
        self.forces: Dict[str, Regiment] = {}

    def add_regiment(self, name: str, regiment: Regiment) -> None:
        """
        Add a regiment to the army.

        Args:
            name (str): The name of the regiment.
            regiment (Regiment): The Regiment instance to add.

        Raises:
            TypeError: If regiment is not an instance of Regiment.
        """
        if not isinstance(regiment, Regiment):
            raise TypeError("regiment must be an instance of Regiment")
        self.forces[name] = regiment

    def __str__(self) -> str:
        return f"Army(faction={self.faction}, forces={list(self.forces.keys())})"

    def __repr__(self) -> str:
        return f"Army(faction={self.faction!r}, forces={self.forces!r})"

if __name__ == "__main__":
    army = Army("Union")
    army.add_regiment("69th PVI", Regiment(1500, '10/10/2/0', 'sq'))
    print(army)
    print(repr(army))