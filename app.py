"""Streamlit production dashboard — orchestration only.

This file is intentionally thin. All data and chart logic lives in core/ and
sections/, which are the single source of truth shared with Colab notebooks.

Run locally with:
    streamlit run app.py
"""

from __future__ import annotations

import traceback
from datetime import date

import streamlit as st

from sections import labor, inflation, income


# ---- Page config -------------------------------------------------------------

st.set_page_config(
    page_title="US Macro Dashboard",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ---- Cached section builds --------------------------------------------------
# joblib.Memory in core/fred_client handles the FRED-API cache; @st.cache_data
# below is the in-memory Streamlit layer that avoids re-running build() Python
# code on every widget interaction.

@st.cache_data(ttl=60 * 60, show_spinner="Loading labor market data...")
def cached_labor(start_date: str, diffusion_extended: bool, cyclical_view: str) -> dict:
    return labor.build(
        start_date=start_date,
        diffusion_extended=diffusion_extended,
        cyclical_view_mode=cyclical_view,
    )


@st.cache_data(ttl=60 * 60, show_spinner="Loading inflation data...")
def cached_inflation(start_date: str) -> dict:
    return inflation.build(start_date=start_date)


@st.cache_data(ttl=60 * 60, show_spinner="Loading wages & income data...")
def cached_income(start_date: str, income_measure: str) -> dict:
    return income.build(start_date=start_date, income_measure=income_measure)


# ---- Rendering helper -------------------------------------------------------

def render_section(loader, *args, **kwargs) -> None:
    """Run `loader(*args, **kwargs)` inside a try/except and render the section.

    Catching here means a failure in one tab doesn't kill the rest of the app
    and the user sees a real error message instead of an infinite spinner.
    """
    try:
        section = loader(*args, **kwargs)
    except RuntimeError as e:
        # Most common: FRED_API_KEY missing from Streamlit Cloud secrets
        st.error(f"Configuration error: {e}")
        st.info(
            "If you're running on Streamlit Cloud, add your keys under "
            "**Settings → Secrets**:\n\n"
            "```toml\nFRED_API_KEY = \"your_key_here\"\nBLS_API_KEY = \"your_key_here\"\n```"
        )
        return
    except Exception as e:  # noqa: BLE001
        st.error(f"Failed to load section: {type(e).__name__}: {e}")
        with st.expander("Traceback"):
            st.code(traceback.format_exc())
        return

    st.header(section["title"])
    for chart in section["charts"]:
        st.subheader(chart["title"])
        if chart.get("error"):
            # A single chart failed (e.g. BLS key missing) — keep the rest of the tab alive.
            st.warning(f"This chart could not be built: {chart['error']}")
        else:
            st.plotly_chart(chart["fig"], use_container_width=True)
        if chart.get("commentary"):
            st.caption(chart["commentary"])
        st.divider()


# ---- Sidebar controls -------------------------------------------------------

with st.sidebar:
    st.title("Controls")

    st.subheader("Date range")
    labor_start = st.date_input(
        "Labor start date",
        value=date(2022, 1, 1),
        min_value=date(2000, 1, 1),
        max_value=date.today(),
        help="Applied to all labor charts. The diffusion index uses its own longer history.",
    )
    inflation_start = st.date_input(
        "Inflation start date",
        value=date(2015, 8, 1),
        min_value=date(2000, 1, 1),
        max_value=date.today(),
        help="CPI dashboard default starts in 2015 to capture the pre-COVID baseline.",
    )
    income_start = st.date_input(
        "Wages & Income start date",
        value=date(2015, 1, 1),
        min_value=date(2000, 1, 1),
        max_value=date.today(),
        help="Applied to all Wages & Income charts. Growth rates are computed on full history first.",
    )

    st.subheader("Labor toggles")
    diffusion_choice = st.radio(
        "Diffusion index",
        options=["Extended (17 sectors)", "Basic (10 sectors)"],
        index=0,
        help="Extended adds sub-sector breakdowns (durable/nondurable mfg, etc.).",
    )
    diffusion_extended = diffusion_choice.startswith("Extended")

    cyclical_choice = st.radio(
        "Cyclical view",
        options=["Stacked bars (contribution)", "Grid panels"],
        index=0,
        help="Stacked: see what's driving headline NFP. Grid: see each component's trend.",
    )
    cyclical_view_mode = "contribution" if cyclical_choice.startswith("Stacked") else "grid"

    st.subheader("Wages & Income toggles")
    income_measure_choice = st.radio(
        "Household income measure",
        options=["YoY", "3m annualized", "6m annualized"],
        index=0,
        help="Growth measure for the Household Income chart.",
    )
    income_measure = {"YoY": "yoy", "3m annualized": "3m", "6m annualized": "6m"}[income_measure_choice]

    st.divider()
    if st.button("Clear data cache", help="Forces a fresh fetch from FRED and BLS on the next interaction."):
        from core.fred_client import clear_cache
        from core.bls_client import clear_cache as clear_bls_cache
        clear_cache()
        clear_bls_cache()
        st.cache_data.clear()
        st.success("Cache cleared. Rerun to refetch.")


# ---- Main layout ------------------------------------------------------------

st.title("US Macro Dashboard")
st.caption("FRED-based labor, inflation, and wages & income indicators.")

tabs = st.tabs(["Labor", "Inflation", "Wages & Income"])

with tabs[0]:
    render_section(
        cached_labor,
        start_date=labor_start.isoformat(),
        diffusion_extended=diffusion_extended,
        cyclical_view=cyclical_view_mode,
    )

with tabs[1]:
    render_section(
        cached_inflation,
        start_date=inflation_start.isoformat(),
    )

with tabs[2]:
    render_section(
        cached_income,
        start_date=income_start.isoformat(),
        income_measure=income_measure,
    )
