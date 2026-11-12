# Is your generation worse off than your parents'?

Enter two birth years and compare what each person faced at 25 in Canada: pay, house prices, mortgage payments, rent, tuition and the job market, from 1976 to 2025.

**Live page:** https://takizawadaiki.github.io/generations/

## What the page does

- **Scorecard.** Six measures for the year each person turned 25 (tuition at 20), each marked better, worse or about the same.
- **Charts.** Fifty years of each measure, with the two chosen years marked.
- **Every year.** A table that shades each year by how it ranks, to show which groups had it hardest on which measure.

Every dollar figure is in 2025 dollars. The sources are Statistics Canada, CMHC and the Bank for International Settlements.

## Findings

- The median income of 25 to 34 year olds was $54,597 in 1976 and $50,617 in 2024, a fall of 7%. Over the same years the median for 45 to 54 year olds rose 19%.
- The fall is a fall in young men's income (down 24%). Young women's rose 43%.
- The low point for young incomes was 1996, at $39,392.
- After inflation, house prices rose 166% between 1976 and 2025. Against the median young income they stood at three times their 1976 level in 2024.
- Lower interest rates soften that. The mortgage payment on the same share of a home is 1.9 times its 1976 level. Rates peaked at 18.1% in 1981, but the payment burden then was lower than it is today.
- Average undergraduate tuition rose from $2,978 to $7,772 a year, up 161%.
- In Toronto, real rent for a one-bedroom rose 56% between 1987 and 2025, from 29% to 41% of the median young income.
- Unemployment for 25 to 29 year olds is about where it was in 1976 (7.1% then, 7.9% in 2025). The worst year was 1993, at 13.0%.
- No group had it all. Someone born in 2000 is worse off than a parent born in 1970 on four of six measures, but better on income and jobs, because the parent turned 25 in the weak mid-1990s.

## Limits

- These are national medians and averages. Results differ by city, education and family background.
- Income is before tax and per person. More young adults are in school now, and far more women work full time, which changes who is counted.
- The housing measures are indexes set to 100 in 1976. They show movement against income and do not give a price in dollars. The payment index ignores the down payment.
- CMHC rents cover older purpose-built apartments and long-term tenants, so they sit below current asking rents.
- Six measures leave out health, safety, technology and much else.

## Run it

Python 3.9 or later, standard library only.

```
python analysis.py                    # writes data/canada_by_year.csv and results/results.json
python -m unittest discover tests     # 13 checks
```

Sources are listed in [data/SOURCES.md](data/SOURCES.md).
