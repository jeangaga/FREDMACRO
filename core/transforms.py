"""Pure data transforms — no plotting, no I/O.

Functions take pandas objects in and return pandas objects out, so they can
be unit-tested without hitting FRED.
"""

from __future__ import annotations

from typing import Iterable, Optional

import pandas as pd


def monthly_change(series: pd.Series) -> pd.Series:
    """First difference. Same as series.diff() but named for clarity at call sites."""
    return series.diff()


def rolling_mean(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window=window).mean()


def yoy_change(series: pd.Series, drop_initial: bool = True) -> pd.Series:
    """12-month percentage change.

    Returns the rolling 12-month % change as a decimal (0.025 = 2.5%).
    With drop_initial=True, the first 12 NaN values are stripped so plots
    don't start with a flat empty stretch.

    NOTE: compute YoY on the FULL history series, then filter your display
    window afterwards. Filtering before pct_change throws away 12 months of
    real data at the start of the window.
    """
    yoy = series.pct_change(periods=12)
    if drop_initial:
        yoy = yoy.iloc[12:]
    return yoy


def annualized_change(
    series: pd.Series,
    periods: int = 3,
    drop_initial: bool = True,
) -> pd.Series:
    """N-period % change, annualized.

    For monthly data:
      - periods=3 → 3-month change × 4   (the classic "3m annualized")
      - periods=6 → 6-month change × 2

    Like yoy_change(), compute on full history and filter display after.
    """
    if periods <= 0:
        raise ValueError("periods must be positive")
    chg = series.pct_change(periods=periods) * (12.0 / periods)
    if drop_initial:
        chg = chg.iloc[periods:]
    return chg


def with_change_and_ma(
    series: pd.Series,
    name: str,
    ma_window: int = 3,
    start_date: Optional[str] = None,
) -> pd.DataFrame:
    """Standard payroll-style frame: level, monthly change, and N-month MA of the change.

    Returns a DataFrame with columns:
        - <name>          : the original level
        - <name> Δ        : first difference (monthly change)
        - <name> Δ Nm MA  : N-month moving average of the change

    Indexed by date. Date column is NOT added — use the index when plotting.
    """
    df = series.to_frame(name=name)
    df[f"{name} Δ"] = df[name].diff()
    df[f"{name} Δ {ma_window}m MA"] = df[f"{name} Δ"].rolling(window=ma_window).mean()
    if start_date is not None:
        df = df.loc[df.index >= pd.to_datetime(start_date)]
    return df


def diffusion_index(
    level_df: pd.DataFrame,
    months_change: int = 3,
    ma_months: int = 6,
    start_date: Optional[str] = None,
) -> pd.DataFrame:
    """Compute breadth: % of columns with a positive change over `months_change` months.

    Args:
        level_df: DataFrame of level series (rows=dates, cols=sectors).
        months_change: look-back window for the change calculation.
        ma_months: window for the smoothed series.
        start_date: optional ISO date string for trimming the output.

    Returns:
        DataFrame with columns "Diffusion (%)" and "Diffusion MA".
    """
    if level_df.empty:
        raise ValueError("level_df is empty — no series to compute diffusion over.")

    chg = level_df - level_df.shift(months_change)
    pos = (chg > 0).astype(float)
    diffusion = pos.mean(axis=1) * 100.0

    out = pd.DataFrame({"Diffusion (%)": diffusion})
    out["Diffusion MA"] = out["Diffusion (%)"].rolling(ma_months).mean()

    if start_date is not None:
        out = out.loc[out.index >= pd.to_datetime(start_date)]

    return out


def cyclical_split(
    nfp: pd.Series,
    government: pd.Series,
    edu_health: pd.Series,
) -> pd.DataFrame:
    """Decompose monthly NFP change into cyclical and non-cyclical contributions.

    cyclical    = Δ(NFP) − Δ(Government) − Δ(Education & Health)
    non_cyclical = Δ(Government) + Δ(Education & Health)
    headline    = Δ(NFP)

    Returns:
        DataFrame with columns "Cyclical Δ", "Non-cyclical Δ", "NFP Δ",
        "NFP Δ 3m MA", aligned on the inner join of all three inputs.
    """
    levels = pd.concat([nfp, government, edu_health], axis=1, join="inner")
    levels.columns = ["NFP", "Gov", "EduHealth"]

    chg = levels.diff()
    out = pd.DataFrame(index=chg.index)
    out["Cyclical Δ"] = chg["NFP"] - chg["Gov"] - chg["EduHealth"]
    out["Non-cyclical Δ"] = chg["Gov"] + chg["EduHealth"]
    out["NFP Δ"] = chg["NFP"]
    out["NFP Δ 3m MA"] = out["NFP Δ"].rolling(3).mean()
    return out


def assemble_levels(
    series_map: dict[str, pd.Series],
) -> pd.DataFrame:
    """Stitch a dict of {name: Series} into a single DataFrame (rows=dates, cols=names).

    Drops rows where every column is NaN, but keeps partial rows so caller can decide.
    """
    if not series_map:
        raise ValueError("series_map is empty.")
    return pd.DataFrame(series_map).dropna(how="all")
