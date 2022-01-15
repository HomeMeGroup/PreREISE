import pandas as pd

from prereise.gather.griddata.hifld import const
from prereise.gather.griddata.hifld.data_access.load import get_eia_form_860
from prereise.gather.hydrodata.eia.fetch_historical import get_generation
from prereise.gather.solardata.nsrdb.sam import retrieve_data_individual


def floatify(x):
    """Coerce an object to a float, returning a float NaN for any objects which raise an
    exception when passed to :func:`float`.

    :param object x: object to coerce.
    :return: (*float*) -- coerced value.
    """
    try:
        return float(x)
    except ValueError:
        return float("nan")


def build_solar(nrel_email, nrel_api_key, solar_plants, **solar_kwargs):
    """Use plant-level data to build solar profiles.

    :param str nrel_email: email used to`sign up <https://developer.nrel.gov/signup/>`_.
    :param str nrel_api_key: API key.
    :param pandas.DataFrame solar_plants: data frame of solar farms.
    :param dict solar_kwargs: keyword arguments to pass to
        :func:`prereise.gather.solardata.nsrdb.sam.retrieve_data_individual`.
    :return: (*pandas.DataFrame*) -- data frame of normalized power profiles. The index
        is hourly timestamps for the profile year, the columns are plant IDs, the values
        are floats.
    """
    boolean_columns = ["Single-Axis Tracking?", "Dual-Axis Tracking?", "Fixed Tilt?"]
    float_columns = ["DC Net Capacity (MW)", "Nameplate Capacity (MW)", "Tilt Angle"]
    # Load raw 'extra' table data, join on plant & generating unit, re-establish index
    extra_solar_data = get_eia_form_860(const.blob_paths["eia_form860_2019_solar"])
    full_data = solar_plants.merge(
        extra_solar_data, on=["Plant Code", "Generator ID"], suffixes=(None, "_extra")
    )
    full_data.index = solar_plants.index
    # Process data to expected types for profile generation
    for col in float_columns:
        full_data[col] = full_data[col].map(floatify)
    for col in boolean_columns:
        # 'Y' becomes True, anything else ('N', blank, etc) becomes False
        full_data[col] = full_data[col] == "Y"

    # If panel type isn't known definitively, assume 100% Fixed Tilt
    # Solar thermal also ends up labeled as fixed tilt, but this will be ignored
    bad_booleans = full_data.index[full_data[boolean_columns].sum(axis=1) != 1]
    full_data.loc[bad_booleans, boolean_columns] = False
    full_data.loc[bad_booleans, "Fixed Tilt?"] = True

    full_data.index.name = "plant_id"  # needed for next step but gets lost in the merge
    profiles = retrieve_data_individual(
        nrel_email,
        nrel_api_key,
        solar_plant=full_data,
        **solar_kwargs,
    )
    return profiles


def build_hydro(eia_api_key, hydro_plants, year, **hydro_kwargs):
    """Use plant-level data to build hydro profiles.

    :param str eia_api_key: API key.
    :param pandas.DataFrame hydro_plants: data frame of hydro generators.
    :param int/str year: year of data to fetch and build profiles for.
    :param dict hydro_kwargs: keyword arguments to pass to
        :func:`from prereise.gather.hydrodata.eia.fetch_historical.get_generation`.
    :return: (*pandas.DataFrame*) -- data frame of normalized power profiles. The index
        is hourly timestamps for the profile year, the columns are plant IDs, the values
        are floats.
    """
    # Build shapes for each region
    query_regions = set(hydro_plants["Balancing Authority Code"].unique())
    query_regions.add("US48")  # total U.S. hydro profile, to be used as a fall-back
    generation = get_generation(eia_api_key, regions=query_regions, **hydro_kwargs)
    # Build shape for 'residual' region (lower 48, minus found regions)
    found_sum = generation.drop("US48", axis=1).sum(axis=1)
    generation["residual"] = generation["US48"] - found_sum
    # Normalize regional totals by regional capacities
    matching_regions = set(query_regions) & set(generation.columns)
    ba_groups = hydro_plants.groupby("Balancing Authority Code")
    ba_capacities = ba_groups["Pmax"].sum()
    residual_capacity = hydro_plants.loc[
        ~hydro_plants["Balancing Authority Code"].isin(matching_regions), "Pmax"
    ].sum()
    normalized_profiles = (
        generation[matching_regions] / ba_capacities.loc[matching_regions]
    )
    normalized_profiles["residual"] = generation["residual"] / residual_capacity
    # Build the output dataframe, and populate it
    profiles = pd.DataFrame(
        index=pd.data_range(start=f"{year}-01-01-00", end=f"{year}-12-31-23", freq="H"),
        columns=hydro_plants.index,
    )
    for region in query_regions:
        plant_ids = ba_groups.get_group(region).index
        if region in normalized_profiles:
            profiles[plant_ids] = normalized_profiles[region]
        else:
            profiles[plant_ids] = normalized_profiles["residual"]

    return profiles
