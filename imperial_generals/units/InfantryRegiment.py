from imperial_generals.units import Regiment

class InfantryRegiment(Regiment):
    """
    Represents an infantry regiment unit in the simulation.

    Inherits from Regiment and sets the unit_type to "inf".
    """

    unit_type: str = "inf"

    def __init__(self, *args, **kwargs) -> None:
        """
        Initialize an InfantryRegiment instance.

        Args:
            *args: Positional arguments passed to Regiment.
            **kwargs: Keyword arguments passed to Regiment.
        """
        super().__init__(*args, **kwargs)

    def __str__(self) -> str:
        # Use Regiment's type and append __str__ info
        base = super().__str__()
        return f"[type: {self.unit_type}] {base}"

    def __repr__(self) -> str:
        # Use Regiment's type and append __repr__ info
        base = super().__repr__()
        return f"[type: {self.unit_type}] {base}"

    def print_type(self) -> str:
        """
        Return only the unit type string for display.
        """
        return self.unit_type