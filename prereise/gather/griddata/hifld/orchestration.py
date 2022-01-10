import os
import shutil

from powersimdata.input import const as psd_const

from prereise.gather.griddata.hifld.const import powersimdata_column_defaults
from prereise.gather.griddata.hifld.data_process.demand import assign_demand_to_buses
from prereise.gather.griddata.hifld.data_process.generators import build_plant
from prereise.gather.griddata.hifld.data_process.profiles import build_solar, build_wind
from prereise.gather.griddata.hifld.data_process.transmission import build_transmission


def create_csvs(
    output_folder,
    wind_directory,
    year,
    nrel_email,
    nrel_api_key,
    solar_kwargs={},
):
    """Process HIFLD source data to CSVs compatible with PowerSimData.

    :param str output_folder: directory to write CSVs to.
    :param str wind_directory: directory to save wind speed data to.
    :param int/str year: weather year to use to generate profiles.
    :param str nrel_email: email used to`sign up <https://developer.nrel.gov/signup/>`_.
    :param str nrel_api_key: API key.
    :param dict solar_kwargs: keyword arguments to pass to
        :func:`prereise.gather.solardata.nsrdb.sam.retrieve_data_individual`.
    """
    # Process grid data from original sources
    branch, bus, substation, dcline = build_transmission()
    plant = build_plant(bus, substation)
    assign_demand_to_buses(substation, branch, plant, bus)

    outputs = {}
    outputs["branch"] = branch
    outputs["dcline"] = dcline
    outputs["sub"] = substation
    # Separate tables as necessary to match PowerSimData format
    # bus goes to bus and bus2sub
    outputs["bus2sub"] = bus[["sub_id", "interconnect"]]
    outputs["bus"] = bus.drop(["sub_id"], axis=1)
    # plant goes to plant and gencost
    outputs["gencost"] = plant[["c0", "c1", "c2", "interconnect"]].copy()
    outputs["plant"] = plant.drop(["c0", "c1", "c2"], axis=1)

    # Use plant data to build profiles
    full_solar_kwargs = {**solar_kwargs, **{"year": year}}
    profiles = {
        "solar": build_solar(
            nrel_email,
            nrel_api_key,
            outputs["plant"].query("type == 'solar'"),
            **full_solar_kwargs,
        ),
        "wind": build_wind(
            outputs["plant"].query("type == 'wind'"),
            wind_directory,
            year,
        ),
    }

    # Fill in missing column values
    for name, defaults in powersimdata_column_defaults.items():
        outputs[name] = outputs[name].assign(**defaults)

    # Filter to only the columns expected by PowerSimData, in the expected order
    for name, df in outputs.items():
        col_names = getattr(psd_const, f"col_name_{name}")
        if name == "bus":
            # The bus column names in PowerSimData include the index for legacy reasons
            col_names = col_names[1:]
        if name == "branch":
            col_names += ["branch_device_type"]
        if name == "plant":
            col_names += ["type", "GenFuelCost", "GenIOB", "GenIOC", "GenIOD"]
        if name == "dcline":
            col_names += ["from_interconnect", "to_interconnect"]
        else:
            col_names += ["interconnect"]
        outputs[name] = outputs[name][col_names]

    # Save files
    outputs.update(profiles)
    os.makedirs(output_folder, exist_ok=True)
    for name, df in outputs.items():
        df.to_csv(os.path.join(output_folder, f"{name}.csv"))
    # The zone file gets copied directly
    zone_path = os.path.join(os.path.dirname(__file__), "data", "zone.csv")
    shutil.copyfile(zone_path, os.path.join(output_folder, "zone.csv"))
