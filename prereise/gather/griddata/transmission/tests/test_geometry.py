from math import pi

import pytest

from prereise.gather.griddata.transmission.geometry import (
    Conductor,
    ConductorBundle,
    PhaseLocations,
    Tower,
)


def test_conductor():
    # Cardinal conductor
    outer_diameter = 0.03038
    strand_radius = 1.688e-3
    rated_dc_resistance_per_1000_ft = 0.0179
    rated_dc_resistance_per_km = rated_dc_resistance_per_1000_ft * 3.2808
    # Calculate for solid-aluminum (resistance should be lower than rated)
    conductor = Conductor(radius=(outer_diameter / 2), material="aluminum")
    print(conductor.resistance_per_km)
    assert conductor.resistance_per_km < rated_dc_resistance_per_km
    # Count 54 aluminum strands only for conductance purposes, ignore 7 steel strands
    # (resistance should be approximately equal to rated)
    area = 54 * pi * strand_radius ** 2
    conductor = Conductor(radius=(outer_diameter / 2), area=area, material="aluminum")
    assert conductor.resistance_per_km == pytest.approx(rated_dc_resistance_per_km, 0.1)


def test_conductor_bundle():
    spacing = 0.4572
    conductor = Conductor(
        radius=0.01519,
        gmr=0.012253,
        material="ACSR",  # No constants for this material, but they're un-needed
        resistance_per_km=0.023,
    )

    for n in (2, 3):
        bundle = ConductorBundle(n=n, spacing=spacing, conductor=conductor)
        assert bundle.resistance_per_km == conductor.resistance_per_km / n
        assert bundle.spacing_L == (conductor.gmr * spacing ** (n - 1)) ** (1 / n)
        assert bundle.spacing_C == (conductor.radius * spacing ** (n - 1)) ** (1 / n)


def test_tower():
    # Conversion factor for tower spacing in feet to tower spacing in meters
    m_in_ft = 304.8e-3
    km_in_mi = 1.609
    # Tower has two-conductor bundles (1.5 ft spacing), 24 ft b/w phases, 90 ft height
    spacing = 1.5 * m_in_ft
    locations = PhaseLocations(
        a=(-24 * m_in_ft, 90 * m_in_ft),
        b=(0, 90 * m_in_ft),
        c=(24 * m_in_ft, 90 * m_in_ft),
    )
    # Conductors are ACSR 'Cardinal'
    rated_ac_resistance_per_km = 0.0672  # rated value at 50 C
    # Alternate value range: 0.0614 at 20 C, 0.0748 at 75 C.

    # instantiate objects
    conductor = Conductor(
        radius=0.01519,
        gmr=0.012253,
        material="ACSR",  # No constants for this material, but they're un-needed
        resistance_per_km=rated_ac_resistance_per_km,
    )
    bundle = ConductorBundle(n=2, spacing=spacing, conductor=conductor)
    tower = Tower(locations=locations, bundle=bundle)
    # Calculate for 50-mile distances (test case)
    resistance_per_50_mi = tower.resistance * 50 * km_in_mi
    series_reactance_per_50_mi = 2 * pi * 60 * tower.inductance * 50 * km_in_mi
    shunt_admittance_per_50_mi = 2 * pi * 60 * tower.capacitance * 50 * km_in_mi

    # Expected values
    expected_resistance = 2.82  # Ohms
    expected_series_reactance = 29.2  # Ohms
    expected_shunt_admittance = 3.59e-4  # Siemens

    # Check
    # relative tolerance of 5% to account for unknown temperature for resistivity
    assert resistance_per_50_mi == pytest.approx(expected_resistance, rel=0.05)
    # Reactance & admittance values match within 1%, since they're purely gemetric
    assert series_reactance_per_50_mi == pytest.approx(
        expected_series_reactance, rel=0.01
    )
    assert shunt_admittance_per_50_mi == pytest.approx(
        expected_shunt_admittance, rel=0.01
    )
