"""Labor market section — converted from the NFP Colab notebook.

Each chart function returns a go.Figure and can be called independently in Colab.
`build()` runs all of them and returns a structured dict that app.py renders.

Toggles:
    diffusion_extended: True  → 17-sector index (default), False → 10-sector basic.
    cyclical_view:      "contribution" (default, stacked bars) or "grid" (4x2 panels).
"""

from __future__ import annotations

from typing import Literal, Optional

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from core import config, plotting, transforms
from core.fred_client import get_series, get_series_safe


# ---- FRED mnemonics ----------------------------------------------------------

# Sector breakdown for the NFP-components grid (cell 7 of the notebook).
NFP_SECTOR_SERIES = [
    ("PAYEMS", "Total Nonfarm"),
    ("USPRIV", "Private Payrolls"),
    ("USGOOD", "Goods-Producing"),
    ("CES0800000001", "Service-Providing"),
    ("USGOVT", "Government"),
    ("USEHS", "Education and Health Services"),
    ("USCONS", "Construction"),
    ("MANEMP", "Manufacturing"),
    ("DMANEMP", "Durable Goods"),
    ("NDMANEMP", "Nondurable Goods"),
    ("USTPU", "Trade, Transportation, and Utilities"),
    ("USWTRADE", "Wholesale Trade"),
    ("USTRADE", "Retail Trade"),
    ("CES4300000001", "Transportation and Warehousing"),
    ("USPBS", "Professional and Business Services"),
    ("TEMPHELPS", "Temporary Help Services"),
    ("USLAH", "Leisure and Hospitality"),
]

# Diffusion-index universes.
DIFFUSION_BASIC = {
    "Mining & Logging": "USMINE",
    "Construction": "USCONS",
    "Manufacturing": "MANEMP",
    "Trade, Transp. & Utilities": "USTPU",
    "Information": "USINFO",
    "Financial Activities": "USFIRE",
    "Prof. & Business Services": "USPBS",
    "Education & Health": "USEHS",
    "Leisure & Hospitality": "USLAH",
    "Government": "USGOVT",
}

DIFFUSION_EXTENDED = {
    "Mining & Logging": "USMINE",
    "Construction": "USCONS",
    "Manufacturing - Durable": "DMANEMP",
    "Manufacturing - Nondurable": "NDMANEMP",
    "Wholesale Trade": "USWTRADE",
    "Retail Trade": "USTRADE",
    "Transportation & Warehousing": "CES4300000001",
    "Utilities": "USUTIL",
    "Information": "USINFO",
    "Financial Activities": "USFIRE",
    "Professional & Business Services": "USPBS",
    "Education & Health Services": "USEHS",
    "Leisure & Hospitality": "USLAH",
    "Other Services": "USOS",
    "Federal Government": "USFEDS",
    "State Government": "USSTATES",
    "Local Government": "USLOCALGOV",
}


# ---- Individual charts -------------------------------------------------------

def nfp_overview(start_date: str = config.DEFAULT_START_DATE) -> go.Figure:
    """Headline NFP and Private Payrolls — monthly change with 3m MA."""
    nfp = get_series("PAYEMS")
    priv = get_series("USPRIV")

    nfp_df = transforms.with_change_and_ma(nfp, "NFP", start_date=start_date)
    priv_df = transforms.with_change_and_ma(priv, "Private", start_date=start_date)

    fig = make_subplots(rows=1, cols=2, subplot_titles=("NFP", "Private Payrolls"))
    fig.add_trace(go.Scatter(x=nfp_df.index, y=nfp_df["NFP Δ"], name="NFP", mode="lines"), row=1, col=1)
    fig.add_trace(go.Scatter(x=nfp_df.index, y=nfp_df["NFP Δ 3m MA"], name="NFP 3m MA", mode="lines"), row=1, col=1)
    fig.add_trace(go.Scatter(x=priv_df.index, y=priv_df["Private Δ"], name="Private", mode="lines"), row=1, col=2)
    fig.add_trace(go.Scatter(x=priv_df.index, y=priv_df["Private Δ 3m MA"], name="Private 3m MA", mode="lines"), row=1, col=2)

    return plotting.apply_layout(fig, title="NFP & Private Payrolls (m/m change, 000s)")


def claims(start_date: str = config.DEFAULT_START_DATE) -> go.Figure:
    """Initial and Continued Claims side-by-side."""
    icsa = get_series("ICSA")
    ccsa = get_series("CCSA")

    icsa_df = icsa.to_frame("Claims")
    icsa_df["3m MA"] = icsa_df["Claims"].rolling(12).mean()  # 12-week MA on weekly data
    icsa_df = icsa_df.loc[icsa_df.index >= pd.to_datetime(start_date)]

    ccsa_df = ccsa.to_frame("Continued Claims")
    ccsa_df = ccsa_df.loc[ccsa_df.index >= pd.to_datetime(start_date)]

    fig = make_subplots(rows=1, cols=2, subplot_titles=("Initial Claims", "Continued Claims"))
    fig.add_trace(go.Scatter(x=icsa_df.index, y=icsa_df["Claims"], name="Initial Claims", mode="lines"), row=1, col=1)
    fig.add_trace(go.Scatter(x=icsa_df.index, y=icsa_df["3m MA"], name="12w MA", mode="lines"), row=1, col=1)
    fig.add_trace(go.Scatter(x=ccsa_df.index, y=ccsa_df["Continued Claims"], name="Continued Claims", mode="lines"), row=1, col=2)

    return plotting.apply_layout(fig, title="Unemployment Claims")


def jolts(start_date: Optional[str] = None) -> go.Figure:
    """JOLTS 4-panel: openings level, hires rate, quits rate, layoffs rate (capped 2.5%)."""
    series = {
        "Job openings (level, ths)": ("JTSJOL", False),
        "Hires rate (%)": ("JTSHIR", True),
        "Quits rate (%)": ("JTSQUR", True),
        "Layoffs & discharges rate (%)": ("JTSLDR", True),
    }

    fig = make_subplots(rows=2, cols=2, subplot_titles=tuple(series.keys()))
    positions = [(1, 1), (1, 2), (2, 1), (2, 2)]

    for (label, (code, is_rate)), (r, c) in zip(series.items(), positions):
        s = get_series(code).dropna()
        if start_date is not None:
            s = s.loc[s.index >= pd.to_datetime(start_date)]
        fig.add_trace(go.Scatter(x=s.index, y=s.values, name=label, mode="lines"), row=r, col=c)
        if is_rate:
            fig.update_yaxes(ticksuffix="%", row=r, col=c)
        fig.update_xaxes(showgrid=False, row=r, col=c)
        fig.update_yaxes(zeroline=True, showgrid=True, row=r, col=c)

    # Cap layoffs y-axis to keep COVID spike from flattening the rest of the chart.
    fig.update_yaxes(range=[0, 2.5], row=2, col=2)

    return plotting.apply_layout(fig, title="JOLTS Dashboard", height=800, show_legend=False)


def unemployment_and_jwg(start_date: str = config.DEFAULT_START_DATE) -> go.Figure:
    """Unemployment level + Job-Worker Gap (Job Openings / Unemployment)."""
    openings = get_series("JTSJOL").to_frame("Job openings")
    unemp = get_series("UNEMPLOY").to_frame("Unemployment")

    merged = openings.merge(unemp, left_index=True, right_index=True)
    merged["Job-Worker Ratio"] = merged["Job openings"] / merged["Unemployment"]

    unemp_trim = unemp.loc[unemp.index >= pd.to_datetime(start_date)]
    merged_trim = merged.loc[merged.index >= pd.to_datetime(start_date)]

    fig = make_subplots(rows=1, cols=2, subplot_titles=("Unemployment (level, ths)", "Job-Worker Ratio (openings / unemployed)"))
    fig.add_trace(go.Scatter(x=unemp_trim.index, y=unemp_trim["Unemployment"], name="Unemployment", mode="lines"), row=1, col=1)
    fig.add_trace(go.Scatter(x=merged_trim.index, y=merged_trim["Job-Worker Ratio"], name="J/W Ratio", mode="lines"), row=1, col=2)

    return plotting.apply_layout(fig, title="Unemployment & Job-Worker Gap")


def nfp_sectors_grid(start_date: str = config.DEFAULT_START_DATE) -> go.Figure:
    """17-panel sector breakdown of NFP m/m changes with 3m MA overlays."""
    panels = []
    titles = []
    rows = (len(NFP_SECTOR_SERIES) + 1) // 2

    for i, (series_id, name) in enumerate(NFP_SECTOR_SERIES):
        s = get_series(series_id)
        df = transforms.with_change_and_ma(s, name, start_date=start_date)
        r = i // 2 + 1
        c = i % 2 + 1
        titles.append(name)
        panels.append({
            "row": r,
            "col": c,
            "traces": plotting.line_and_ma_traces(
                df, level_col=f"{name} Δ", ma_col=f"{name} Δ 3m MA", base_name=name
            ),
        })

    return plotting.grid_from_traces(
        panels=panels,
        rows=rows,
        cols=2,
        title="NFP by Sector — Monthly Change & 3m MA",
        subplot_titles=titles,
        height_per_row=300,
        show_legend=False,
    )


def diffusion_index_chart(
    extended: bool = True,
    start_date: str = config.DEFAULT_DIFFUSION_START_DATE,
    months_change: int = 3,
    ma_months: int = 6,
) -> go.Figure:
    """Payroll diffusion index — % of sectors with positive 3m change.

    Args:
        extended: True for the 17-sector universe, False for the 10-sector basic.
    """
    universe = DIFFUSION_EXTENDED if extended else DIFFUSION_BASIC
    label = "Extended (17 sectors)" if extended else "Basic (10 sectors)"

    # Fetch every series; gracefully skip any that fail.
    level_map: dict[str, pd.Series] = {}
    for name, sid in universe.items():
        s = get_series_safe(sid, freq="MS")
        if s is not None:
            level_map[name] = s

    levels = transforms.assemble_levels(level_map)
    diff = transforms.diffusion_index(
        levels, months_change=months_change, ma_months=ma_months, start_date=start_date,
    )

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=diff.index, y=diff["Diffusion (%)"],
        name=f"Diffusion (% sectors with Δ{months_change}m > 0)", mode="lines",
    ))
    fig.add_trace(go.Scatter(
        x=diff.index, y=diff["Diffusion MA"],
        name=f"{ma_months}m MA", mode="lines",
    ))
    fig.update_yaxes(ticksuffix="%")

    return plotting.apply_layout(
        fig,
        title=f"Payroll Diffusion Index — {label}",
        height=500,
    )


def cyclical_view(
    view: Literal["contribution", "grid"] = "contribution",
    start_date: str = config.DEFAULT_START_DATE,
) -> go.Figure:
    """Cyclical vs non-cyclical NFP.

    - "contribution": stacked bars of cyclical/non-cyclical Δ + headline NFP Δ line.
                      Best for seeing which slice is driving the headline number.
    - "grid":         2-panel time series showing each component's m/m change + 3m MA.
                      Best for seeing each series' own trend.
    """
    nfp = get_series("PAYEMS")
    gov = get_series("USGOVT")
    ehs = get_series("USEHS")

    chg = transforms.cyclical_split(nfp, gov, ehs)
    chg_trim = chg.loc[chg.index >= pd.to_datetime(start_date)].dropna(
        subset=["Cyclical Δ", "Non-cyclical Δ"]
    )

    if view == "contribution":
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=chg_trim.index, y=chg_trim["Cyclical Δ"],
            name="Cyclical (NFP − Gov − Edu&Health)",
        ))
        fig.add_trace(go.Bar(
            x=chg_trim.index, y=chg_trim["Non-cyclical Δ"],
            name="Non-cyclical (Gov + Edu&Health)",
        ))
        fig.add_trace(go.Scatter(
            x=chg_trim.index, y=chg_trim["NFP Δ"],
            name="Headline NFP Δ", mode="lines", line=dict(width=2),
        ))
        fig.add_trace(go.Scatter(
            x=chg_trim.index, y=chg_trim["NFP Δ 3m MA"],
            name="NFP Δ 3m MA", mode="lines", line=dict(width=1, dash="dot"),
        ))
        fig.update_layout(barmode="relative")
        fig.update_yaxes(zeroline=True, zerolinewidth=1)
        return plotting.apply_layout(
            fig, title="NFP Contribution — Cyclical vs Non-Cyclical (m/m, 000s)"
        )

    # view == "grid"
    cyc_ma = chg_trim["Cyclical Δ"].rolling(3).mean()
    nc_ma = chg_trim["Non-cyclical Δ"].rolling(3).mean()

    fig = make_subplots(rows=1, cols=2, subplot_titles=("Cyclical Δ", "Non-cyclical Δ"))
    fig.add_trace(go.Scatter(x=chg_trim.index, y=chg_trim["Cyclical Δ"], name="Cyclical", mode="lines"), row=1, col=1)
    fig.add_trace(go.Scatter(x=chg_trim.index, y=cyc_ma, name="Cyclical 3m MA", mode="lines"), row=1, col=1)
    fig.add_trace(go.Scatter(x=chg_trim.index, y=chg_trim["Non-cyclical Δ"], name="Non-cyclical", mode="lines"), row=1, col=2)
    fig.add_trace(go.Scatter(x=chg_trim.index, y=nc_ma, name="Non-cyclical 3m MA", mode="lines"), row=1, col=2)

    return plotting.apply_layout(fig, title="Cyclical vs Non-Cyclical NFP — Grid View")


# ---- Section assembler -------------------------------------------------------

def build(
    start_date: str = config.DEFAULT_START_DATE,
    diffusion_extended: bool = True,
    cyclical_view_mode: Literal["contribution", "grid"] = "contribution",
) -> dict:
    """Build the full Labor section. Returns a dict that app.py can iterate over.

    Shape:
        {
            "title": str,
            "charts": [
                {"id": str, "title": str, "fig": go.Figure, "commentary": str | None},
                ...
            ],
        }
    """
    charts = [
        {
            "id": "nfp_overview",
            "title": "NFP & Private Payrolls",
            "fig": nfp_overview(start_date=start_date),
            "commentary": "Headline payrolls and the private-sector subset. The 3m MA is the more reliable signal — the single-month print is noisy and frequently revised.",
        },
        {
            "id": "claims",
            "title": "Unemployment Claims",
            "fig": claims(start_date=start_date),
            "commentary": "Weekly initial claims is the highest-frequency labor-market signal. Continued claims (insured unemployed) is slower-moving and tracks the duration side of the unemployment story.",
        },
        {
            "id": "jolts",
            "title": "JOLTS",
            "fig": jolts(),
            "commentary": "Quits rate is the cleanest signal of labor-market tightness — workers quit when they're confident they can find a better job. Layoffs y-axis capped at 2.5% so COVID doesn't flatten the rest.",
        },
        {
            "id": "unemployment_jwg",
            "title": "Unemployment & Job-Worker Gap",
            "fig": unemployment_and_jwg(start_date=start_date),
            "commentary": "Job-worker ratio (openings / unemployed) was a key tightness gauge in 2022. Watch for it crossing back below 1.0.",
        },
        {
            "id": "nfp_sectors",
            "title": "NFP by Sector",
            "fig": nfp_sectors_grid(start_date=start_date),
            "commentary": "17-panel breakdown. The non-cyclical sectors (Government, Education & Health) tend to dominate headline NFP late in cycles — see the cyclical chart below.",
        },
        {
            "id": "diffusion",
            "title": f"Payroll Diffusion Index ({'Extended' if diffusion_extended else 'Basic'})",
            "fig": diffusion_index_chart(extended=diffusion_extended),
            "commentary": "% of sectors with positive 3m job growth. Historically dips below 50% around recessions. Toggle between basic (10 sectors) and extended (17 sectors) in the sidebar.",
        },
        {
            "id": "cyclical",
            "title": f"Cyclical vs Non-Cyclical NFP ({cyclical_view_mode})",
            "fig": cyclical_view(view=cyclical_view_mode, start_date=start_date),
            "commentary": "Cyclical = NFP excluding Government and Education & Health. When non-cyclical is doing the heavy lifting, headline NFP is overstating private-sector labor demand.",
        },
    ]

    return {
        "title": "Labor Market",
        "charts": charts,
    }
