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

from core import config, plotting, transforms
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


# ---- Individual chart functions ---------------------------------------------

def cpi_headline_yoy(start_date: str = CPI_DEFAULT_START) -> go.Figure:
    """Panel 1 standalone: headline/core CPI + major buckets, YoY %."""
    df = _trim(_yoy_frame(HEADLINE_AND_BUCKETS), start_date)
    plot_cols = ["CPI", "Core CPI", "Services CPI", "Goods CPI", "Foods CPI"]

    fig = go.Figure()
    for col in plot_cols:
        fig.add_trace(go.Scatter(x=df.index, y=df[col], name=col, mode="lines"))

    plotting.add_last_value_annotation(fig, df["CPI"])
    fig.update_yaxes(ticksuffix="%", tickformat=".1%")
    return plotting.apply_layout(
        fig, title="US CPI — YoY (headline/core + major buckets)", height=520,
    )


def cpi_services_breakdown(start_date: str = CPI_DEFAULT_START) -> go.Figure:
    """Panel 2 standalone: services CPI broken into sub-categories, YoY %."""
    df = _trim(_yoy_frame(SERVICES_BREAKDOWN), start_date)
    plot_cols = [name for _, name in SERVICES_BREAKDOWN]

    fig = go.Figure()
    for col in plot_cols:
        fig.add_trace(go.Scatter(x=df.index, y=df[col], name=col, mode="lines"))

    plotting.add_last_value_annotation(fig, df["Services CPI"])
    fig.update_yaxes(ticksuffix="%", tickformat=".1%")
    return plotting.apply_layout(
        fig, title="US Core Services CPI — YoY breakdown", height=520,
    )


def cpi_momentum(start_date: str = CPI_DEFAULT_START) -> go.Figure:
    """Panel 3 standalone: 3-month annualized headline & core CPI."""
    df = _trim(_ann_frame(MOMENTUM_SERIES, periods=3), start_date)

    fig = go.Figure()
    for col in df.columns:
        fig.add_trace(go.Scatter(x=df.index, y=df[col], name=col, mode="lines"))

    plotting.add_last_value_annotation(fig, df["CPI 3m ann"])
    fig.update_yaxes(ticksuffix="%", tickformat=".1%")
    return plotting.apply_layout(
        fig, title="US CPI — 3m Annualized (headline vs core)", height=520,
    )


def cpi_dashboard(start_date: str = CPI_DEFAULT_START) -> go.Figure:
    """Combined 3-panel CPI dashboard, single column.

    Preserves the user's original design:
      - YoY/3m-ann computed on FULL history, display filtered after
      - No Plotly legend (would shrink the plots)
      - Per-panel pseudo-legend as text annotations in paper coords
      - Last-release arrow on the primary series of each panel
    """
    yoy_all = _yoy_frame(HEADLINE_AND_BUCKETS + SERVICES_BREAKDOWN)
    ann_all = _ann_frame(MOMENTUM_SERIES, periods=3)

    df_main = _trim(yoy_all, start_date)
    df_svc = _trim(yoy_all, start_date)
    df_3m = _trim(ann_all, start_date)

    fig = make_subplots(
        rows=3, cols=1,
        shared_xaxes=False,
        subplot_titles=(
            f"US CPI — YoY (headline/core + major buckets) [display since {start_date}]",
            f"US Core Services CPI — YoY breakdown [display since {start_date}]",
            f"US CPI — 3m annualized (headline vs core) [display since {start_date}]",
        ),
        vertical_spacing=0.12,
    )

    # ---- Panel 1: headline & buckets
    p1_cols = ["CPI", "Core CPI", "Services CPI", "Goods CPI", "Foods CPI"]
    for c in p1_cols:
        fig.add_trace(go.Scatter(x=df_main.index, y=df_main[c], mode="lines", name=c), row=1, col=1)
    plotting.add_last_value_annotation(fig, df_main["CPI"], row=1, col=1)

    # ---- Panel 2: services breakdown
    p2_cols = [name for _, name in SERVICES_BREAKDOWN]
    for c in p2_cols:
        fig.add_trace(go.Scatter(x=df_svc.index, y=df_svc[c], mode="lines", name=c), row=2, col=1)
    plotting.add_last_value_annotation(fig, df_svc["Services CPI"], row=2, col=1)

    # ---- Panel 3: 3m annualized
    p3_cols = ["CPI 3m ann", "Core CPI 3m ann"]
    for c in p3_cols:
        fig.add_trace(go.Scatter(x=df_3m.index, y=df_3m[c], mode="lines", name=c), row=3, col=1)
    plotting.add_last_value_annotation(fig, df_3m["CPI 3m ann"], row=3, col=1)

    # Y-axis formatting: percent on all rows
    for r in (1, 2, 3):
        fig.update_yaxes(ticksuffix="%", tickformat=".1%", row=r, col=1)

    # Pseudo-legends between panels (no Plotly legend → charts don't shrink)
    plotting.add_paper_annotation(
        fig,
        "Panel 1: CPI | Core CPI | Services CPI | Goods CPI | Foods CPI",
        ypaper=0.64,
    )
    plotting.add_paper_annotation(
        fig,
        "Panel 2: Services | Shelter | Medical | Transport | Edu/Comm | Recreation | Other",
        ypaper=0.33,
    )
    plotting.add_paper_annotation(
        fig,
        "Panel 3: CPI 3m ann | Core CPI 3m ann",
        ypaper=0.05,
    )

    fig.update_layout(
        title="U.S. CPI Dashboard — YoY + 3m Annualized (computed on full history, then filtered)",
        template="plotly_white",
        height=1650,
        margin=dict(l=60, r=30, t=70, b=60),
        showlegend=False,
    )
    return fig


# ---- Section assembler -------------------------------------------------------

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
            "commentary": "Three views in one: headline + major buckets, services breakdown, and 3m annualized momentum. YoY and 3m-ann are computed on full history and then trimmed, so the chart starts with real data instead of 12 months of NaNs.",
        },
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
