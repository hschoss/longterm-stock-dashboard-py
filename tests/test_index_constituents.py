import importlib.util
import sys
from pathlib import Path
import re

import pandas as pd
import pytest

from app.charts.plotly_charts import build_etf_country_exposure_map, build_index_country_choropleth
from app.services.data_service import (
    load_all_index_country_counts,
    load_index_companies,
    load_index_country_counts,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "clean_index_constituents.py"
INDEX_DIR = PROJECT_ROOT / "data" / "index_constituents"
CLEANED_DIR = INDEX_DIR / "cleaned"
AGGREGATED_DIR = INDEX_DIR / "aggregated"
EXPECTED_COMPANY_COLUMNS = [
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
EXPECTED_AGGREGATED_COLUMNS = [
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
NON_COMPANY_PATTERN = re.compile(r"\bcash collateral\b|\bcurrency cash\b|\bindex futures\b|\bderivatives\b|\bfutures\b|\bmargin\b|\bfx\b|\bcash\b")
TARGET_INDEX_IDS = ("sp500", "msci_canada", "msci_japan")


def _load_cleaning_module():
    spec = importlib.util.spec_from_file_location("clean_index_constituents", SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load clean_index_constituents.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="session")
def cleaning_result():
    module = _load_cleaning_module()
    result = module.run_cleaning()
    return {"module": module, "result": result}


@pytest.fixture(scope="session")
def cleaned_company_frames(cleaning_result):
    frames = {}
    for index_id in TARGET_INDEX_IDS:
        frames[index_id] = load_index_companies(index_id)
    return frames


def test_cleaning_script_creates_all_expected_outputs(cleaning_result):
    result = cleaning_result["result"]
    expected_cleaned = {
        CLEANED_DIR / "sp500_companies.csv",
        CLEANED_DIR / "msci_canada_companies.csv",
        CLEANED_DIR / "msci_japan_companies.csv",
        CLEANED_DIR / "excluded_non_company_rows.csv",
    }
    expected_aggregated = {
        AGGREGATED_DIR / "sp500_country_counts.csv",
        AGGREGATED_DIR / "msci_canada_country_counts.csv",
        AGGREGATED_DIR / "msci_japan_country_counts.csv",
        AGGREGATED_DIR / "all_indices_country_counts.csv",
    }

    assert expected_cleaned.issubset(set(result["cleaned"]))
    assert expected_aggregated.issubset(set(result["aggregated"]))
    assert all(path.exists() for path in expected_cleaned | expected_aggregated)


def test_cleaned_company_csvs_share_identical_schema(cleaned_company_frames):
    for frame in cleaned_company_frames.values():
        assert list(frame.columns) == EXPECTED_COMPANY_COLUMNS


def test_non_company_rows_are_excluded_from_cleaned_company_files(cleaned_company_frames):
    for frame in cleaned_company_frames.values():
        haystack = (
            frame[["asset_class", "security_name", "company_name", "ticker"]]
            .fillna("")
            .astype(str)
            .agg(" ".join, axis=1)
            .str.lower()
        )
        assert not haystack.str.contains(NON_COMPANY_PATTERN).any()

    excluded = pd.read_csv(CLEANED_DIR / "excluded_non_company_rows.csv")
    assert list(excluded.columns) == [
        "index_id",
        "source_file",
        "source_row_number",
        "ticker",
        "security_name",
        "asset_class",
        "reason_excluded",
    ]


def test_iso_codes_are_populated_for_all_included_rows(cleaned_company_frames):
    for frame in cleaned_company_frames.values():
        assert frame["iso_alpha3"].fillna("").astype(str).str.strip().ne("").all()
        assert frame["tax_residence_iso_alpha3"].fillna("").astype(str).str.strip().ne("").all()


def test_duplicate_security_rows_are_flagged(cleaned_company_frames):
    canada = cleaned_company_frames["msci_canada"]
    duplicates = canada.loc[canada["company_name"].eq("Constellation Software Inc.")]
    assert len(duplicates) == 2
    assert duplicates["is_duplicate_security"].all()


def test_aggregated_country_count_files_have_expected_schema(cleaning_result):
    per_index_frames = [load_index_country_counts(index_id) for index_id in TARGET_INDEX_IDS]
    for frame in per_index_frames:
        assert list(frame.columns) == EXPECTED_AGGREGATED_COLUMNS
        assert {"company_count", "security_count", "total_weight_pct"}.issubset(frame.columns)
        assert (frame["company_count"] > 0).all()
        assert (frame["security_count"] > 0).all()
        assert (frame["company_count"] <= frame["security_count"]).all()

    combined = load_all_index_country_counts()
    assert list(combined.columns) == EXPECTED_AGGREGATED_COLUMNS
    assert len(combined) == sum(len(frame) for frame in per_index_frames)


def test_index_company_loaders_work_for_supported_indices(cleaned_company_frames):
    for index_id, frame in cleaned_company_frames.items():
        assert not frame.empty
        assert frame["index_id"].eq(index_id).all()


def test_invalid_index_id_raises_clear_error():
    with pytest.raises(ValueError, match="Unsupported index_id"):
        load_index_companies("not_an_index")

    with pytest.raises(ValueError, match="Unsupported index_id"):
        load_index_country_counts("not_an_index")


def test_build_etf_country_exposure_map_returns_choropleth_figure_for_selected_index(cleaning_result):
    country_counts = load_all_index_country_counts()
    sp500_counts = load_index_country_counts("sp500")
    figure = build_etf_country_exposure_map(country_counts, selected_index_id="sp500", color_metric="company_count")

    assert figure is not None
    assert len(figure.data) == 1
    trace = figure.data[0]
    assert trace.type == "choropleth"
    assert trace.name == "S&P 500"
    assert set(trace.locations) == set(sp500_counts["iso_alpha3"])


def test_build_etf_country_exposure_map_overview_uses_choropleth_traces_only(cleaning_result):
    country_counts = load_all_index_country_counts()
    figure = build_etf_country_exposure_map(country_counts, selected_index_id=None, color_metric="company_count")

    assert len(figure.data) >= len(TARGET_INDEX_IDS)
    assert all(trace.type == "choropleth" for trace in figure.data)
    assert not any(trace.type == "scattergeo" for trace in figure.data)


def test_build_etf_country_exposure_map_hover_includes_company_and_total_weight(cleaning_result):
    country_counts = load_index_country_counts("sp500")
    figure = build_etf_country_exposure_map(country_counts, selected_index_id="sp500", color_metric="company_count")

    trace = figure.data[0]
    assert "Company count" in trace.hovertemplate
    assert "Total weight %" in trace.hovertemplate
    assert "Tax-country basis" in trace.hovertemplate


def test_build_index_country_choropleth_returns_plotly_figure(cleaning_result):
    country_counts = load_index_country_counts("sp500")
    figure = build_index_country_choropleth(country_counts)

    assert figure is not None
    assert len(figure.data) == 1
    assert figure.data[0].type == "choropleth"
    assert figure.data[0].colorbar.title.text == "Company count"
