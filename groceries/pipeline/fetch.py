"""Download the Statistics Canada tables behind the grocery page and keep the rows it uses.

    python groceries/pipeline/fetch.py out/

Writes small CSV files:
  prices.csv    average retail price of each product, by month and province   (table 18-10-0245-01)
  cpi.csv       consumer price index for food and for all items, by month and province   (table 18-10-0004-01)
  wages.csv     average hourly wage of employees, by month and province   (table 14-10-0063-01)
  earnings.csv  average weekly earnings of employees, by month and province   (table 14-10-0223-01)
"""
from __future__ import annotations

import io
import sys
import time
import zipfile
from pathlib import Path

import pandas as pd
import requests

URL = 'https://www150.statcan.gc.ca/n1/tbl/csv/{pid}-eng.zip'
START = '2017-01'
CPI_KEEP = ['All-items', 'Food', 'Food purchased from stores', 'Food purchased from restaurants', 'Meat', 'Dairy products and eggs', 'Bakery and cereal products (excluding baby food)',
            'Fresh fruit', 'Fresh vegetables', 'Shelter', 'Rented accommodation', 'Gasoline', 'All-items excluding food and energy', 'Fish, seafood and other marine products',
            'Fruit, fruit preparations and nuts', 'Vegetables and vegetable preparations', 'Other food products and non-alcoholic beverages', 'Coffee and tea', 'Sugar and confectionery', 'Edible fats and oils']


def table(pid):
    for attempt in range(4):
        try:
            r = requests.get(URL.format(pid=pid), timeout=600, headers={'User-Agent': 'research (github.com/takizawadaiki)'})
            r.raise_for_status()
            z = zipfile.ZipFile(io.BytesIO(r.content))
            name = [n for n in z.namelist() if n.endswith('.csv') and 'MetaData' not in n][0]
            return z.open(name)
        except Exception as e:           # noqa: BLE001
            print('retry', pid, e)
            time.sleep(10 * (attempt + 1))
    raise RuntimeError(f'could not download {pid}')


def chunks(pid, keep):
    out = []
    for i, c in enumerate(pd.read_csv(table(pid), chunksize=400_000, dtype=str, low_memory=False)):
        if i == 0:
            print(pid, 'columns:', list(c.columns))
        c = c[c['REF_DATE'] >= START]
        out.append(keep(c))
    df = pd.concat(out, ignore_index=True)
    df['VALUE'] = pd.to_numeric(df['VALUE'], errors='coerce')
    return df.dropna(subset=['VALUE'])


def describe(df, cols):
    for c in cols:
        vals = sorted(df[c].dropna().unique())
        print(f'  {c}: {len(vals)} values, e.g. {vals[:12]}')


def main(out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)

    p = chunks('18100245', lambda c: c)
    describe(p, ['GEO', 'Products', 'UOM'])
    p[['REF_DATE', 'GEO', 'Products', 'VALUE']].rename(columns={'REF_DATE': 'month', 'GEO': 'geo', 'Products': 'product', 'VALUE': 'price'}).to_csv(out / 'prices.csv', index=False)
    print('prices', len(p), p['REF_DATE'].min(), p['REF_DATE'].max())

    col = 'Products and product groups'
    c = chunks('18100004', lambda c: c[c[col].isin(CPI_KEEP) & (c['UOM'] == '2002=100')])
    describe(c, ['GEO', col])
    c = c[~c['GEO'].str.contains(',')]                 # provinces and Canada, not cities
    c[['REF_DATE', 'GEO', col, 'VALUE']].rename(columns={'REF_DATE': 'month', 'GEO': 'geo', col: 'item', 'VALUE': 'index'}).to_csv(out / 'cpi.csv', index=False)
    print('cpi', len(c), c['REF_DATE'].max())

    try:
        w = chunks('14100063', lambda c: c)
        cols = [x for x in w.columns if x not in ('REF_DATE', 'DGUID', 'UOM_ID', 'SCALAR_FACTOR', 'SCALAR_ID', 'VECTOR', 'COORDINATE', 'VALUE', 'STATUS', 'SYMBOL', 'TERMINATED', 'DECIMALS')]
        describe(w, cols)
        sel = w
        for name, want in (('Wages', 'Average hourly wage rate'), ('Type of work', 'Both full- and part-time employees'), ('Age group', '15 years and over')):
            if name in sel.columns:
                sel = sel[sel[name] == want]
        for name in sel.columns:
            if name.startswith('National Occupational Classification'):
                sel = sel[sel[name].str.startswith('Total employees')]
            if name in ('Sex', 'Gender'):
                sel = sel[sel[name].isin(['Both sexes', 'Total - Gender'])]
        sel[['REF_DATE', 'GEO', 'VALUE']].rename(columns={'REF_DATE': 'month', 'GEO': 'geo', 'VALUE': 'hourly_wage'}).to_csv(out / 'wages.csv', index=False)
        print('wages', len(sel), sel['REF_DATE'].max(), sel.groupby('GEO').size().head(12).to_dict())
    except Exception as e:               # noqa: BLE001
        print('wages failed:', e)

    try:
        e = chunks('14100223', lambda c: c)
        cols = [x for x in e.columns if x not in ('REF_DATE', 'DGUID', 'UOM_ID', 'SCALAR_FACTOR', 'SCALAR_ID', 'VECTOR', 'COORDINATE', 'VALUE', 'STATUS', 'SYMBOL', 'TERMINATED', 'DECIMALS')]
        describe(e, cols)
        est = [x for x in e.columns if x.startswith('Estimate')][0]
        ind = [x for x in e.columns if 'NAICS' in x][0]
        sel = e[e[est].str.startswith('Average weekly earnings') & e[ind].str.startswith('Industrial aggregate excluding')]
        sel[['REF_DATE', 'GEO', 'VALUE']].rename(columns={'REF_DATE': 'month', 'GEO': 'geo', 'VALUE': 'weekly_earnings'}).to_csv(out / 'earnings.csv', index=False)
        print('earnings', len(sel), sel['REF_DATE'].max())
    except Exception as e:               # noqa: BLE001
        print('earnings failed:', e)


if __name__ == '__main__':
    main(sys.argv[1])
