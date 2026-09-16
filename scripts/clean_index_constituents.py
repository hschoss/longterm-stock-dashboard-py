from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
INDEX_CONSTITUENTS_DIR = PROJECT_ROOT / "data" / "index_constituents"
RAW_DIR = INDEX_CONSTITUENTS_DIR / "raw"
CLEANED_DIR = INDEX_CONSTITUENTS_DIR / "cleaned"
AGGREGATED_DIR = INDEX_CONSTITUENTS_DIR / "aggregated"

COMPANY_COLUMNS = [
    "index_id",
    "index_name",
    "security_id",
    "ticker",
    "company_name",
    "security_name",
    "sector",
    "industry",
    "asset_class",
    "currency",
    "isin",
    "weight_pct",
    "market_value_usd",
    "shares",
    "country",
    "iso_alpha3",
    "tax_residence_country",
    "tax_residence_iso_alpha3",
    "tax_country_basis",
    "tax_country_confidence",
    "is_company",
    "is_duplicate_security",
    "source_file",
    "source_row_number",
    "notes",
]

AGGREGATED_COLUMNS = [
    "index_id",
    "index_name",
    "country",
    "iso_alpha3",
    "tax_residence_country",
    "tax_residence_iso_alpha3",
    "company_count",
    "security_count",
    "total_weight_pct",
    "tax_country_basis",
    "tax_country_confidence",
]

EXCLUDED_COLUMNS = [
    "index_id",
    "source_file",
    "source_row_number",
    "ticker",
    "security_name",
    "asset_class",
    "reason_excluded",
]

NON_COMPANY_KEYWORDS = {
    "cash collateral": "cash collateral",
    "currency cash": "currency cash",
    "index futures": "index futures",
    "derivatives": "derivatives",
    "futures": "futures",
    "margin": "margin",
    "fx": "FX",
    "cash": "cash",
}

PRESERVED_RAW_ONLY_FILES = [
    "Constituent_IE00BTJRMP35_recreated_index_holdings.csv",
]


@dataclass(frozen=True)
class SourceSpec:
    index_id: str
    index_name: str
    raw_filename: str
    cleaned_filename: str
    parser: str


SOURCE_SPECS = (
    SourceSpec("sp500", "S&P 500", "sp500_dash_plotly_company_map.csv", "sp500_companies.csv", "company_map"),
    SourceSpec(
        "msci_canada",
        "MSCI Canada",
        "msci_canada_dash_plotly_company_map.csv",
        "msci_canada_companies.csv",
        "msci_holdings",
    ),
    SourceSpec(
        "msci_japan",
        "MSCI Japan",
        "msci_japan_dash_plotly_company_map.csv",
        "msci_japan_companies.csv",
        "msci_holdings",
    ),
    SourceSpec(
        "stoxx_europe_600", "STOXX Europe 600", "stoxx-600.csv", "stoxx_europe_600_companies.csv", "company_map"
    ),
    SourceSpec(
        "emerging_markets",
        "MSCI Emerging Markets",
        "msci-emering-markets.csv",
        "emerging_markets_companies.csv",
        "company_map",
    ),
)


def _clean_text(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    return re.sub(r"\s+", " ", str(value).strip())


def _normalized_company_key(value: object) -> str:
    cleaned = _clean_text(value).upper()
    cleaned = re.sub(r"[^A-Z0-9 ]+", "", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


def _to_float(value: object) -> float | None:
    if value is None or pd.isna(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _security_id(index_id: str, source_row_number: int, isin: str, ticker: str) -> str:
    if isin:
        return isin
    if ticker:
        return ticker
    return f"{index_id}-{source_row_number}"


def _detect_non_company_reason(asset_class: str, security_name: str, company_name: str, ticker: str) -> str | None:
    haystack = " ".join([asset_class, security_name, company_name, ticker]).lower()
    for keyword, reason in NON_COMPANY_KEYWORDS.items():
        if keyword in haystack:
            return reason
    return None


def _required_raw_path(filename: str) -> Path:
    path = RAW_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"Required raw index constituent file is missing: {path}")
    return path


def _base_company_row(spec: SourceSpec, source_row_number: int) -> dict[str, object]:
    return {
        "index_id": spec.index_id,
        "index_name": spec.index_name,
        "security_id": "",
        "ticker": "",
        "company_name": "",
        "security_name": "",
        "sector": "",
        "industry": "",
        "asset_class": "Equity",
        "currency": "",
        "isin": "",
        "weight_pct": None,
        "market_value_usd": None,
        "shares": None,
        "country": "",
        "iso_alpha3": "",
        "tax_residence_country": "",
        "tax_residence_iso_alpha3": "",
        "tax_country_basis": "",
        "tax_country_confidence": "proxy_only",
        "is_company": True,
        "is_duplicate_security": False,
        "source_file": spec.raw_filename,
        "source_row_number": source_row_number,
        "notes": "",
    }


def _append_excluded_row(
    spec: SourceSpec,
    excluded_rows: list[dict[str, object]],
    source_row_number: int,
    ticker: str,
    security_name: str,
    asset_class: str,
    reason: str,
) -> None:
    excluded_rows.append(
        {
            "index_id": spec.index_id,
            "source_file": spec.raw_filename,
            "source_row_number": source_row_number,
            "ticker": ticker,
            "security_name": security_name,
            "asset_class": asset_class,
            "reason_excluded": reason,
        }
    )


def _normalize_company_map_source(df: pd.DataFrame, spec: SourceSpec) -> tuple[pd.DataFrame, pd.DataFrame]:
    included_rows: list[dict[str, object]] = []
    excluded_rows: list[dict[str, object]] = []

    for source_row_number, row in enumerate(df.to_dict(orient="records"), start=1):
        company_name = _clean_text(row.get("company_name"))
        ticker = _clean_text(row.get("ticker"))
        security_name = company_name
        asset_class = "Equity"
        reason = _detect_non_company_reason(asset_class, security_name, company_name, ticker)
        if reason is not None:
            _append_excluded_row(spec, excluded_rows, source_row_number, ticker, security_name, asset_class, reason)
            continue

        item = _base_company_row(spec, source_row_number)
        country = _clean_text(row.get("map_country") or row.get("headquarters_country"))
        iso_alpha3 = _clean_text(row.get("map_iso_alpha3") or row.get("iso_alpha3"))
        tax_residence_country = _clean_text(row.get("tax_residence_country") or country)
        tax_residence_iso_alpha3 = _clean_text(row.get("tax_residence_iso_alpha3") or iso_alpha3)
        tax_country_basis = _clean_text(row.get("tax_country_basis"))
        if spec.index_id == "stoxx_europe_600" and country and not tax_country_basis:
            tax_country_basis = "holding_country_from_source_not_tax_verified"
        if spec.index_id == "emerging_markets" and not tax_country_basis:
            tax_country_basis = "holding_country_from_source_not_tax_verified"

        item.update(
            {
                "ticker": ticker,
                "company_name": company_name,
                "security_name": security_name,
                "sector": _clean_text(row.get("gics_sector")),
                "industry": _clean_text(row.get("gics_sub_industry")),
                "asset_class": asset_class,
                "currency": _clean_text(row.get("trading_currency")),
                "isin": _clean_text(row.get("isin")),
                "weight_pct": _to_float(row.get("index_weight_pct")),
                "market_value_usd": _to_float(row.get("market_value_usd")),
                "shares": _to_float(row.get("quantity")),
                "country": country,
                "iso_alpha3": iso_alpha3,
                "tax_residence_country": tax_residence_country,
                "tax_residence_iso_alpha3": tax_residence_iso_alpha3,
                "tax_country_basis": tax_country_basis,
                "tax_country_confidence": _clean_text(row.get("tax_country_confidence")) or "proxy_only",
                "notes": _clean_text(row.get("notes")),
            }
        )
        item["security_id"] = _security_id(spec.index_id, source_row_number, item["isin"], ticker)
        included_rows.append(item)

    return pd.DataFrame(included_rows), pd.DataFrame(excluded_rows, columns=EXCLUDED_COLUMNS)


def _normalize_msci_holdings_source(df: pd.DataFrame, spec: SourceSpec) -> tuple[pd.DataFrame, pd.DataFrame]:
    included_rows: list[dict[str, object]] = []
    excluded_rows: list[dict[str, object]] = []

    for source_row_number, row in enumerate(df.to_dict(orient="records"), start=1):
        company_name = _clean_text(row.get("company_name"))
        security_name = _clean_text(row.get("company_name_raw")) or company_name
        ticker = _clean_text(row.get("ticker"))
        asset_class = _clean_text(row.get("security_type")) or "Equity"
        reason = _detect_non_company_reason(asset_class, security_name, company_name, ticker)
        if reason is not None:
            _append_excluded_row(spec, excluded_rows, source_row_number, ticker, security_name, asset_class, reason)
            continue

        item = _base_company_row(spec, source_row_number)
        item.update(
            {
                "ticker": ticker,
                "company_name": company_name,
                "security_name": security_name,
                "sector": _clean_text(row.get("sector")),
                "industry": _clean_text(row.get("gics_sub_industry")),
                "asset_class": asset_class,
                "currency": _clean_text(row.get("trading_currency")),
                "isin": _clean_text(row.get("isin")),
                "weight_pct": _to_float(row.get("index_weight_pct")),
                "market_value_usd": _to_float(row.get("market_value_usd")),
                "shares": _to_float(row.get("quantity")),
                "country": _clean_text(row.get("map_country") or row.get("headquarters_country")),
                "iso_alpha3": _clean_text(row.get("map_iso_alpha3")),
                "tax_residence_country": _clean_text(
                    row.get("tax_residence_country") or row.get("map_country") or row.get("headquarters_country")
                ),
                "tax_residence_iso_alpha3": _clean_text(
                    row.get("tax_residence_iso_alpha3") or row.get("map_iso_alpha3")
                ),
                "tax_country_basis": _clean_text(row.get("tax_country_basis")),
                "tax_country_confidence": _clean_text(row.get("tax_country_confidence")) or "proxy_only",
                "notes": _clean_text(row.get("notes")),
            }
        )
        item["security_id"] = _security_id(spec.index_id, source_row_number, item["isin"], ticker)
        included_rows.append(item)

    return pd.DataFrame(included_rows), pd.DataFrame(excluded_rows, columns=EXCLUDED_COLUMNS)


def _normalize_source(spec: SourceSpec) -> tuple[pd.DataFrame, pd.DataFrame]:
    raw_df = pd.read_csv(_required_raw_path(spec.raw_filename))
    if spec.parser == "company_map":
        normalized_df, excluded_df = _normalize_company_map_source(raw_df, spec)
    elif spec.parser == "msci_holdings":
        normalized_df, excluded_df = _normalize_msci_holdings_source(raw_df, spec)
    else:
        raise ValueError(f"Unsupported parser '{spec.parser}' for {spec.index_id}.")

    normalized_df = normalized_df.reindex(columns=COMPANY_COLUMNS)
    company_keys = normalized_df["company_name"].map(_normalized_company_key)
    normalized_df["is_duplicate_security"] = company_keys.duplicated(keep=False)

    if normalized_df["iso_alpha3"].fillna("").astype(str).str.strip().eq("").any():
        missing_rows = normalized_df.loc[
            normalized_df["iso_alpha3"].fillna("").astype(str).str.strip().eq(""), ["source_file", "source_row_number"]
        ]
        raise ValueError(
            f"Missing iso_alpha3 in normalized rows for {spec.index_id}: {missing_rows.to_dict(orient='records')}"
        )
    if normalized_df["tax_residence_iso_alpha3"].fillna("").astype(str).str.strip().eq("").any():
        missing_rows = normalized_df.loc[
            normalized_df["tax_residence_iso_alpha3"].fillna("").astype(str).str.strip().eq(""),
            ["source_file", "source_row_number"],
        ]
        raise ValueError(
            f"Missing tax_residence_iso_alpha3 in normalized rows for {spec.index_id}: "
            f"{missing_rows.to_dict(orient='records')}"
        )
    return normalized_df, excluded_df.reindex(columns=EXCLUDED_COLUMNS)


def _aggregate_country_counts(company_df: pd.DataFrame) -> pd.DataFrame:
    working = company_df.copy()
    working["normalized_company_key"] = working["company_name"].map(_normalized_company_key)
    aggregated = (
        working.groupby(
            [
                "index_id",
                "index_name",
                "country",
                "iso_alpha3",
                "tax_residence_country",
                "tax_residence_iso_alpha3",
                "tax_country_basis",
                "tax_country_confidence",
            ],
            dropna=False,
            sort=True,
        )
        .agg(
            company_count=("normalized_company_key", "nunique"),
            security_count=("security_id", "size"),
            total_weight_pct=("weight_pct", "sum"),
        )
        .reset_index()
    )
    aggregated = aggregated.reindex(columns=AGGREGATED_COLUMNS)
    aggregated["company_count"] = aggregated["company_count"].astype(int)
    aggregated["security_count"] = aggregated["security_count"].astype(int)
    aggregated["total_weight_pct"] = pd.to_numeric(aggregated["total_weight_pct"], errors="coerce").fillna(0.0)
    return aggregated.sort_values(["index_id", "country", "tax_residence_country"]).reset_index(drop=True)


def _ensure_output_dirs() -> None:
    for path in (CLEANED_DIR, AGGREGATED_DIR):
        path.mkdir(parents=True, exist_ok=True)


def run_cleaning() -> dict[str, list[Path]]:
    _ensure_output_dirs()

    cleaned_paths: list[Path] = []
    aggregated_paths: list[Path] = []
    excluded_frames: list[pd.DataFrame] = []
    all_aggregated_frames: list[pd.DataFrame] = []

    for spec in SOURCE_SPECS:
        company_df, excluded_df = _normalize_source(spec)
        cleaned_path = CLEANED_DIR / spec.cleaned_filename
        company_df.to_csv(cleaned_path, index=False)
        cleaned_paths.append(cleaned_path)

        excluded_frames.append(excluded_df)

        aggregated_df = _aggregate_country_counts(company_df)
        aggregated_path = AGGREGATED_DIR / f"{spec.index_id}_country_counts.csv"
        aggregated_df.to_csv(aggregated_path, index=False)
        aggregated_paths.append(aggregated_path)
        all_aggregated_frames.append(aggregated_df)

    combined_excluded = (
        pd.concat(excluded_frames, ignore_index=True) if excluded_frames else pd.DataFrame(columns=EXCLUDED_COLUMNS)
    )
    combined_excluded = combined_excluded.reindex(columns=EXCLUDED_COLUMNS)
    excluded_path = CLEANED_DIR / "excluded_non_company_rows.csv"
    combined_excluded.to_csv(excluded_path, index=False)
    cleaned_paths.append(excluded_path)

    combined_aggregated = pd.concat(all_aggregated_frames, ignore_index=True).reindex(columns=AGGREGATED_COLUMNS)
    combined_aggregated = combined_aggregated.sort_values(["index_id", "country", "tax_residence_country"]).reset_index(
        drop=True
    )
    combined_aggregated_path = AGGREGATED_DIR / "all_indices_country_counts.csv"
    combined_aggregated.to_csv(combined_aggregated_path, index=False)
    aggregated_paths.append(combined_aggregated_path)

    return {
        "cleaned": cleaned_paths,
        "aggregated": aggregated_paths,
        "preserved_raw_only": [
            RAW_DIR / filename for filename in PRESERVED_RAW_ONLY_FILES if (RAW_DIR / filename).exists()
        ],
    }


if __name__ == "__main__":
    result = run_cleaning()
    print("Cleaned files:")
    for path in result["cleaned"]:
        print(f"- {path.relative_to(PROJECT_ROOT)}")
    print("Aggregated files:")
    for path in result["aggregated"]:
        print(f"- {path.relative_to(PROJECT_ROOT)}")
    print("Preserved raw-only files:")
    for path in result["preserved_raw_only"]:
        print(f"- {path.relative_to(PROJECT_ROOT)}")
