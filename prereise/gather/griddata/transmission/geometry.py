from dataclasses import dataclass
from math import exp, log, pi, prod, sqrt

from prereise.gather.griddata.transmission.const import (
    epsilon_0,
    mu_0,
    relative_permeability,
    resistivity,
)


@dataclass
class Conductor:
    radius: float
    material: str = None
    resistance_per_km: float = None
    gmr: float = None
    area: float = None

    def __post_init__(self):
        # Validate inputs
        if self.gmr is None and (self.material is None or self.radius is None):
            raise ValueError(
                "If gmr is not provided, material and radius are needed to estimate"
            )
        if self.resistance_per_km is None and (
            self.material is None or self.radius is None
        ):
            raise ValueError(
                "If resistance_per_km is not provided, "
                "material and radius are needed to estimate"
            )

        if self.gmr is None:
            try:
                self.permeability = relative_permeability[self.material]
            except KeyError:
                raise ValueError(
                    f"Unknown permeability for {self.material}, can't calculate gmr"
                )
            self.gmr = self.radius * exp(self.permeability / 4)

        if self.resistance_per_km is None:
            try:
                self.resistivity = resistivity[self.material]
            except KeyError:
                raise ValueError(
                    f"Unknown resistivity for {self.material}, "
                    "can't calculate resistance"
                )
            if self.area is None:
                self.area = pi * self.radius ** 2
            # convert per-m to per-km
            self.resistance_per_km = self.resistivity * 1000 / self.area


@dataclass
class ConductorBundle:
    n: int
    spacing: float
    conductor: Conductor
    layout: str = "circular"

    def __post_init__(self):
        self.resistance_per_km = self.conductor.resistance_per_km / self.n
        self.spacing_L = self.calculate_equivalent_spacing("inductance")
        self.spacing_C = self.calculate_equivalent_spacing("capacitance")

    def calculate_equivalent_spacing(self, type="inductance"):
        if type == "inductance":
            conductor_distance = self.conductor.gmr
        elif type == "capacitance":
            conductor_distance = self.conductor.radius
        else:
            raise ValueError("type must be either 'inductance' or 'capacitance'")
        if self.n == 2:
            return (conductor_distance * self.spacing) ** (1 / 2)
        else:
            if self.layout == "circular":
                return self.calculate_equivalent_spacing_circular(conductor_distance)
            if self.layout == "flat":
                return self.calculate_equivalent_spacing_flat(conductor_distance)
            raise ValueError(f"Unknown layout: {self.layout}")

    def calculate_equivalent_spacing_circular(self, conductor_distance):
        if self.n == 3:
            return (conductor_distance * self.spacing ** (self.n - 1)) ** (1 / self.n)
        if self.n == 4:
            return (conductor_distance * self.spacing ** 3 * 2 ** (1 / 2)) ** (1 / 4)
        raise NotImplementedError("Geometry calculations not implemented for n > 4")

    def calculate_equivalent_spacing_flat(self, conductor_distance):
        if self.n == 3:
            return (conductor_distance * 2 * self.spacing ** 2) ** (1 / 3)
        if self.n == 4:
            return (conductor_distance * 12 * self.spacing ** 3) ** (1 / 8)
        raise NotImplementedError("Geometry calculations not implemented for n > 4")


@dataclass
class PhaseLocations:
    a: tuple
    b: tuple
    c: tuple


@dataclass
class Tower:
    """Given the geometry of a transmission tower and conductor bundle information,
    estimate per-kilometer inductance, resistance, and shunt capacitance.
    """

    locations: PhaseLocations
    bundle: ConductorBundle
    circuits: int = 1
    freq: float = 60.0

    def __post_init__(self):
        if self.circuits != 1:
            raise ValueError("Can't calculate geometry for multi-circuit lines yet")
        self.a = self.locations.a
        self.b = self.locations.b
        self.c = self.locations.c
        self.calculate_distances()
        self.resistance = self.bundle.resistance_per_km
        self.inductance = self.calculate_inductance_per_km()
        self.capacitance = self.calculate_shunt_capacitance_per_km()

    def calculate_distances(self):
        self.true_distance = {
            "ab": sqrt((self.a[0] - self.b[0]) ** 2 + (self.a[1] - self.b[1]) ** 2),
            "ac": sqrt((self.a[0] - self.c[0]) ** 2 + (self.a[1] - self.c[1]) ** 2),
            "bc": sqrt((self.b[0] - self.c[0]) ** 2 + (self.b[1] - self.c[1]) ** 2),
        }
        self.reflected_distance = {
            "ab": sqrt((self.a[0] - self.b[0]) ** 2 + (self.a[1] + self.b[1]) ** 2),
            "ac": sqrt((self.a[0] - self.c[0]) ** 2 + (self.a[1] + self.c[1]) ** 2),
            "bc": sqrt((self.b[0] - self.c[0]) ** 2 + (self.b[1] + self.c[1]) ** 2),
        }
        # 'Equivalent' distances are geometric means
        self.equivalent_distance = prod(self.true_distance.values()) ** (1 / 3)
        self.equivalent_reflected_distance = prod(self.reflected_distance.values()) ** (
            1 / 3
        )
        self.equivalent_height = prod([self.a[1], self.b[1], self.c[1]]) ** (1 / 3)

    def calculate_inductance_per_km(self):
        inductance_per_km = (
            mu_0 / (2 * pi) * log(self.equivalent_distance / self.bundle.spacing_L)
        )
        return inductance_per_km

    def calculate_shunt_capacitance_per_km(self):
        capacitance_per_km = (2 * pi * epsilon_0) / (
            log(self.equivalent_distance / self.bundle.spacing_C)
            - log(self.equivalent_reflected_distance / (2 * self.equivalent_height))
        )
        return capacitance_per_km
