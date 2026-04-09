"""Legacy wrapper — prefer ``efuse-dashboard`` or ``streamlit run efuse_datagen/dashboard_app.py``.

This file exists only so ``streamlit run dashboard/app.py`` still works from
the repo root.  All real code lives in ``efuse_datagen/dashboard_app.py``.
"""

from efuse_datagen.dashboard_app import *  # noqa: F401,F403