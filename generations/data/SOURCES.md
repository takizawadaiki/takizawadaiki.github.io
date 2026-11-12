# Data sources

All series were retrieved on 12 November 2026 and are stored unchanged in `raw/`. Each file was checked against a checksum computed at the source when it was collected.

## `raw/statcan_series.txt`

Statistics Canada, through the Web Data Service. One series per line: `name|vector|first year|values`. Monthly series are averaged to calendar years.

| Name | Table | What it is |
| --- | --- | --- |
| `cpi_all`, `cpi_rent`, `cpi_tuition`, `cpi_food`, `cpi_gas`, `cpi_owned` | 18-10-0005-01 | Consumer Price Index, annual average, Canada (2002 = 100) |
| `inc_med_total_2534` and the other `inc_` series | 11-10-0239-01 | Median (or average) income of people with income, by age group and gender, in 2024 constant dollars |
| `ur_2529`, `ur_1524`, `ur_2554`, `er_2529`, `ft_2529` | 14-10-0327-01 | Labour Force Survey: unemployment rate, employment rate and share employed full time, by age |
| `mort5` | 34-10-0145-01 | CMHC conventional mortgage lending rate, five-year term |
| `nhpi` | 18-10-0205-01 | New housing price index (collected, not used on the page) |
| `tu_old` | 37-10-0150-01 | Average undergraduate tuition, Canadian students, 1972/73 to 2006/07 |
| `tu_new` | 37-10-0003-01 | Average undergraduate tuition, Canadian students, 2006/07 to 2026/27 |
| `tu_intl` | 37-10-0045-01 | Average undergraduate tuition, international students (collected, not used on the page) |

Tuition years are labelled by the year the academic year starts. The page uses `tu_old` up to 2005/06 and `tu_new` from 2006/07.

## `raw/bis_house_prices.txt`

Bank for International Settlements, residential property prices for Canada, nominal, index 2010 = 100, quarterly, averaged to calendar years. Retrieved from FRED, series `QCAN628BIS`. The 2026 value covers the first quarter only and is not used.

## `raw/cmhc_rents.txt`

Canada Mortgage and Housing Corporation, average rents for areas with a population of 10,000 and over, Statistics Canada table 34-10-0133-01. One-bedroom units, by city, 1987 to 2025. The page uses apartment structures of six units and over (`s4`), which has the longest history.
