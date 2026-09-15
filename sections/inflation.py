"""Inflation section — CPI dashboard.

Design choices preserved from the original Colab function:
  - YoY and 3m-annualized are computed on the FULL history, then the display
    window is filtered after. This avoids losing the first 12 months of
    real YoY data at the start of the chosen window.
  - No Plotly legend: legends shrink the plotting area. Instead, each panel
    gets a text "pseudo-legend" placed in paper coordinates between panels.
  - Last-release arrow annotation on the primary series of each panel.
"""

from __future__ import annotations

from typing import Optional

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

import datetime as dt

from core import bea_client, bls_client, config, inflation_tables, plotting, transforms
from core.fred_client import get_series


# ---- FRED mnemonics ----------------------------------------------------------

# Panel 1: headline + core + major buckets
HEADLINE_AND_BUCKETS = [
    ("CPIAUCSL",        "CPI"),
    ("CPILFESL",        "Core CPI"),
    ("CUSR0000SASLE",   "Services CPI"),
    ("CUUR0000SACL1E",  "Goods CPI"),
    ("CPIUFDSL",        "Foods CPI"),
    # Energy is fetched but not plotted in panel 1 of the original; available if you want it.
    ("CPIENGSL",        "Energy CPI"),
]

# Panel 2: services breakdown
SERVICES_BREAKDOWN = [
    ("CUSR0000SASLE",   "Services CPI"),
    ("CUSR0000SAH1",    "Shelter CPI"),
    ("CUSR0000SAM2",    "Medical Svc CPI"),
    ("CUUR0000SAS4",    "Transport Svc CPI"),
    ("CPIEDUSL",        "Edu Comm Svc CPI"),
    ("CPIRECSL",        "Recreation Svc CPI"),
    ("CPIOGSSL",        "Other Svc CPI"),
]

# Panel 3: 3m annualized momentum
MOMENTUM_SERIES = [
    ("CPIAUCSL",  "CPI 3m ann"),
    ("CPILFESL",  "Core CPI 3m ann"),
]

# CPI dashboard defaults to a longer history than the labor section.
CPI_DEFAULT_START = "2015-08-01"


# ---- Helpers (private) -------------------------------------------------------

def _yoy_frame(specs: list[tuple[str, str]]) -> pd.DataFrame:
    """Fetch each (series_id, name) in `specs`, compute YoY on full history,
    and return a single DataFrame indexed by date with one column per name."""
    cols = {}
    for series_id, name in specs:
        s = get_series(series_id)
        cols[name] = transforms.yoy_change(s, drop_initial=True)
    df = pd.concat(cols, axis=1).dropna(how="all")
    return df


def _ann_frame(specs: list[tuple[str, str]], periods: int = 3) -> pd.DataFrame:
    cols = {}
    for series_id, name in specs:
        s = get_series(series_id)
        cols[name] = transforms.annualized_change(s, periods=periods, drop_initial=True)
    df = pd.concat(cols, axis=1).dropna(how="all")
    return df


def _trim(df: pd.DataFrame, start_date: str) -> pd.DataFrame:
    return df.loc[df.index >= pd.to_datetime(start_date)].copy()

# ---- Presentation constants (display only — no effect on data) ---------------

# Legend labels. Keys are the DataFrame column names produced by the series
# specs above; values are what the user sees in the Plotly legend.
DISPLAY_NAMES = {
    "CPI": "CPI",
    "Core CPI": "Core CPI",
    "Services CPI": "Services CPI",
    "Goods CPI": "Goods CPI",
    "Foods CPI": "Food CPI",
    "Shelter CPI": "Shelter",
    "Medical Svc CPI": "Medical Care",
    "Transport Svc CPI": "Transportation Services",
    "Edu Comm Svc CPI": "Education & Communication",
    "Recreation Svc CPI": "Recreation",
    "Other Svc CPI": "Other Services",
    "CPI 3m ann": "Headline CPI — 3m annualized",
    "Core CPI 3m ann": "Core CPI — 3m annualized",
}

PANEL_TITLES = (
    "Headline & Major CPI Components — YoY",
    "Core Services Breakdown — YoY",
    "Inflation Momentum — 3m Annualized",
)

DASHBOARD_TITLE = "U.S. CPI Dashboard — Inflation Level & Momentum"
DASHBOARD_CAPTION = (
    "Rates are computed on full available history before applying the selected display window."
)

_LEGEND_FONT = 13
_PANEL_TITLE_FONT = 16


def _label(col: str) -> str:
    return DISPLAY_NAMES.get(col, col)


def _percent_axis(fig: go.Figure, **kwargs) -> None:
    """Percent y-axis using ONE formatting mechanism.

    The underlying values are decimals (0.034 == 3.4%), so ``tickformat=".1%"``
    does both the scaling and the suffix. Adding ``ticksuffix="%"`` on top of it
    is what produced the ``12.0%%`` labels.
    """
    fig.update_yaxes(tickformat=".1%", **kwargs)


def _legend_style(**overrides) -> dict:
    base = dict(
        orientation="h",
        font=dict(size=_LEGEND_FONT),
        bgcolor="rgba(0,0,0,0)",
        title_text="",
        xanchor="left",
        x=0,
    )
    base.update(overrides)
    return base


# ---- Individual chart functions ---------------------------------------------

def cpi_headline_yoy(start_date: str = CPI_DEFAULT_START) -> go.Figure:
    """Panel 1 standalone: headline/core CPI + major buckets, YoY %."""
    df = _trim(_yoy_frame(HEADLINE_AND_BUCKETS), start_date)
    plot_cols = ["CPI", "Core CPI", "Services CPI", "Goods CPI", "Foods CPI"]

    fig = go.Figure()
    for col in plot_cols:
        fig.add_trace(go.Scatter(x=df.index, y=df[col], name=_label(col), mode="lines", showlegend=True))

    plotting.add_last_value_annotation(fig, df["CPI"])
    _percent_axis(fig)
    fig = plotting.apply_layout(fig, title=PANEL_TITLES[0], height=520)
    fig.update_layout(legend=_legend_style(yanchor="bottom", y=1.02))
    return fig


def cpi_services_breakdown(start_date: str = CPI_DEFAULT_START) -> go.Figure:
    """Panel 2 standalone: services CPI broken into sub-categories, YoY %."""
    df = _trim(_yoy_frame(SERVICES_BREAKDOWN), start_date)
    plot_cols = [name for _, name in SERVICES_BREAKDOWN]

    fig = go.Figure()
    for col in plot_cols:
        fig.add_trace(go.Scatter(x=df.index, y=df[col], name=_label(col), mode="lines", showlegend=True))

    plotting.add_last_value_annotation(fig, df["Services CPI"])
    _percent_axis(fig)
    fig = plotting.apply_layout(fig, title=PANEL_TITLES[1], height=520)
    fig.update_layout(legend=_legend_style(yanchor="bottom", y=1.02))
    return fig


def cpi_momentum(start_date: str = CPI_DEFAULT_START) -> go.Figure:
    """Panel 3 standalone: 3-month annualized headline & core CPI."""
    df = _trim(_ann_frame(MOMENTUM_SERIES, periods=3), start_date)

    fig = go.Figure()
    for col in df.columns:
        fig.add_trace(go.Scatter(x=df.index, y=df[col], name=_label(col), mode="lines", showlegend=True))

    plotting.add_last_value_annotation(fig, df["CPI 3m ann"])
    _percent_axis(fig)
    fig = plotting.apply_layout(fig, title=PANEL_TITLES[2], height=520)
    fig.update_layout(legend=_legend_style(yanchor="bottom", y=1.02))
    return fig


def cpi_dashboard(start_date: str = CPI_DEFAULT_START) -> go.Figure:
    """Combined 3-panel CPI dashboard, single column.

    Data logic (unchanged):
      - YoY/3m-ann computed on FULL history, display filtered after
      - Last-release arrow on the primary series of each panel

    Presentation:
      - Each panel gets its own native, clickable Plotly legend (legend /
        legend2 / legend3, Plotly >= 5.15), anchored directly above its plot.
      - Each panel gets a readable title above the legend.
      - Vertical order per panel is TITLE -> LEGEND -> PLOT.
    """
    yoy_all = _yoy_frame(HEADLINE_AND_BUCKETS + SERVICES_BREAKDOWN)
    ann_all = _ann_frame(MOMENTUM_SERIES, periods=3)

    df_main = _trim(yoy_all, start_date)
    df_svc = _trim(yoy_all, start_date)
    df_3m = _trim(ann_all, start_date)

    # ---- Vertical geometry (paper coordinates, 0..1 inside the margins) -----
    # Each panel reserves `header` above its plot area for title + legend. The
    # plot areas themselves are ~25% of the paper height each, the same as
    # the previous layout, so no plotting area is lost.
    header = 0.08
    plot_h = (1.0 - 3 * header) / 3
    domains = []
    top = 1.0
    for _ in range(3):
        top -= header
        domains.append((top - plot_h, top))
        top -= plot_h

    fig = make_subplots(rows=3, cols=1, shared_xaxes=False, vertical_spacing=0.0)

    # ---- Panel 1: headline & buckets
    p1_cols = ["CPI", "Core CPI", "Services CPI", "Goods CPI", "Foods CPI"]
    for c in p1_cols:
        fig.add_trace(
            go.Scatter(x=df_main.index, y=df_main[c], mode="lines", name=_label(c),
                       showlegend=True, legend="legend"),
            row=1, col=1,
        )
    plotting.add_last_value_annotation(fig, df_main["CPI"], row=1, col=1)

    # ---- Panel 2: services breakdown
    p2_cols = [name for _, name in SERVICES_BREAKDOWN]
    for c in p2_cols:
        fig.add_trace(
            go.Scatter(x=df_svc.index, y=df_svc[c], mode="lines", name=_label(c),
                       showlegend=True, legend="legend2"),
            row=2, col=1,
        )
    plotting.add_last_value_annotation(fig, df_svc["Services CPI"], row=2, col=1)

    # ---- Panel 3: 3m annualized
    p3_cols = ["CPI 3m ann", "Core CPI 3m ann"]
    for c in p3_cols:
        fig.add_trace(
            go.Scatter(x=df_3m.index, y=df_3m[c], mode="lines", name=_label(c),
                       showlegend=True, legend="legend3"),
            row=3, col=1,
        )
    plotting.add_last_value_annotation(fig, df_3m["CPI 3m ann"], row=3, col=1)

    # ---- Axes: one percent mechanism, explicit domains
    for r, (lo, hi) in enumerate(domains, start=1):
        _percent_axis(fig, row=r, col=1)
        fig.update_yaxes(domain=[lo, hi], row=r, col=1)

    # ---- Per-panel titles (above legend) and legends (above plot)
    legends = {}
    for i, ((lo, hi), name) in enumerate(zip(domains, PANEL_TITLES)):
        fig.add_annotation(
            x=0, y=hi + 0.052, xref="paper", yref="paper",
            xanchor="left", yanchor="bottom",
            text=f"<b>{name}</b>", showarrow=False,
            font=dict(size=_PANEL_TITLE_FONT),
        )
        key = "legend" if i == 0 else f"legend{i + 1}"
        legends[key] = _legend_style(yanchor="bottom", y=hi + 0.006)

    # ---- Main title + caption, both in the top margin, left-aligned with plots
    height, margin_t, margin_b = 1750, 100, 60
    plot_px = height - margin_t - margin_b
    fig.add_annotation(
        x=0, y=1.0 + 26 / plot_px, xref="paper", yref="paper",
        xanchor="left", yanchor="bottom",
        text=DASHBOARD_CAPTION, showarrow=False,
        font=dict(size=12, color="#666"),
    )

    fig.update_layout(
        title=dict(
            text=DASHBOARD_TITLE,
            x=0, xanchor="left", xref="paper",
            # title.y must be in [0, 1]: express the same 52 px offset in container coords
            y=(height - margin_t + 52) / height, yanchor="bottom", yref="container",
            font=dict(size=20),
        ),
        template="plotly_white",
        height=height,
        margin=dict(l=60, r=30, t=margin_t, b=margin_b),
        showlegend=True,
        **legends,
    )
    return fig


# ---- Contribution charts (BLS weights, N-month annualized) -------------------
#
# Two charts share one engine:
#   * Headline CPI = Core + Food + Energy
#   * Core CPI     = Used & New Cars + Other Core Goods + Rent & OER + Other Core Services
#
# Method (mirrors the research notebook):
#   1. SA index levels from BLS -> compound N-month annualized rate, percent.
#   2. NSA relative-importance weights from BLS (percent of the all-items basket).
#   3. contribution_c = rate_c x weight_c(start of window) / base_weight(start of window),
#      where base_weight is 100 for the headline chart and the Core weight for the
#      core chart, using the BLS convention that the weight published with month t
#      describes month t-1 (see transforms.weighted_contributions).
#   4. Displayed groups are signed sums of leaf contributions, e.g.
#      Other Core Goods = Core Goods - New Vehicles - Used Cars.

CONTRIB_PERIODS = 6                 # 6-month window, annualized
CONTRIB_FETCH_START_YEAR = 2017     # a year of run-in before the 2018 chart start

# BLS CPI-U item codes. SA levels = "CUSR0000" + code, NSA weights = "CUUR0000" + code.
BLS_ITEM_CODES = {
    "Headline":       "SA0",
    "Core":           "SA0L1E",    # All items less food & energy
    "Food":           "SAF1",
    "Energy":         "SA0E",
    "Core Goods":     "SACL1E",    # Commodities less food & energy commodities
    "Core Services":  "SASLE",     # Services less energy services
    "New Vehicles":   "SETA01",
    "Used Cars":      "SETA02",    # Used cars and trucks
    "Rent":           "SEHA",      # Rent of primary residence
    "OER":            "SEHC",      # Owners' equivalent rent
}


def _bls_ids(names: list[str], prefix: str) -> dict[str, str]:
    return {n: prefix + BLS_ITEM_CODES[n] for n in names}


# Chart specs. `groups` is an ordered list of (display name, {leaf: sign}).
HEADLINE_CONTRIB = {
    "line": "Headline",
    "base": None,                       # weights already sum to 100 across all items
    "leaves": ["Headline", "Core", "Food", "Energy"],
    "groups": [
        ("Core",   {"Core": 1}),
        ("Food",   {"Food": 1}),
        ("Energy", {"Energy": 1}),
    ],
    "colors": {"Core": "#1f3b63", "Food": "#9ecae1", "Energy": "#a6a6a6"},
    "line_color": "#d62728",
    "line_label": "Headline CPI",
    "title": "Headline CPI — {p}m Annualized, Contributions by Component",
}

CORE_CONTRIB = {
    "line": "Core",
    "base": "Core",                     # rescale weights so Core = 100
    "leaves": ["Core", "Core Goods", "Core Services", "New Vehicles", "Used Cars", "Rent", "OER"],
    "groups": [
        ("Used and New Cars",   {"New Vehicles": 1, "Used Cars": 1}),
        ("Other Core Goods",    {"Core Goods": 1, "New Vehicles": -1, "Used Cars": -1}),
        ("Rent + OER",          {"Rent": 1, "OER": 1}),
        ("Other Core Services", {"Core Services": 1, "Rent": -1, "OER": -1}),
    ],
    "colors": {
        "Used and New Cars":   "#7fbf3f",   # green
        "Other Core Goods":    "#5b84b1",   # steel blue
        "Rent + OER":          "#a8cbe8",   # light blue
        "Other Core Services": "#1f3b63",   # navy
    },
    "line_color": "#d62728",
    "line_label": "Core CPI",
    "title": "Core CPI — {p}m Annualized, Contributions by Component",
}


def _contribution_frame(spec: dict, periods: int = CONTRIB_PERIODS) -> pd.DataFrame:
    """Grouped contributions (percentage points) + the aggregate rate column named spec['line']."""
    leaves = spec["leaves"]
    cpi = bls_client.get_indexes(_bls_ids(leaves, "CUSR0000"), start_year=CONTRIB_FETCH_START_YEAR)
    weights = bls_client.get_relative_importance(_bls_ids(leaves, "CUUR0000"), start_year=CONTRIB_FETCH_START_YEAR)

    # Calendar-align before shifting. BLS skipped the October 2025 CPI release; if
    # that month is simply absent from the index, a row-based shift(6) would span
    # seven months for the next six observations and annualize them as six.
    # Reindexing to a full monthly range makes the missing month NaN instead, so
    # only windows that actually touch the gap drop out.
    cpi = cpi.reindex(pd.date_range(cpi.index.min(), cpi.index.max(), freq="MS"))

    rates = transforms.compound_annualized_change(cpi, periods=periods)
    leaf_contrib = transforms.weighted_contributions(
        rates, weights, leaves, periods=periods, base=spec["base"],
    )

    out = pd.DataFrame(index=rates.index)
    for name, parts in spec["groups"]:
        out[name] = sum(sign * leaf_contrib[leaf] for leaf, sign in parts.items())
    out[spec["line"]] = rates[spec["line"]]
    return out.dropna()


def cpi_contribution_frame(periods: int = CONTRIB_PERIODS) -> pd.DataFrame:
    """Headline: Core / Food / Energy contributions + 'Headline' rate."""
    return _contribution_frame(HEADLINE_CONTRIB, periods=periods)


def core_cpi_contribution_frame(periods: int = CONTRIB_PERIODS) -> pd.DataFrame:
    """Core: Used and New Cars / Other Core Goods / Rent + OER / Other Core Services + 'Core' rate."""
    return _contribution_frame(CORE_CONTRIB, periods=periods)


def _contribution_figure(df: pd.DataFrame, spec: dict, periods: int) -> go.Figure:
    """Stacked bars (positives above zero, negatives below) with the aggregate line overlaid."""
    fig = go.Figure()
    for name, _ in spec["groups"]:
        fig.add_trace(go.Bar(
            x=df.index, y=df[name], name=name,
            marker=dict(color=spec["colors"][name], line=dict(width=0)),
            hovertemplate="%{x|%b %Y}<br>" + name + ": %{y:.2f} pp<extra></extra>",
            showlegend=True,
        ))
    fig.add_trace(go.Scatter(
        x=df.index, y=df[spec["line"]], name=spec["line_label"], mode="lines",
        line=dict(color=spec["line_color"], width=2),
        hovertemplate="%{x|%b %Y}<br>" + spec["line_label"] + ": %{y:.2f}%<extra></extra>",
        showlegend=True,
    ))

    plotting.add_last_value_annotation(fig, df[spec["line"]], fmt="{:.1f}%", scale=1.0)

    fig.update_layout(barmode="relative", bargap=0.15)
    fig.update_yaxes(
        title_text=f"% chg, {periods}m annual rate",
        tickformat=".0f", zeroline=True, zerolinewidth=1, zerolinecolor="#444",
    )
    fig = plotting.apply_layout(fig, title=spec["title"].format(p=periods), height=560)
    fig.update_layout(legend=_legend_style(yanchor="bottom", y=1.02))
    return fig


def cpi_contribution(start_date: str = CPI_DEFAULT_START, periods: int = CONTRIB_PERIODS) -> go.Figure:
    """Headline CPI contribution chart. Weights start in 2018, so the chart does too."""
    df = _trim(cpi_contribution_frame(periods=periods), start_date)
    return _contribution_figure(df, HEADLINE_CONTRIB, periods)


def core_cpi_contribution(start_date: str = CPI_DEFAULT_START, periods: int = CONTRIB_PERIODS) -> go.Figure:
    """Core CPI contribution chart (cars / other goods / rent+OER / other services)."""
    df = _trim(core_cpi_contribution_frame(periods=periods), start_date)
    return _contribution_figure(df, CORE_CONTRIB, periods)


# ---- INFLATION DETAIL: monthly breakdown tables (CPI + PCE) ------------------
#
# Row registries. Each dict describes one table row:
#   label / level (0 aggregate, 1 sub-aggregate, 2 component) / bold
#   PCE : bea = BEA SeriesCode stem in NIPA table 2.4.4U (price index, monthly,
#         2017=100); the matching current-dollar line in 2.4.5U has the same
#         stem with "RC" instead of "RG" (IA/LA prefixes for the two derived
#         aggregates). Weight = current-dollar share of total PCE.
#         fred = (price index id, nominal id) for the one aggregate BEA
#         publishes only through FRED's derived series (Super-Core).
#   CPI : code  = BLS CPI-U item code (SA levels from CUSR0000+code, weights
#         from the Relative Importance aspect of CUUR0000+code), or
#         residual = (parent code, [child codes]) computed by
#         core.inflation_tables.residual_mm.

PCE_TABLE_ROWS = [
    dict(label="Headline PCE",                              bea="DPCERG",   level=0, bold=True),
    dict(label="Core PCE (ex food & energy)",               bea="DPCCRG",   level=0, bold=True),
    dict(label="Core Goods (ex food & energy)",             bea="IA000062", level=1, bold=True),
    dict(label="Motor vehicles & parts",                    bea="DMOTRG",   level=2),
    dict(label="Home furnishings & durable equipment",      bea="DFDHRG",   level=2),
    dict(label="Recreational goods & vehicles",             bea="DREQRG",   level=2),
    dict(label="Other durable goods",                       bea="DODGRG",   level=2),
    dict(label="Apparel (clothing & footwear)",             bea="DCLORG",   level=2),
    dict(label="Other nondurable goods",                    bea="DONGRG",   level=2),
    dict(label="Core Services (ex energy services)",        bea="IA000063", level=1, bold=True),
    dict(label="Housing",                                   bea="DHSGRG",   level=2),
    dict(label="Health care",                               bea="DHLCRG",   level=2),
    dict(label="Transportation services",                   bea="DTRSRG",   level=2),
    dict(label="Recreation services",                       bea="DRCARG",   level=2),
    dict(label="Food services & accommodations",            bea="DFSARG",   level=2),
    dict(label="Financial services & insurance",            bea="DIFSRG",   level=2),
    dict(label="Other services",                            bea="DOTSRG",   level=2),
    dict(label="Food & beverages (off-premises)",           bea="DFXARG",   level=0),
    dict(label="Energy goods & services",                   bea="DNRGRG",   level=0),
    dict(label="Super-Core (services ex energy & housing)", fred=("IA001260M", "LA001260M"), level=0, bold=True),
]


def _bea_nominal_code(price_code: str) -> str:
    """2.4.4U price code -> 2.4.5U current-dollar code (DxxxRG -> DxxxRC, IAnnn -> LAnnn)."""
    if price_code.startswith("IA"):
        return "LA" + price_code[2:]
    if price_code.endswith("RG"):
        return price_code[:-2] + "RC"
    raise ValueError(f"cannot derive nominal code from {price_code!r}")

CPI_TABLE_ROWS = [
    dict(label="Headline CPI",                          code="SA0",    level=0, bold=True),
    dict(label="Core CPI (ex food & energy)",           code="SA0L1E", level=0, bold=True),
    dict(label="Core Goods",                            code="SACL1E", level=1, bold=True),
    dict(label="New vehicles",                          code="SETA01", level=2),
    dict(label="Used cars & trucks",                    code="SETA02", level=2),
    dict(label="Apparel",                               code="SAA",    level=2),
    dict(label="Medical care commodities",              code="SAM1",   level=2),
    dict(label="Other core goods (residual)",           residual=("SACL1E", ["SETA01", "SETA02", "SAA", "SAM1"]), level=2),
    dict(label="Core Services",                         code="SASLE",  level=1, bold=True),
    dict(label="Shelter",                               code="SAH1",   level=2),
    dict(label="Medical care services",                 code="SAM2",   level=2),
    dict(label="Transportation services",               code="SAS4",   level=2),
    dict(label="Recreation services",                   code="SARS",   level=2),
    dict(label="Education & communication services",    code="SAES",   level=2),
    # "Other personal services" (SAGS) has no seasonally adjusted series, so the
    # remainder of core services is shown as a documented residual instead.
    dict(label="Other core services (residual)",        residual=("SASLE", ["SAH1", "SAM2", "SAS4", "SARS", "SAES"]), level=2),
    dict(label="Food",                                  code="SAF1",   level=0, bold=True),
    dict(label="Energy",                                code="SA0E",   level=0, bold=True),
    dict(label="Super-Core (core services ex shelter)", residual=("SASLE", ["SAH1"]), level=0, bold=True),
]

TABLE_MONTHS = 3

PCE_TABLE_CAPTION = (
    "Seasonally adjusted month-on-month percent change of BEA chain-type price indexes (NIPA table 2.4.4U "
    "via the BEA API; Super-Core via FRED). Weights correspond to the latest available composition "
    "measure: PCE weights shown as current-dollar expenditure shares (table 2.4.5U) and are an "
    "approximation to chain-index contribution weights. Core Services components exclude household "
    "utilities and nonprofit final consumption, so they do not sum exactly to Core Services."
)
CPI_TABLE_CAPTION = (
    "Seasonally adjusted CPI-U month-on-month percent change (BLS API). Weights are the BLS Relative "
    "Importance published with the latest CPI release. Residual rows are derived from the parent and the "
    "listed components using those weights; Super-Core is core services excluding shelter."
)


def _pce_rows() -> list[inflation_tables.TableRow]:
    """Rows for the PCE table: BEA 2.4.4U price indexes (m/m on full fetched
    history) and 2.4.5U current-dollar levels (weights = share of total PCE at
    the latest month). One missing line only blanks its own row."""
    year = dt.date.today().year
    bea_specs = [s for s in PCE_TABLE_ROWS if "bea" in s]
    price_codes = {s["bea"]: s["bea"] for s in bea_specs}
    nom_codes = {s["bea"]: _bea_nominal_code(s["bea"]) for s in bea_specs}
    prices = bea_client.get_table_series(bea_client.TABLE_PCE_PRICE, price_codes, start_year=year - 2)
    nominal = bea_client.get_table_series(bea_client.TABLE_PCE_NOMINAL, nom_codes, start_year=year - 2)

    total = nominal["DPCERG"].dropna()                # total PCE, $mn SAAR (keyed by its price stem)
    w_date = total.index.max()

    rows = []
    for spec in PCE_TABLE_ROWS:
        mm, w, note = None, None, ""
        try:
            if "bea" in spec:
                k = spec["bea"]
                mm = inflation_tables.mm_pct(prices[k])
                nom = nominal[k].dropna()
            else:
                price_id, nominal_id = spec["fred"]
                mm = inflation_tables.mm_pct(get_series(price_id))
                nom = get_series(nominal_id).dropna()     # FRED LA... series are $mn too
            if w_date in nom.index:
                w = float(nom.loc[w_date] / total.loc[w_date] * 100.0)
            else:
                note = f"no nominal value for {w_date:%b %Y}"
        except Exception as e:  # noqa: BLE001
            note = f"{type(e).__name__}: {e}"
        rows.append(inflation_tables.TableRow(spec["label"], mm, w, spec["level"], spec.get("bold", False), note))
    return rows


def pce_table(n_months: int = TABLE_MONTHS) -> inflation_tables.InflationTable:
    return inflation_tables.build_inflation_table(_pce_rows(), n_months=n_months)


def _cpi_rows() -> list[inflation_tables.TableRow]:
    """Rows for the CPI table from the BLS API (SA levels + NSA relative importance)."""
    codes = sorted({s["code"] for s in CPI_TABLE_ROWS if "code" in s})
    year = dt.date.today().year
    levels = bls_client.get_indexes({c: "CUSR0000" + c for c in codes}, start_year=year - 2)
    ri = bls_client.get_relative_importance({c: "CUUR0000" + c for c in codes}, start_year=year - 2)
    w_row = ri.dropna(subset=["SA0"]).iloc[-1]           # latest month with a headline weight

    mm = {c: inflation_tables.mm_pct(levels[c]) for c in codes if c in levels.columns}
    weight = {c: float(w_row[c]) for c in codes if c in w_row.index and pd.notna(w_row[c])}

    rows = []
    for spec in CPI_TABLE_ROWS:
        note = ""
        try:
            if "code" in spec:
                c = spec["code"]
                r_mm, r_w = mm.get(c), weight.get(c)
                if r_mm is None:
                    note = "no SA series"
            else:
                parent, children = spec["residual"]
                r_mm, r_w = inflation_tables.residual_mm(
                    mm[parent], weight[parent], [(mm[k], weight[k]) for k in children],
                )
        except Exception as e:  # noqa: BLE001
            r_mm, r_w, note = None, None, f"{type(e).__name__}: {e}"
        rows.append(inflation_tables.TableRow(spec["label"], r_mm, r_w, spec["level"], spec.get("bold", False), note))
    return rows


def cpi_table(n_months: int = TABLE_MONTHS) -> inflation_tables.InflationTable:
    return inflation_tables.build_inflation_table(_cpi_rows(), n_months=n_months)


def _table_tab(label: str, builder, caption: str) -> dict:
    """One sub-tab of the detail block: styled HTML + caption, or an error."""
    tab = {"label": label, "caption": caption}
    try:
        tbl = builder()
        tab["html"] = inflation_tables.table_html(tbl)
        missing = [f"{tbl.df.loc[i, 'Category']} ({n})" for i, n in enumerate(tbl.notes) if n]
        if missing:
            tab["caption"] += " Rows without data: " + "; ".join(missing) + "."
    except Exception as e:  # noqa: BLE001
        tab["error"] = f"{type(e).__name__}: {e}"
    return tab


def inflation_detail_entry() -> dict:
    """Section entry rendered by app.py as sub-tabs (PCE | CPI) with one table each."""
    return {
        "id": "inflation_detail",
        "title": "Inflation Detail",
        "tabs": [
            _table_tab("PCE", pce_table, PCE_TABLE_CAPTION),
            _table_tab("CPI", cpi_table, CPI_TABLE_CAPTION),
        ],
        "commentary": None,
    }


# ---- Section assembler -------------------------------------------------------

def _safe_entry(chart_id: str, title: str, commentary: str, builder, start_date: str) -> dict:
    """Chart entry built inside try/except.

    A missing BLS key or a BLS outage degrades to a warning on this one chart
    instead of taking down the whole Inflation tab.
    """
    entry = {"id": chart_id, "title": title, "commentary": commentary}
    try:
        entry["fig"] = builder(start_date=start_date)
    except Exception as e:  # noqa: BLE001
        entry["fig"] = None
        entry["error"] = f"{type(e).__name__}: {e}"
    return entry


_CONTRIB_METHOD_NOTE = (
    "Weights are the BLS relative-importance shares published with the CPI release, applied at "
    "the start of each 6-month window. Index levels are seasonally adjusted (BLS API); weights "
    "come from the NSA series, which is where BLS attaches them. History starts in 2018 when "
    "monthly weights become available."
)


def _contribution_entry(start_date: str) -> dict:
    return _safe_entry(
        "cpi_contribution",
        "Headline CPI — Contributions (6m annualized)",
        "Bars are the contribution of Core, Food and Energy to the 6-month annualized headline "
        "rate (percentage points); the red line is headline CPI itself. " + _CONTRIB_METHOD_NOTE,
        cpi_contribution, start_date,
    )


def _core_contribution_entry(start_date: str) -> dict:
    return _safe_entry(
        "core_cpi_contribution",
        "Core CPI — Contributions (6m annualized)",
        "Bars split the 6-month annualized core rate into Used and New Cars, Other Core Goods, "
        "Rent + OER, and Other Core Services (which includes health insurance); the red line is "
        "core CPI itself. Weights are rescaled so core = 100. 'Other' groups are residuals: "
        "core goods less vehicles, core services less rent and OER. " + _CONTRIB_METHOD_NOTE,
        core_cpi_contribution, start_date,
    )

def build(start_date: str = CPI_DEFAULT_START) -> dict:
    """Build the Inflation section. Same shape as labor.build().

    The combined dashboard is the headline view; individual panels are also
    exposed in case you want to dig into a single panel in Streamlit or Colab.
    """
    charts = [
        {
            "id": "cpi_dashboard",
            "title": "CPI Dashboard",
            "fig": cpi_dashboard(start_date=start_date),
            "commentary": f"Display window starts {start_date}. Three views in one: headline + major buckets, services breakdown, and 3m annualized momentum. YoY and 3m-ann are computed on full history and then trimmed, so the chart starts with real data instead of 12 months of NaNs. Click legend entries to hide or show a series.",
        },
        _contribution_entry(start_date),
        _core_contribution_entry(start_date),
        {
            "id": "cpi_headline_yoy",
            "title": "CPI Headline — Major Buckets (YoY)",
            "fig": cpi_headline_yoy(start_date=start_date),
            "commentary": "Goods deflation since 2022 has been the main story behind the headline cooling — services has been much stickier (see next chart).",
        },
        {
            "id": "cpi_services_breakdown",
            "title": "Services CPI — Sub-Category Breakdown (YoY)",
            "fig": cpi_services_breakdown(start_date=start_date),
            "commentary": "Shelter is the dominant component by weight (~30% of CPI). Watch transport and medical services for second-round effects.",
        },
        {
            "id": "cpi_momentum",
            "title": "CPI Momentum — 3-Month Annualized",
            "fig": cpi_momentum(start_date=start_date),
            "commentary": "3m annualized = current-quarter pace. When it diverges from YoY, momentum is shifting — useful leading signal for where YoY is headed.",
        },
        inflation_detail_entry(),
    ]

    return {
        "title": "Inflation (CPI)",
        "charts": charts,
    }
