# Index Constituent Data

This directory stores raw and derived index composition files used for country-level company mapping and future Plotly choropleth views.

## Layout

- `raw/`: source CSV files moved from the project root.
- `cleaned/`: normalized company-level CSVs with one shared schema.
- `aggregated/`: country-level summary CSVs ready for Plotly `px.choropleth(locations="iso_alpha3")`.

The current raw files are:

- `raw/sp500_dash_plotly_company_map.csv`
- `raw/msci_canada_dash_plotly_company_map.csv`
- `raw/msci_japan_dash_plotly_company_map.csv`
- `raw/Constituent_IE00BTJRMP35_recreated_index_holdings.csv`

The first three raw files are normalized by `scripts/clean_index_constituents.py`.
The `Constituent_IE00BTJRMP35_recreated_index_holdings.csv` file is preserved in `raw/` as additional source data, but it is not yet part of the current cleaned and aggregated outputs.

## Cleaned Company-Level Schema

The cleaned company files are:

- `cleaned/sp500_companies.csv`
- `cleaned/msci_canada_companies.csv`
- `cleaned/msci_japan_companies.csv`
- `cleaned/excluded_non_company_rows.csv`

Each company-level CSV uses this standard schema and column order:

```text
index_id
index_name
security_id
ticker
company_name
security_name
sector
industry
asset_class
currency
isin
weight_pct
market_value_usd
shares
country
iso_alpha3
tax_residence_country
tax_residence_iso_alpha3
tax_country_basis
tax_country_confidence
is_company
is_duplicate_security
source_file
source_row_number
notes
```

Notes:

- `tax_residence_country` is currently a proxy field and is not verified legal tax-residence data.
- `tax_residence_iso_alpha3` is the ISO-3166 alpha-3 code for the current proxy country.
- `is_duplicate_security` is `True` where the same normalized company appears more than once as separate security rows.
- Non-company rows such as cash, FX, futures, collateral, derivatives, and margin lines are excluded from the cleaned company files and written to `cleaned/excluded_non_company_rows.csv` when present.

## Aggregated Country-Count Schema

The aggregated files are:

- `aggregated/sp500_country_counts.csv`
- `aggregated/msci_canada_country_counts.csv`
- `aggregated/msci_japan_country_counts.csv`
- `aggregated/all_indices_country_counts.csv`

Each aggregated CSV uses this schema:

```text
index_id
index_name
country
iso_alpha3
tax_residence_country
tax_residence_iso_alpha3
company_count
security_count
total_weight_pct
tax_country_basis
tax_country_confidence
```

Notes:

- `company_count` is based on unique normalized company names.
- `security_count` counts security rows.
- `total_weight_pct` sums the available `weight_pct` values for each grouped country row.
- The data is ready for Plotly world choropleths using `iso_alpha3`.

## Regeneration

Regenerate the cleaned and aggregated files with:

```bash
python scripts/clean_index_constituents.py
```

This script reads from `raw/` and rewrites the contents of `cleaned/` and `aggregated/`.
