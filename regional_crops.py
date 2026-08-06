"""
regional_crops.py
--------------------
Whether a crop is actually, historically grown in a given state — built
from real Indian government crop-production records (the same
data/crop_yield_data.csv used by yield_model.py), not guessed.

This exists because the crop recommendation model itself has NO location
input at all — it was trained purely on N/P/K/temperature/humidity/pH/
rainfall (see ml_models.py). Selecting a state in the form did nothing to
the recommendation itself before this module; it only affected weather
auto-fill and the yield/price lookups shown alongside it. That's a real
gap: two farmers in different states entering the same soil numbers would
get the exact same crop list regardless of what's actually grown near
them. This module doesn't change the ML model, but it lets app.py
re-prioritize its output using real regional cultivation history.

Coverage: only the 11 crops this dataset covers (see yield_model.py's
CROP_YIELD_MAP) have a real answer. Every other crop returns None
("unknown regional relevance") rather than a guessed True/False.
"""

import os
import pandas as pd

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(BASE_DIR, "data", "crop_yield_data.csv")

CROP_MAP = {
    "rice": "Rice", "maize": "Maize", "chickpea": "Gram", "pigeonpeas": "Arhar/Tur",
    "mothbeans": "Moth", "mungbean": "Moong(Green Gram)", "blackgram": "Urad",
    "lentil": "Masoor", "banana": "Banana", "cotton": "Cotton(lint)", "jute": "Jute",
}

_df = pd.read_csv(DATA_PATH)
_df["Crop"] = _df["Crop"].astype(str).str.strip()
_df["State"] = _df["State"].astype(str).str.strip()

# crop_key -> set of real states with at least one production record
_STATE_PRESENCE = {
    crop_key: set(_df[_df["Crop"] == dataset_name]["State"].unique())
    for crop_key, dataset_name in CROP_MAP.items()
}

# All states that appear ANYWHERE in this dataset (for any crop). Some
# states (e.g. Rajasthan) are entirely absent from this specific dataset —
# a real gap in the source data, not evidence about what's grown there. A
# state missing from this set must return "unknown", never "false".
_ALL_DATASET_STATES = set(_df["State"].unique())


def is_grown_in_state(crop, state):
    """True if we have a real production record for this crop in this
    state. False only if the state itself has other real records in this
    dataset but none for this crop (a meaningful negative). None if either
    the crop isn't covered, or the state doesn't appear in this dataset at
    all (e.g. Rajasthan) — a data gap, not a signal either way."""
    crop_key = (crop or "").strip().lower()
    if crop_key not in _STATE_PRESENCE or not state:
        return None
    state = state.strip()
    if state not in _ALL_DATASET_STATES:
        return None
    return state in _STATE_PRESENCE[crop_key]


def is_covered(crop):
    return (crop or "").strip().lower() in _STATE_PRESENCE
