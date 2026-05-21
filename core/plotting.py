"""Plot factories. All functions return go.Figure — the caller decides how to display.

No `width` is set on layouts: in Streamlit we use `use_container_width=True`, and
in Colab the default Plotly width works fine. Setting widths in core/ would break
responsive layouts.
"""

from __future__ import annotations

from typing import Iterable, Optional, Sequence

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from . import config


def apply_layout(
    fig: go.Figure,
    title: str,
    height: int = config.DEFAULT_HEIGHT,
    show_legend: bool = True,
) -> go.Figure:
    """Standard chart styling. Call this last on any figure built by core code."""
    fig.update_layout(
        title=title,
        height=height,
        showlegend=show_legend,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="left",
            x=0,
        ),
        margin=dict(l=60, r=30, t=80, b=40),
    )
    return fig


def line_panel(
    df: pd.DataFrame,
    cols: Sequence[str],
    title: str,
    height: int = config.DEFAULT_HEIGHT,
) -> go.Figure:
    """Simple multi-line chart for `cols` in `df`, using the index as x."""
    fig = go.Figure()
    for col in cols:
        fig.add_trace(go.Scatter(x=df.index, y=df[col], name=col, mode="lines"))
    return apply_layout(fig, title=title, height=height)


def two_panel(
    left: go.Figure,
    right: go.Figure,
    title: str,
    subtitles: tuple[str, str],
    height: int = config.DEFAULT_HEIGHT,
) -> go.Figure:
    """Combine two single-panel Figures side-by-side. Traces are copied, not the layout."""
    fig = make_subplots(rows=1, cols=2, subplot_titles=subtitles)
    for trace in left["data"]:
        fig.add_trace(trace, row=1, col=1)
    for trace in right["data"]:
        fig.add_trace(trace, row=1, col=2)
    return apply_layout(fig, title=title, height=height)


def grid_from_traces(
    panels: list[dict],
    rows: int,
    cols: int,
    title: str,
    subplot_titles: Sequence[str],
    height_per_row: int = 350,
    show_legend: bool = False,
) -> go.Figure:
    """Build an N×M subplot grid.

    Each entry in `panels` is a dict:
        {
            "row": int (1-indexed),
            "col": int (1-indexed),
            "traces": list[go.Scatter | go.Bar],
            "yaxis_ticksuffix": Optional[str],  # e.g. "%"
            "yaxis_range": Optional[tuple[float, float]],
        }
    """
    fig = make_subplots(rows=rows, cols=cols, subplot_titles=tuple(subplot_titles))
    for p in panels:
        r, c = p["row"], p["col"]
        for trace in p["traces"]:
            fig.add_trace(trace, row=r, col=c)
        if p.get("yaxis_ticksuffix"):
            fig.update_yaxes(ticksuffix=p["yaxis_ticksuffix"], row=r, col=c)
        if p.get("yaxis_range"):
            fig.update_yaxes(range=list(p["yaxis_range"]), row=r, col=c)

    return apply_layout(
        fig,
        title=title,
        height=height_per_row * rows,
        show_legend=show_legend,
    )


def line_and_ma_traces(
    df: pd.DataFrame,
    level_col: str,
    ma_col: str,
    base_name: str,
) -> list[go.Scatter]:
    """Return [level_trace, ma_trace] ready to drop into a subplot panel."""
    return [
        go.Scatter(x=df.index, y=df[level_col], name=base_name, mode="lines"),
        go.Scatter(x=df.index, y=df[ma_col], name=f"{base_name} MA", mode="lines"),
    ]


def add_last_value_annotation(
    fig: go.Figure,
    series: pd.Series,
    row: Optional[int] = None,
    col: Optional[int] = None,
    fmt: str = "{:.1f}%",
    scale: float = 100.0,
    ax: int = 25,
    ay: int = -25,
) -> go.Figure:
    """Drop an arrow-labeled annotation on the most recent non-NaN value of `series`.

    Default formatting assumes `series` is in decimal form (e.g. 0.025) and
    should be displayed as a percent. Override `scale=1` to display as-is.

    Safe to call on empty / all-NaN series — it's a no-op in that case.
    """
    clean = series.dropna()
    if clean.empty:
        return fig
    x = clean.index[-1]
    y = float(clean.iloc[-1])
    fig.add_annotation(
        x=x, y=y,
        text=fmt.format(y * scale),
        showarrow=True,
        arrowhead=2,
        ax=ax, ay=ay,
        row=row, col=col,
    )
    return fig


def add_paper_annotation(
    fig: go.Figure,
    text: str,
    ypaper: float,
    xpaper: float = 0.5,
    font_size: int = 11,
) -> go.Figure:
    """Add a centered text annotation in paper coordinates (0..1 across the whole figure).

    Useful for placing "pseudo-legends" between subplot panels without invoking
    Plotly's legend (which shrinks the plot area).
    """
    fig.add_annotation(
        x=xpaper, y=ypaper,
        xref="paper", yref="paper",
        text=text,
        showarrow=False,
        align="center",
        font=dict(size=font_size),
    )
    return fig
