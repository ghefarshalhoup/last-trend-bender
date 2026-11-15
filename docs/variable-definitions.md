# Plain-language definitions of the 25 variables

Status: **draft**. Husam checks the science (units, what each measures); G checks the voice. Same text feeds the app (`frontend/src/features/atlas/variableDefinitions.json`).

A "reading hint" never states a cause: it says what a higher value usually means, so the UI can stay honest about what a trend does and does not show.


## Air

| Variable | Units | What it is | What higher usually means |
|---|---|---|---|
| NO2 (`no2_mean_molec_cm2`) | molecules/cm^2 | How much nitrogen dioxide, a gas released mainly by burning fuel, sits in the air column above the area, measured by the Aura satellite. | Higher usually means more combustion (traffic, power, industry, fires), but weather also moves it. |
| Wind speed (`ws10m`) | m/s | How fast the wind blows 10 metres above the ground. | Stronger wind spreads pollution out; calm air lets it build up. |
| Cloud amount (`cloud_amt`) | % | The share of the sky covered by cloud. | Clouds also block the satellite's view, so this helps judge how much to trust NO₂ months. |
| Pressure (`ps`) | kPa | The air pressure at the ground. | High pressure usually means calm, clear weather; low pressure means storms and cloud. |
| Clear-sky sunlight (`clrsky_sfc_sw_dwn`) | MJ/m^2/day | The sunlight that would reach the ground if the sky were cloud-free. | Set by the season and latitude; it is the sunny-day ceiling. |
| Cloud sunlight reduction (`cloud_radiative_attenuation_wm2`) | W/m^2 | How much sunlight the clouds blocked: clear-sky sunlight minus actual sunlight. | Larger means cloudier skies took away more sun. |

## Fire

| Variable | Units | What it is | What higher usually means |
|---|---|---|---|
| Vegetation fire density (`fire_type0_per_1k_km2_day`) | det / 1000 km^2 / day | How many satellite-detected heat spots from presumed vegetation fires appear per 1,000 km² each day. | Higher means more burning detected, from wildfires, farm burning or war-related fires; the satellite cannot say which. |
| Static heat sources (`fire_type2_per_1k_km2_day`) | det / 1000 km^2 / day | Heat spots on land that are not vegetation fires, such as gas flares and industrial sites. | A steady background reading; changes can mean industry started, stopped or was damaged. |
| Air temperature (`t2m`) | °C | The average air temperature 2 metres above the ground. | The basic measure of warm or cold. |
| Peak temperature (`t2m_max`) | °C | The hottest air temperature reached each day, averaged over the month. | Shows daytime heat, which drives drought and wildfire risk. |
| Temperature range (`dtr_c`) | °C | The gap between the hottest and coldest air temperature of the day. | A big gap means clear, dry days and cold nights; a small gap means cloudy or humid weather. |
| All-sky sunlight (`allsky_sfc_sw_dwn`) | MJ/m^2/day | The sunlight actually reaching the ground, with clouds included. | Less than clear-sky sunlight whenever it is cloudy. |
| Evaporation demand (PET) (`pet_fao56_mm_day`) | mm/day | How much water the air and sun could pull from a well-watered field in a day (the FAO-56 standard estimate). | Higher means thirstier air and faster drying of soil and crops. |

## Water

| Variable | Units | What it is | What higher usually means |
|---|---|---|---|
| Rainfall (`prectotcorr`) | mm/day | The rain and snow that fell, as millimetres of water per day. | The main supply of water to land. |
| VPD (drying demand) (`vpd_kpa`) | kPa | How dry the air is, measured as how much more moisture it could still hold. | Higher means the air pulls water from plants and soil harder. |
| Specific humidity (`qv2m`) | g/kg | The weight of water vapour in the air, in grams per kilogram of air. | Higher means the air holds more moisture. |
| Relative humidity (`rh2m`) | % | How full of water vapour the air is, as a percentage of the most it could hold at that temperature. | Low values mean dry air. |
| Transpiration (`evptrns_mm_day`) | mm/day | The water that plants release into the air through their leaves, per day. | Higher means growing vegetation is active and using water. |
| Water balance (P - PET) (`precip_minus_pet_mm_day`) | mm/day | Rainfall minus the water the air could evaporate: the surplus or deficit of water. | Below zero means more water is being demanded than rain supplies. |

## Earth

| Variable | Units | What it is | What higher usually means |
|---|---|---|---|
| Surface soil wetness (`gwettop`) | fraction | How wet the top 5 cm of soil is, from 0 (dry) to 1 (saturated). | Reacts quickly to rain and dry spells. |
| Root-zone wetness (`gwetroot`) | fraction | How wet the soil is down to 1 metre, where most roots grow, from 0 (dry) to 1 (saturated). | Shows whether crops and plants have water in reserve. |
| Full-profile wetness (`gwetprof`) | fraction | How wet the whole soil column is, from 0 (dry) to 1 (saturated). | Changes slowly; shows long dry or wet periods. |
| Surface temperature (`ts`) | °C | The temperature of the ground surface itself, not the air above it. | Rises with sun and dry ground. |
| Surface-air diff (`ts_minus_t2m_c`) | °C | How much hotter or cooler the ground surface is than the air just above it. | A large positive gap points to hot, dry, bare ground. |
| Albedo (`allsky_srf_alb`) | dimensionless | The share of incoming sunlight the ground reflects, from 0 (none) to 1 (all). | Snow and bright soil reflect more; dark forest and wet fields reflect less. |

Note: the catalog files temperature, PET and sunlight under Fire, and soil and surface fields under Earth. Fire is the only element with just four seasons of data.
