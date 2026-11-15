# Plain-language definitions of the 25 variables

Status: **science-reviewed (Husam); awaiting final voice check (G)**. Same text feeds the app (`frontend/src/features/atlas/variableDefinitions.json`).

A "reading hint" never states a cause: it says what a higher value usually means, so the UI can stay honest about what a trend does and does not show.


## Air

| Variable | Units | What it is | What higher usually means |
|---|---|---|---|
| NO2 (`no2_mean_molec_cm2`) | molecules/cm^2 | How much nitrogen dioxide, a gas released mainly by burning fuel, sits in the lower atmosphere (tropospheric air column) above the area, measured by the Aura satellite. | Higher usually means more combustion (traffic, power, industry, fires), but weather and sunlight also change how fast it disperses or breaks down. |
| Wind speed (`ws10m`) | m/s | How fast the wind blows 10 metres above the ground. | Stronger wind spreads pollution out and increases drying; calm air lets pollution build up. |
| Cloud amount (`cloud_amt`) | % | The share of the sky covered by cloud. | Clouds also block the satellite's view, so this helps judge how much to trust NO₂ months. |
| Pressure (`ps`) | kPa | The air pressure at the ground surface. | Changes over time track high-pressure fair weather versus low-pressure storms; average levels also depend on ground elevation. |
| Clear-sky sunlight (`clrsky_sfc_sw_dwn`) | MJ/m^2/day | The sunlight energy that would reach the ground if the sky were cloud-free. | Mainly set by the season and latitude (plus atmospheric haze and water vapour); it is the cloudless ceiling. |
| Cloud sunlight reduction (`cloud_radiative_attenuation_wm2`) | W/m^2 | How much sunlight power clouds blocked before reaching the ground: clear-sky minus actual sunlight, converted to watts per square metre. | Larger means cloudier skies took away more sun. |

## Fire

| Variable | Units | What it is | What higher usually means |
|---|---|---|---|
| Vegetation fire density (`fire_type0_per_1k_km2_day`) | det / 1000 km^2 / day | How many satellite-detected heat spots from presumed vegetation fires appear per 1,000 km² per day observed by the satellite (nominal and high confidence). | Counts detected pixels across satellite overpasses, not distinct fires or burned area; higher means more detected burning from wildfires, farm burning or war-related fires. |
| Static heat sources (`fire_type2_per_1k_km2_day`) | det / 1000 km^2 / day | Persistent stationary heat spots on land that are not vegetation fires, such as steelworks, industrial plants and gas flares, per 1,000 km² per satellite-observed day. | A steady industrial background reading; sharp drops or rises usually mean plants or flares stopped, started or were damaged. |
| Air temperature (`t2m`) | °C | The monthly average air temperature 2 metres above the ground. | The basic measure of warm or cold. |
| Peak temperature (`t2m_max`) | °C | The single hottest air temperature reached 2 metres above the ground at any time during the month (monthly extreme peak, not an average of daily highs). | Captures monthly heat extremes, which spike wildfire and heat-stress risk. |
| Temperature range (`dtr_c`) | °C | The daily gap between daytime high and nighttime low air temperature, averaged over the month. | A wider average daily swing points to clear, dry days and cooler nights; a narrow gap points to cloudy or humid air. |
| All-sky sunlight (`allsky_sfc_sw_dwn`) | MJ/m^2/day | The sunlight energy actually reaching the ground each day, with clouds included. | Less than clear-sky sunlight whenever it is cloudy; drives surface heating and evaporation. |
| Evaporation demand (PET) (`pet_fao56_mm_day`) | mm/day | How much water the air and sun could pull in a day from a hypothetical well-watered reference grass field (the FAO-56 standard benchmark). | Higher means thirstier air and potential faster drying of soil and crops; actual evaporation is lower when soils are dry. |

## Water

| Variable | Units | What it is | What higher usually means |
|---|---|---|---|
| Rainfall (`prectotcorr`) | mm/day | The total rain and melted snowfall reaching the ground, as millimetres of liquid water per day (bias-corrected reanalysis). | The main supply of water to land. |
| VPD (drying demand) (`vpd_kpa`) | kPa | How dry the air feels to plants: the gap between saturation vapour pressure at that temperature and the air's actual vapour pressure. | Higher means the air pulls moisture out of leaves and damp soil faster. |
| Specific humidity (`qv2m`) | g/kg | The mass of water vapour mixed into the air, in grams per kilogram of moist air at 2 metres height. | Higher means the air actually carries more moisture, independent of temperature. |
| Relative humidity (`rh2m`) | % | How close the air's water vapour is to saturation, as a percentage of the maximum it could hold at that temperature. | Lower values mean drier air, either because moisture fell or because temperature rose. |
| Transpiration (`evptrns_mm_day`) | mm/day | Model-estimated water that plants release into the air through their leaves each day (MERRA-2 canopy transpiration, converted from energy flux). | Drops near zero in dormant winter; higher in warm months means active, growing vegetation with available root water. |
| Water balance (P - PET) (`precip_minus_pet_mm_day`) | mm/day | Total precipitation (rain and melted snow) minus reference evaporation demand (PET): the climatic water surplus or deficit. | Below zero (common in summer) means atmospheric demand exceeds water supplied by precipitation. |

## Earth

| Variable | Units | What it is | What higher usually means |
|---|---|---|---|
| Surface soil wetness (`gwettop`) | fraction | Reanalysis model estimate of how wet the top 5 cm of soil is, from 0 (completely water-free) to 1 (saturated). | Reacts quickly to recent rain and dry spells. |
| Root-zone wetness (`gwetroot`) | fraction | Reanalysis model estimate of how wet the soil is down to 1 metre, where most roots grow, from 0 (completely water-free) to 1 (saturated). | Shows whether crops and vegetation have moisture in reserve. |
| Full-profile wetness (`gwetprof`) | fraction | Reanalysis model estimate of wetness across the entire soil column from the surface to bedrock, from 0 (completely water-free) to 1 (saturated). | Changes slowly; tracks multi-season dry or wet periods. |
| Surface temperature (`ts`) | °C | The modelled radiative skin temperature of the ground surface itself, rather than the air 2 metres above it. | Rises with strong sun and dry ground. |
| Surface-air diff (`ts_minus_t2m_c`) | °C | How much warmer or cooler the modelled ground skin surface is than the air 2 metres above it, as a 24-hour monthly mean. | Across 24-hour monthly averages, values stay near zero (-1.4 to +2.0 °C); positive summer shifts point to stronger heating or drier ground, while winter values often turn negative under snow or radiative cooling. |
| Albedo (`allsky_srf_alb`) | dimensionless | The share of incoming sunlight the ground reflects back upward, from 0 (none) to 1 (all). | Snow and bright bare soil reflect more; dark forest and green or wet fields reflect less. |

Note: the catalog files temperature, PET and sunlight under Fire, and soil and surface fields under Earth. Record spans differ by source: Fire covers March–August only of 2019–2022 (four warm seasons); NO₂ spans March 2015 – August 2022; all 22 NASA POWER weather, water and earth variables span January 2015 – December 2022.
