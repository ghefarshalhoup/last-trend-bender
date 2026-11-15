# Data availability by place (checked 2026-11-15 against the API)

| Place | NO₂ | Air / Water / Earth (17 variables) | Temperature, sunlight, evaporation demand (5) | Fire (2) |
| --- | --- | --- | --- | --- |
| Kyiv city | ✓ | ✓ | ✓ | ✓ (2019–2022) |
| North, South, Central, West, East front | ✓ | ✓ | ✓ | ✓ (2019–2022) |
| Kharkiv city | ✓ | not collected | not collected | not collected |
| Kraków, Prague (comparison) | ✓ | ✓ | ✓ (exported from the monthly panel, 2026-11-15) | not collected |

## How each gap is filled

| Gap | Source and steps | Time |
| --- | --- | --- |
| Fire for Kraków and Prague | NASA FIRMS archive request, VIIRS S-NPP 375 m, one box per city, 2019-03 to 2022-08; then `src.fire_pipeline` with the new boxes | Hours (FIRMS delivery) |
| Fire before 2019 (needed for a fire trend test) | FIRMS archive request for 2015-01 to 2019-02 (VIIRS starts 2012); same pipeline | Hours |
| Weather, water and soil for Kharkiv city | Add the box to `STUDY_BOXES` in `src/weather_power_pipeline.py`, run `python -m src.weather_power_pipeline --fetch` (NASA POWER API), then regenerate the exports and `python -m src.trend_results` | Minutes, needs internet |
| NO₂ for any new place | NASA Giovanni, Time Series Area-Averaged, `OMNO2d_004_ColumnAmountNO2TropCloudScreened`, 2015-03-01 to 2022-08-31; save to `data/frozen/no2_regional/`, add to `NO2_REGIONAL_FILES` | Minutes |

The cards say "Not collected" with the matching step, so the gap is visible in the app.
