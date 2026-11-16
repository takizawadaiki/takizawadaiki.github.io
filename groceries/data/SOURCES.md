# Data sources

All from Statistics Canada, downloaded by `pipeline/fetch.py` on 16 November 2026. Rows from January 2017 are kept.

| File | Table | What it holds |
| --- | --- | --- |
| `prices.csv` | 18-10-0245-01, Monthly average retail prices for selected products | Average price in dollars of 110 products, for Canada, the ten provinces, Whitehorse and Yellowknife, to September 2026 |
| `cpi.csv` | 18-10-0004-01, Consumer Price Index, monthly, not seasonally adjusted | Index (2002 = 100) for all items, food bought in stores, restaurant food and food groups, for Canada and the provinces, to October 2026 |
| `wages.csv` | 14-10-0063-01, Employee wages by industry, monthly, unadjusted | Average hourly wage, all employees aged 15 and over, all industries, full- and part-time, to October 2026 |
| `earnings.csv` | 14-10-0223-01, Employment and average weekly earnings | Average weekly earnings including overtime, all industries. Downloaded as a cross-check and not used on the page |

Statistics Canada notes that the average retail prices are not adjusted for changes in quality or in the brands sold, and that the Consumer Price Index is the measure to use for price change over time.
