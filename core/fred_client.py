"""FRED API client with on-disk caching.

`joblib.Memory` is used as the cache layer because it works identically in
Streamlit, Colab, and a plain Python REPL — unlike `@st.cache_data`, which is
Streamlit-only and would break the "single source of truth" promise.

Public API:
    get_series(series_id, freq=None) -> pd.Series
        Cached fetch. Raises on failure.

    get_series_safe(series_id, freq=None) -> pd.Series | None
        Cached fetch that returns None instead of raising. Use when a missing
        series should be silently skipped (e.g. payroll diffusion index that
        unions many sector mnemonics).
"""

from __future__ import annotations

from functools import lru_cache
from typing import Optional

import pandas as pd
from fredapi import Fred
from joblib import Memory

from . import config


_memory = Memory(config.CACHE_DIR, verbose=0)


@lru_cache(maxsize=1)
def _fred() -> Fred:
    """Singleton FRED client, lazily constructed so importing this module
    doesn't fail if the key isn't set yet (e.g. during test collection)."""
    return Fred(api_key=config.get_fred_key())


@_memory.cache
def _fetch_series_raw(series_id: str) -> pd.Series:
    """Cached raw fetch. Cache key is just the series_id — re-run by deleting
    the .cache/ directory or calling clear_cache()."""
    s = _fred().get_series(series_id)
    s.name = series_id
    return s


def get_series(series_id: str, freq: Optional[str] = None) -> pd.Series:
    """Fetch a FRED series (cached).

    Args:
        series_id: FRED mnemonic, e.g. 'PAYEMS'.
        freq: Optional pandas frequency string (e.g. 'MS' for month-start).
              If provided, the series is reindexed via .asfreq(freq).

    Returns:
        pd.Series indexed by date.
    """
    s = _fetch_series_raw(series_id).copy()
    if freq is not None:
        s = s.asfreq(freq)
    return s


def get_series_safe(series_id: str, freq: Optional[str] = None) -> Optional[pd.Series]:
    """Fetch a FRED series, returning None on any failure (including empty result).

    Use this when iterating over a dict of mnemonics where some may not exist
    (e.g. the diffusion index that mixes US* aliases and CESxxxxxxxx codes).
    """
    try:
        s = get_series(series_id, freq=freq)
        if s is None or len(s.dropna()) == 0:
            return None
        return s
    except Exception:
        return None


def clear_cache() -> None:
    """Wipe the on-disk cache. Call when you want fresh data."""
    _memory.clear(warn=False)
