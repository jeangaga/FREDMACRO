"""Wages & Income section — price of labor and household income / purchasing power.

Complements the other two tabs:
  Labor     = employment quantity / slack / labor demand
  Inflation = consumer-price inflation
  Wages & Income = wage growth, wage momentum, household income, aggregate labor income

Conventions (shared with the other sections):
  - Every transform is computed on FULL available history, then the display
    window is applied with _trim(). Never filter before differencing.
  - Growth rates are plotted in PERCENTAGE POINTS (3.4 == 3.4%), with the axis
    formatted as tickformat=".1f" + ticksuffix="%".
  - Quarterly series are plotted at their native quarter dates. Nothing is
    interpolated to monthly.
  - No streamlit import: this module runs identically in Colab.

Annualization uses core.transforms.annualized_change (linear, the same one the
Inflation tab uses for "3m annualized"), so the two tabs are comparable.
"""

from __future__ import annotations

from typing import Callable, Literal

import pandas as pd
import plotly.graph_objects as go

import datetime as dt

from core import bea_client, config, inflation_tables, plotting, transforms
from core.fred_client import get_series


# ---- Series registry ---------------------------------------------------------
#
# Every FRED series used by this section, with the metadata needed to use it
# correctly. `transform` says how the raw series becomes a growth rate:
#   "yoy_12" : monthly level  -> 12-month % change
#   "yoy_4"  : quarterly level -> 4-quarter % change
#   "asis"   : FRED already publishes it as a % change from a year ago
#   "level"  : used as a level input (labor income proxy)
SERIES = {
    # --- wages
    "AHETPI":        dict(name="Avg Hourly Earnings, Production & Nonsupervisory", freq="M", units="$ per hour",            transform="yoy_12"),
    "ECIWAG":        dict(name="Employment Cost Index, Wages & Salaries (Private)", freq="Q", units="Index Dec 2005=100",    transform="yoy_4"),
    "PRS85006101":   dict(name="Nonfarm Business Compensation per Hour",             freq="Q", units="% chg from year ago",   transform="asis"),
    # --- household income (BEA, SAAR)
    "PI":            dict(name="Personal Income",                                    freq="M", units="$bn SAAR",              transform="growth"),
    "DSPI":          dict(name="Disposable Personal Income",                         freq="M", units="$bn SAAR",              transform="growth"),
    "DSPIC96":       dict(name="Real Disposable Personal Income",                    freq="M", units="Chained 2017 $bn SAAR", transform="growth"),
    # --- aggregate labor income proxy (all employees, total private — same population)
    "USPRIV":        dict(name="All Employees, Total Private",                       freq="M", units="Thousands",             transform="level"),
    "AWHAETP":       dict(name="Avg Weekly Hours, All Employees, Total Private",     freq="M", units="Hours",                 transform="level"),
    "CES0500000003": dict(name="Avg Hourly Earnings, All Employees, Total Private",  freq="M", units="$ per hour",            transform="level"),
}

DEFAULT_INCOME_START_DATE = "2015-01-01"

IncomeMeasure = Literal["yoy", "3m", "6m"]
MEASURE_LABEL = {"yoy": "YoY", "3m": "3m annualized", "6m": "6m annualized"}

_LEGEND = dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0,
               font=dict(size=13), bgcolor="rgba(0,0,0,0)", title_text="")


# ---- Helpers (private) -------------------------------------------------------

def _trim(obj, start_date: str):
    return obj.loc[obj.index >= pd.to_datetime(start_date)]


def _pct_axis(fig: go.Figure) -> None:
    """Values are percentage points already -> ONE formatting mechanism."""
    fig.update_yaxes(tickformat=".1f", ticksuffix="%", zeroline=True, zerolinewidth=1)


def _growth(series: pd.Series, measure: IncomeMeasure) -> pd.Series:
    """Growth rate in percentage points, computed on the full series."""
    if measure == "yoy":
        return transforms.yoy_change(series, periods=12) * 100.0
    if measure == "3m":
        return transforms.annualized_change(series, periods=3) * 100.0
    if measure == "6m":
        return transforms.annualized_change(series, periods=6) * 100.0
    raise ValueError(f"unknown measure {measure!r}")


def _lines(df: pd.DataFrame, styles: dict[str, dict] | None = None) -> go.Figure:
    """One line per column, native dates, hover in percent."""
    styles = styles or {}
    fig = go.Figure()
    for col in df.columns:
        s = df[col].dropna()
        fig.add_trace(go.Scatter(
            x=s.index, y=s.values, name=col, mode="lines",
            line=styles.get(col, {}),
            hovertemplate="%{x|%b %Y}<br>" + col + ": %{y:.2f}%<extra></extra>",
            showlegend=True,
        ))
    return fig


def _finish(fig: go.Figure, title: str, y_title: str = "Percent, YoY", height: int = 520) -> go.Figure:
    _pct_axis(fig)
    fig.update_yaxes(title_text=y_title)
    fig = plotting.apply_layout(fig, title=title, height=height)
    fig.update_layout(legend=_LEGEND)
    return fig


# ---- Block 1: wage growth ----------------------------------------------------

def wage_growth_frame() -> pd.DataFrame:
    """Three wage measures in YoY percent, on a union index (monthly + quarterly)."""
    ahe = transforms.yoy_change(get_series("AHETPI").dropna(), periods=12) * 100.0
    eci = transforms.yoy_change(get_series("ECIWAG").dropna(), periods=4) * 100.0
    comp = get_series("PRS85006101").dropna()          # already % change from year ago — NOT re-transformed
    return pd.concat({
        "AHE (Production & Nonsupervisory) — YoY": ahe,
        "ECI Wages & Salaries (Private) — YoY": eci,
        "Nonfarm Business Compensation per Hour — YoY": comp,
    }, axis=1).sort_index()


def wage_growth(start_date: str = DEFAULT_INCOME_START_DATE) -> go.Figure:
    df = _trim(wage_growth_frame(), start_date)
    fig = _lines(df, styles={
        "AHE (Production & Nonsupervisory) — YoY": dict(color="#1f3b63", width=2.2),
        "ECI Wages & Salaries (Private) — YoY": dict(color="#5b84b1", width=2.0),
        "Nonfarm Business Compensation per Hour — YoY": dict(color="#a6a6a6", width=1.6, dash="dot"),
    })
    plotting.add_last_value_annotation(fig, df.iloc[:, 0], fmt="{:.1f}%", scale=1.0)
    return _finish(fig, "U.S. Wage Growth")


# ---- Block 2: AHE momentum ---------------------------------------------------

def ahe_momentum_frame() -> pd.DataFrame:
    s = get_series("AHETPI").dropna()
    return pd.concat({
        "AHE — YoY": _growth(s, "yoy"),
        "AHE — 6m annualized": _growth(s, "6m"),
        "AHE — 3m annualized": _growth(s, "3m"),
    }, axis=1)


def ahe_momentum(start_date: str = DEFAULT_INCOME_START_DATE) -> go.Figure:
    df = _trim(ahe_momentum_frame(), start_date)
    fig = _lines(df, styles={
        "AHE — YoY": dict(color="#1f3b63", width=2.4),
        "AHE — 6m annualized": dict(color="#5b84b1", width=1.8),
        "AHE — 3m annualized": dict(color="#a6a6a6", width=1.5),
    })
    plotting.add_last_value_annotation(fig, df["AHE — YoY"], fmt="{:.1f}%", scale=1.0)
    return _finish(fig, "Average Hourly Earnings — Momentum", y_title="Percent, annualized")


# ---- Block 3: household income -----------------------------------------------

def household_income_frame(measure: IncomeMeasure = "yoy") -> pd.DataFrame:
    label = MEASURE_LABEL[measure]
    return pd.concat({
        f"Personal Income — {label}": _growth(get_series("PI").dropna(), measure),
        f"Disposable Personal Income — {label}": _growth(get_series("DSPI").dropna(), measure),
        f"Real Disposable Personal Income — {label}": _growth(get_series("DSPIC96").dropna(), measure),
    }, axis=1)


def household_income(start_date: str = DEFAULT_INCOME_START_DATE, measure: IncomeMeasure = "yoy") -> go.Figure:
    df = _trim(household_income_frame(measure), start_date)
    cols = list(df.columns)
    fig = _lines(df, styles={
        cols[0]: dict(color="#a6a6a6", width=1.6),
        cols[1]: dict(color="#5b84b1", width=2.0),
        cols[2]: dict(color="#1f3b63", width=2.4),
    })
    plotting.add_last_value_annotation(fig, df[cols[2]], fmt="{:.1f}%", scale=1.0)
    y_title = "Percent, YoY" if measure == "yoy" else "Percent, annualized"
    return _finish(fig, f"Household Income Growth — {MEASURE_LABEL[measure]}", y_title=y_title)


# ---- Block 4: aggregate labor income proxy -----------------------------------

def labor_income_index() -> pd.Series:
    """Employment x weekly hours x hourly earnings (all employees, total private), 100 = first valid month.

    USPRIV starts in 1939 but AWHAETP / CES0500000003 start in March 2006, so
    the index starts there.
    """
    emp = get_series("USPRIV")
    hours = get_series("AWHAETP")
    ahe = get_series("CES0500000003")
    levels = pd.concat([emp, hours, ahe], axis=1, join="inner").dropna()
    raw = levels.iloc[:, 0] * levels.iloc[:, 1] * levels.iloc[:, 2]
    idx = raw / raw.iloc[0] * 100.0
    idx.name = "Aggregate Labor Income (index)"
    return idx


def labor_income_frame() -> pd.DataFrame:
    idx = labor_income_index()
    return pd.concat({
        "Aggregate Labor Income — YoY": _growth(idx, "yoy"),
        "Aggregate Labor Income — 3m annualized": _growth(idx, "3m"),
    }, axis=1)


def labor_income(start_date: str = DEFAULT_INCOME_START_DATE) -> go.Figure:
    df = _trim(labor_income_frame(), start_date)
    fig = _lines(df, styles={
        "Aggregate Labor Income — YoY": dict(color="#1f3b63", width=2.4),
        "Aggregate Labor Income — 3m annualized": dict(color="#a6a6a6", width=1.6),
    })
    plotting.add_last_value_annotation(fig, df["Aggregate Labor Income — YoY"], fmt="{:.1f}%", scale=1.0)
    return _finish(fig, "Aggregate Labor Income — Growth", y_title="Percent")


# ---- Blocks 5-6: consumer spending -------------------------------------------
#
# Real PCE spending detail comes from BEA NIPA table 2.4.6U (real PCE by type
# of product, millions of chained 2017 dollars, SAAR, monthly) through the
# shared BEA client. FRED carries this detail at quarterly frequency only.
# `bea` is the 2.4.6U SeriesCode (real = "...RX"; the two derived core
# aggregates are LB000062 / LB000063). Mapping to the reference table:
#   Home furnishings   -> Furnishings and durable household equipment (DFDHRX)
#   Recreational goods -> Recreational goods and vehicles (DREQRX)
#   Apparel            -> Clothing and footwear (DCLORX)
#   Housing            -> Housing (DHSGRX; excludes household utilities)
#   Food services      -> Food services and accommodations (DFSARX)
#   Core Goods         -> PCE goods excluding food and energy (LB000062)
#   Core Services      -> PCE services excluding energy (LB000063)

REAL_PCE_ROWS = [
    dict(label="Headline",             bea="DPCERX",   level=0, bold=True),
    dict(label="ex Food and Energy",   bea="DPCCRX",   level=0, bold=True),
    dict(label="Core Goods",           bea="LB000062", level=1, bold=True),
    dict(label="Motor vehicles",       bea="DMOTRX",   level=2),
    dict(label="Home furnishings",     bea="DFDHRX",   level=2),
    dict(label="Recreational goods",   bea="DREQRX",   level=2),
    dict(label="Other durables",       bea="DODGRX",   level=2),
    dict(label="Apparel",              bea="DCLORX",   level=2),
    dict(label="Other nondurables",    bea="DONGRX",   level=2),
    dict(label="Core Services",        bea="LB000063", level=1, bold=True),
    dict(label="Housing",              bea="DHSGRX",   level=2),
    dict(label="Health care",          bea="DHLCRX",   level=2),
    dict(label="Transportation",       bea="DTRSRX",   level=2),
    dict(label="Recreation",           bea="DRCARX",   level=2),
    dict(label="Food services",        bea="DFSARX",   level=2),
    dict(label="Financial services",   bea="DIFSRX",   level=2),
    dict(label="Other services",       bea="DOTSRX",   level=2),
]

REAL_PCE_TABLE_MONTHS = 3
REAL_PCE_TABLE_CAPTION = (
    "Month-on-month percent change of real (chained 2017 dollar) personal consumption expenditures, "
    "seasonally adjusted, BEA NIPA table 2.4.6U via the BEA API. Core Goods = goods excluding food and "
    "energy; Core Services = services excluding energy services. Shading is symmetric around zero: "
    "warm = growth, green = decline."
)


def _real_pce_rows() -> list[inflation_tables.TableRow]:
    year = dt.date.today().year
    codes = {s["bea"]: s["bea"] for s in REAL_PCE_ROWS}
    levels = bea_client.get_table_series(bea_client.TABLE_PCE_REAL, codes, start_year=year - 2)
    rows = []
    for spec in REAL_PCE_ROWS:
        mm, note = None, ""
        try:
            mm = inflation_tables.mm_pct(levels[spec["bea"]])
        except Exception as e:  # noqa: BLE001
            note = f"{type(e).__name__}: {e}"
        rows.append(inflation_tables.TableRow(spec["label"], mm, None, spec["level"], spec.get("bold", False), note))
    return rows


def real_pce_table(n_months: int = REAL_PCE_TABLE_MONTHS) -> inflation_tables.InflationTable:
    """Latest `n_months` m/m % changes of real PCE by category (no weight column)."""
    return inflation_tables.build_inflation_table(_real_pce_rows(), n_months=n_months, include_weight=False)


def real_pce_growth_frame() -> pd.DataFrame:
    """Total real PCE (FRED PCEC96): YoY and 6m annualized, percent, full history.

    6m annualized = ((x_t / x_{t-6}) ** 2 - 1) * 100  (transforms.compound_annualized_change).
    """
    s = get_series("PCEC96").dropna()
    return pd.concat({
        "Real PCE — YoY": transforms.yoy_change(s, periods=12) * 100.0,
        "Real PCE — 6m annualized": transforms.compound_annualized_change(s, periods=6),
    }, axis=1)


def real_pce_growth(start_date: str = DEFAULT_INCOME_START_DATE) -> go.Figure:
    df = _trim(real_pce_growth_frame(), start_date)
    fig = _lines(df, styles={
        "Real PCE — YoY": dict(color="#1f3b63", width=2.4),
        "Real PCE — 6m annualized": dict(color="#a6a6a6", width=1.6),
    })
    for col, ay in (("Real PCE — YoY", -25), ("Real PCE — 6m annualized", 25)):
        plotting.add_last_value_annotation(fig, df[col], fmt="{:.1f}%", scale=1.0, ay=ay)
    return _finish(fig, "Real Consumer Spending — YoY vs 6-Month Annualized", y_title="Percent")


def _safe_table_entry(chart_id: str, title: str, commentary: str, builder: Callable[[], inflation_tables.InflationTable], **extra) -> dict:
    """Like _safe_entry, but the payload is pre-rendered table HTML (rendered by app.py with st.markdown)."""
    entry = {"id": chart_id, "title": title, "commentary": commentary, **extra}
    try:
        tbl = builder()
        entry["html"] = inflation_tables.table_html(tbl)
        missing = [f"{tbl.df.loc[i, 'Category']} ({n})" for i, n in enumerate(tbl.notes) if n]
        if missing:
            entry["commentary"] += " Rows without data: " + "; ".join(missing) + "."
    except RuntimeError as e:
        if "API_KEY" in str(e) and "BEA" not in str(e):
            raise
        entry["html"], entry["error"] = None, f"{type(e).__name__}: {e}"
    except Exception as e:  # noqa: BLE001
        entry["html"], entry["error"] = None, f"{type(e).__name__}: {e}"
    return entry


# ---- Section assembler -------------------------------------------------------

def _safe_entry(chart_id: str, title: str, commentary: str, builder: Callable[[], go.Figure]) -> dict:
    """Build one chart; a failure degrades to a warning on that chart only.

    A missing FRED key is re-raised so app.py can show the configuration hint,
    exactly as the other sections do.
    """
    entry = {"id": chart_id, "title": title, "commentary": commentary}
    try:
        entry["fig"] = builder()
    except RuntimeError as e:
        if "API_KEY" in str(e):
            raise
        entry["fig"], entry["error"] = None, f"{type(e).__name__}: {e}"
    except Exception as e:  # noqa: BLE001
        entry["fig"], entry["error"] = None, f"{type(e).__name__}: {e}"
    return entry


def build(
    start_date: str = DEFAULT_INCOME_START_DATE,
    income_measure: IncomeMeasure = "yoy",
) -> dict:
    """Build the Wages & Income section. Same shape as labor.build() / inflation.build()."""
    charts = [
        _safe_entry(
            "wage_growth", "Wage Growth",
            "Compares establishment-based hourly earnings (monthly) with broader quarterly measures of "
            "labor compensation. ECI is less affected by changes in employment composition. Nonfarm business "
            "compensation per hour is plotted as published by BLS (percent change from a year ago). "
            "Quarterly points sit on quarter dates; nothing is interpolated.",
            lambda: wage_growth(start_date),
        ),
        _safe_entry(
            "ahe_momentum", "Average Hourly Earnings — Momentum",
            "Short-horizon annualized changes help identify acceleration or deceleration before it is fully "
            "visible in the year-over-year rate. All three rates are computed on full history, then trimmed.",
            lambda: ahe_momentum(start_date),
        ),
        _safe_entry(
            "household_income", "Household Income Growth",
            "Real disposable income measures household purchasing power after taxes and inflation. "
            "Personal income and disposable income are nominal. Switch between YoY and 3m / 6m annualized "
            "in the sidebar.",
            lambda: household_income(start_date, income_measure),
        ),
        _safe_entry(
            "labor_income", "Aggregate Labor Income",
            "Proxy combines private employment, average weekly hours and average hourly earnings "
            "(all employees, total private) into one index, 100 at March 2006. Combines employment, working "
            "hours and hourly pay to approximate aggregate private-sector labor-income growth.",
            lambda: labor_income(start_date),
        ),
        _safe_table_entry(
            "real_pce_table", "Real PCE Spending — Monthly Change",
            REAL_PCE_TABLE_CAPTION,
            real_pce_table,
            heading="Consumer Spending",
        ),
        _safe_entry(
            "real_pce_growth", "Real Consumer Spending — YoY vs 6-Month Annualized",
            "Total real personal consumption expenditures (FRED PCEC96, chained 2017 dollars). YoY = 12-month "
            "change; 6m annualized = compounded 6-month change. Both are computed on full history, then trimmed "
            "to the Wages & Income start date.",
            lambda: real_pce_growth(start_date),
        ),
    ]
    return {"title": "Wages & Income", "charts": charts}
