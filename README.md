# FRED Macro Dashboard

Modular US macro dashboard built on FRED data. The same Python modules drive both:

- **Streamlit** — production dashboard interface (`app.py`)
- **Google Colab** — research / testing notebooks (`notebooks/`)

`core/` and `sections/` are the single source of truth. Neither imports Streamlit, so they run identically in both environments.

## Layout

```
fred_macro/
├── core/
│   ├── config.py         # key loading + defaults
│   ├── fred_client.py    # cached FRED fetcher
│   ├── transforms.py     # diff, rolling MA, diffusion index, cyclical split
│   └── plotting.py       # layout helpers + grid builder
├── sections/
│   └── labor.py          # NFP, claims, JOLTS, diffusion, cyclical view
├── notebooks/
│   └── labor.ipynb       # Colab workbench mirroring sections/labor.py
├── app.py                # Streamlit entry
├── .streamlit/secrets.toml  # FRED_API_KEY (gitignored)
└── requirements.txt
```

## Local setup

```bash
pip install -r requirements.txt
pip install -e .          # makes `from core...` and `from sections...` work everywhere
streamlit run app.py
```

## Colab setup

In the first cell of any notebook:

```python
!git clone <your-repo-url> /content/fred_macro
%cd /content/fred_macro
!pip install -q -e .
import os
os.environ["FRED_API_KEY"] = "your_key_here"   # or use Colab user secrets
```

## API key resolution order

`core.config.get_fred_key()` tries, in order:

1. `st.secrets["FRED_API_KEY"]` (when running under Streamlit)
2. `os.environ["FRED_API_KEY"]`
3. `.env` file in the project root (via `python-dotenv`)

## Adding a new section

1. Create `sections/<name>.py` with chart functions returning `go.Figure` and a `build()` function returning the section dict.
2. Add a tab in `app.py`.
3. Create `notebooks/<name>.ipynb` as a research mirror.

Keep `streamlit` imports out of `core/` and `sections/`. If you need Streamlit-specific caching, wrap calls in `app.py`.
