"""Streamlit production dashboard — orchestration only.

This file is intentionally thin. All data and chart logic lives in core/ and
sections/, which are the single source of truth shared with Colab notebooks.

Run locally with:
    streamlit run app.py
"""

from __future__ import annotations

from datetime import date

import streamlit as st

from sections import labor


# ---- Page config -------------------------------------------------------------

st.set_page_config(
    page_title="US Macro Dashboard",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ---- Cached section build ---------------------------------------------------
# Wraps labor.build() so Streamlit doesn't re-fetch FRED data on every widget
# change. Core caching (joblib.Memory) handles the FRED-API side; this is the
# in-memory Streamlit layer that avoids re-running the build() Python code itself.

@st.cache_data(ttl=60 * 60, show_spinner="Loading labor market data...")
def cached_labor(start_date: str, diffusion_extended: bool, cyclical_view: str) -> dict:
    return labor.build(
        start_date=start_date,
        diffusion_extended=diffusion_extended,
        cyclical_view_mode=cyclical_view,
    )


# ---- Sidebar controls -------------------------------------------------------

with st.sidebar:
    st.title("Controls")

    start = st.date_input(
        "Start date",
        value=date(2022, 1, 1),
        min_value=date(2000, 1, 1),
        max_value=date.today(),
        help="Applied to all charts. Diffusion index uses its own longer history.",
    )

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
st.caption("FRED-based labor, growth, and inflation indicators. Updated on each load.")

tabs = st.tabs(["Labor"])

with tabs[0]:
    section = cached_labor(
        start_date=start.isoformat(),
        diffusion_extended=diffusion_extended,
        cyclical_view=cyclical_view_mode,
    )

    st.header(section["title"])

    for chart in section["charts"]:
        st.subheader(chart["title"])
        st.plotly_chart(chart["fig"], use_container_width=True)
        if chart.get("commentary"):
            st.caption(chart["commentary"])
        st.divider()
