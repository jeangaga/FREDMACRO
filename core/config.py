"""Configuration: API key loading and project-wide defaults.

Order of resolution for the FRED key:
  1. st.secrets["FRED_API_KEY"]  (Streamlit runtime)
  2. os.environ["FRED_API_KEY"]
  3. .env file in the project root

Keeping this in one place means core/ and sections/ never need to know
which environment they're running in.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

# ---- Project-wide defaults ----------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = PROJECT_ROOT / ".cache"
CACHE_DIR.mkdir(exist_ok=True)

DEFAULT_START_DATE = "2022-01-01"
DEFAULT_DIFFUSION_START_DATE = "2015-01-01"   # diffusion charts need more history
DEFAULT_MA_WINDOW = 3                          # months
DEFAULT_HEIGHT = 500                           # plot height in px


# ---- Key loading --------------------------------------------------------------

def _try_streamlit_secrets() -> Optional[str]:
    """Read FRED_API_KEY from st.secrets if Streamlit is importable and configured.

    Importing streamlit at module-load time would couple core/ to Streamlit, so
    we import lazily and swallow all errors.
    """
    try:
        import streamlit as st  # noqa: WPS433 (intentional lazy import)
        # st.secrets raises if not configured; treat any failure as "no key"
        return st.secrets["FRED_API_KEY"]  # type: ignore[index]
    except Exception:
        return None


def _try_env() -> Optional[str]:
    return os.environ.get("FRED_API_KEY")


def _try_dotenv() -> Optional[str]:
    try:
        from dotenv import load_dotenv  # noqa: WPS433
        load_dotenv(PROJECT_ROOT / ".env")
        return os.environ.get("FRED_API_KEY")
    except Exception:
        return None


def get_fred_key() -> str:
    """Return the FRED API key, trying every source in turn.

    Raises:
        RuntimeError: if no key is found in any source.
    """
    for source in (_try_streamlit_secrets, _try_env, _try_dotenv):
        key = source()
        if key:
            return key

    raise RuntimeError(
        "FRED_API_KEY not found. Set it in one of:\n"
        "  - .streamlit/secrets.toml  (for Streamlit)\n"
        "  - environment variable FRED_API_KEY\n"
        "  - .env file in the project root\n"
        "Get a free key at https://fredaccount.stlouisfed.org/apikey"
    )
