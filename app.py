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

from sections import labor, inflation


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
            "If you're running on Streamlit Cloud, add your key under "
            "**Settings → Secrets**:\n\n"
            "```toml\nFRED_API_KEY = \"your_key_here\"\n```"
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

    st.divider()
    if st.button("Clear FRED cache", help="Forces a fresh fetch from FRED on the next interaction."):
        from core.fred_client import clear_cache
        clear_cache()
        st.cache_data.clear()
        st.success("Cache cleared. Rerun to refetch.")


# ---- Main layout ------------------------------------------------------------

st.title("US Macro Dashboard")
st.caption("FRED-based labor, inflation, growth, and rates indicators.")

tabs = st.tabs(["Labor", "Inflation"])

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
