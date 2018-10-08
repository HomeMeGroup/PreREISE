# Import western interconnect data
from westernintnet.westernintnet import WesternIntNet

from .context import *

win = WesternIntNet()


def test():

    all_siteID_NREL = te_wind.get_all_NREL_siteID_for_states(['WA'])

    wind_farm_bus = win.genbus.groupby('type').get_group('wind')

    closest_NREL_siteID = te_wind.find_NREL_siteID_closest_to_windfarm(
        all_siteID_NREL, wind_farm_bus[['lat', 'lon']]
    )

    data_start = te_wind.pd.Timestamp('2010-01-01')
    data_end = te_wind.pd.Timestamp('2010-01-01 23:55:00')
    data_range = te_wind.pd.date_range(data_start, data_end, freq='5min')

    data = te_wind.get_data_from_NREL_server(closest_NREL_siteID, data_range)

    [power, wind_speed] = te_wind.dict_to_DataFrame(
        data, data_range, closest_NREL_siteID
    )
