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

from core import bls_client, config, plotting, transforms
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


# ---- Contributions to 6m-annualized headline CPI (BLS weights) ---------------

# Seasonally adjusted CPI-U indexes (levels) — BLS series ids.
CPI_SA_BLS = {
    "Headline": "CUSR0000SA0",
    "Core":     "CUSR0000SA0L1E",   # All items less food & energy
    "Food":     "CUSR0000SAF1",
    "Energy":   "CUSR0000SA0E",
}

# NSA CPI-U series — these are the ones that carry the BLS
# "Relative Importance" aspect (basket weights, percent).
CPI_NSA_BLS = {
    "Headline": "CUUR0000SA0",
    "Core":     "CUUR0000SA0L1E",
    "Food":     "CUUR0000SAF1",
    "Energy":   "CUUR0000SA0E",
}

CONTRIB_COMPONENTS = ["Core", "Food", "Energy"]
CONTRIB_PERIODS = 6                 # 6-month window, annualized
CONTRIB_FETCH_START_YEAR = 2017     # a year of run-in before the 2018 chart start

CONTRIB_COLORS = {
    "Core":     "#1f3b63",   # navy
    "Food":     "#9ecae1",   # light blue
    "Energy":   "#a6a6a6",   # grey
    "Headline": "#d62728",   # red
}


def cpi_contribution_frame(periods: int = CONTRIB_PERIODS) -> pd.DataFrame:
    """Contributions of Core / Food / Energy to the N-month annualized headline CPI.

    Steps (mirrors the research notebook):
      1. SA index levels from BLS  -> compound N-month annualized rate, percent.
      2. NSA relative-importance weights from BLS (percent of basket).
      3. contribution_c = rate_c x weight_c(start of window) / 100,
         using the BLS convention that the weight published with month t
         describes month t-1  (see transforms.weighted_contributions).
      4. 'Headline' column = the headline N-month annualized rate itself.

    Returns a DataFrame with columns Core, Food, Energy, Headline (percent).
    """
    cpi = bls_client.get_indexes(CPI_SA_BLS, start_year=CONTRIB_FETCH_START_YEAR)
    weights = bls_client.get_relative_importance(CPI_NSA_BLS, start_year=CONTRIB_FETCH_START_YEAR)

    rates = transforms.compound_annualized_change(cpi, periods=periods)
    contrib = transforms.weighted_contributions(rates, weights, CONTRIB_COMPONENTS, periods=periods)
    contrib["Headline"] = rates["Headline"]
    return contrib.dropna()


def cpi_contribution(start_date: str = CPI_DEFAULT_START, periods: int = CONTRIB_PERIODS) -> go.Figure:
    """Stacked-bar contribution chart with the headline rate overlaid.

    Bars: Core / Food / Energy contributions (percentage points, stacked with
    positives above and negatives below zero). Line: headline CPI, N-month
    annualized. Weights history starts in 2018, so the chart starts there
    even if an earlier display window is selected.
    """
    df = _trim(cpi_contribution_frame(periods=periods), start_date)

    fig = go.Figure()
    for comp in CONTRIB_COMPONENTS:
        fig.add_trace(go.Bar(
            x=df.index, y=df[comp], name=comp,
            marker=dict(color=CONTRIB_COLORS[comp], line=dict(width=0)),
            hovertemplate="%{x|%b %Y}<br>" + comp + ": %{y:.2f} pp<extra></extra>",
            showlegend=True,
        ))
    fig.add_trace(go.Scatter(
        x=df.index, y=df["Headline"], name="Headline CPI", mode="lines",
        line=dict(color=CONTRIB_COLORS["Headline"], width=2),
        hovertemplate="%{x|%b %Y}<br>Headline: %{y:.2f}%<extra></extra>",
        showlegend=True,
    ))

    plotting.add_last_value_annotation(fig, df["Headline"], fmt="{:.1f}%", scale=1.0)

    fig.update_layout(barmode="relative", bargap=0.15)
    fig.update_yaxes(
        title_text=f"% chg, {periods}m annual rate",
        tickformat=".0f", zeroline=True, zerolinewidth=1, zerolinecolor="#444",
    )
    fig = plotting.apply_layout(
        fig, title=f"Headline CPI — {periods}m Annualized, Contributions by Component", height=560,
    )
    fig.update_layout(legend=_legend_style(yanchor="bottom", y=1.02))
    return fig


# ---- Section assembler -------------------------------------------------------

def _contribution_entry(start_date: str) -> dict:
    """Chart entry for the BLS contribution chart.

    Built inside try/except so a missing BLS key or a BLS outage degrades to a
    warning on this one chart instead of taking down the whole Inflation tab.
    """
    entry = {
        "id": "cpi_contribution",
        "title": "Headline CPI — Contributions (6m annualized)",
        "commentary": (
            "Bars are the contribution of Core, Food and Energy to the 6-month annualized "
            "headline rate (percentage points); the red line is headline CPI itself. "
            "Weights are the BLS relative-importance shares published with the CPI release, "
            "applied at the start of each 6-month window. Index levels are seasonally adjusted "
            "(BLS API); weights come from the NSA series, which is where BLS attaches them. "
            "History starts in 2018 when monthly weights become available."
        ),
    }
    try:
        entry["fig"] = cpi_contribution(start_date=start_date)
    except Exception as e:  # noqa: BLE001
        entry["fig"] = None
        entry["error"] = f"{type(e).__name__}: {e}"
    return entry

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
    ]

    return {
        "title": "Inflation (CPI)",
        "charts": charts,
    }
