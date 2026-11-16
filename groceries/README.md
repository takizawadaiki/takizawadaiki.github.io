# What happened to grocery prices?

Live page: https://takizawadaiki.github.io/groceries/

Shelf prices of 110 everyday products in Canada, 2019 against the latest twelve months, set against wages, with a basket you can build and price by province.

## Findings

- Grocery prices (the consumer price index for food bought in stores) rose 35% from the 2019 average to October 2025–September 2026. All consumer prices rose 23%.
- The average hourly wage rose 32%, from $28.31 to $37.30. Wages were ahead of groceries until 2022, fell behind in 2022 and 2023, and have made up part of the gap.
- 46 of 110 products rose faster than wages and 17 rose 50% or more. None is cheaper than in 2019. Beef striploin is up 90%, coffee 81% and ground beef 74%. The middle fresh vegetable rose 16%.
- A typical week's shop of 27 products went from $128.96 to $175.46. On the average wage that is 4 hours 33 minutes of work in 2019 and 4 hours 42 minutes now.
- Food prices rose 33% to 39% in every province, but wages rose 20% in Alberta and 21% in Saskatchewan against 35% or more in Quebec, British Columbia and the Maritimes. The basket takes about 35 minutes more work in Alberta and Saskatchewan and slightly less in Quebec.

## Files

| Path | What it is |
| --- | --- |
| `pipeline/fetch.py` | Downloads four Statistics Canada tables and keeps the rows used here |
| `data/` | Prices, price indexes and wages (see `data/SOURCES.md`) |
| `analysis.py` | Twelve-month averages, changes, minutes of work, baskets; writes `results/results.json` |
| `tests/test_analysis.py` | Six tests |
| `index.html` | The page |

## Limits

Shelf prices are averages across stores and brands, so they also move when shoppers switch brands; the consumer price index is the official measure and is shown beside them. The average wage shifts with the mix of jobs and is before tax. The typical basket is my own list. 2019 is the starting point; another year would give other figures.

```
pip install pytest          # the analysis itself needs only the standard library
python analysis.py
python -m pytest tests
```

The data is refreshed by the workflow in `.github/workflows/grocery-data.yml`.
