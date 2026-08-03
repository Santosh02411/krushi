"""
market_model.py
----------------
Replaces the old "simulated seasonal pattern" market feature with an actual
ML model trained on real government mandi (market) data.

Dataset: data/market_price_data.csv — real Agmarknet-sourced daily market
records (arrivals, min/max/modal price) for Potato, Tomato and Wheat across
markets in Haryana, Punjab, Uttar Pradesh and Uttarakhand.

This is real but NARROW: three crops, four states. Rather than papering
over that gap with invented numbers for the other 19 crops in the crop
model, this module is explicit about coverage — get_price_estimate()
returns covered=False for anything outside the training data, and app.py /
the frontend show an honest "no real market dataset for this crop yet"
message instead of a fabricated figure.

Target variable is Modal Price predicted from State/District/Market/Variety/
Crop/Arrivals — deliberately NOT from that day's Min/Max price, since a
farmer asking "what will this crop fetch" does not already know today's
price range. That makes this a genuinely harder, honest prediction problem:
held-out R^2 is modest (~0.4), and the UI says so rather than implying
false precision.
"""

import os
import math
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import r2_score, mean_absolute_error

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(BASE_DIR, "data", "market_price_data.csv")
BY_LOCATION_PATH = os.path.join(BASE_DIR, "data", "market_prices_by_location.csv")

TARGET_COL = "Modal Price (Rs./Quintal)"
LEAK_COLS = ["Min Price (Rs./Quintal)", "Max Price (Rs./Quintal)"]

CROP_COLUMNS = {"potato": "Crop_Potato", "tomato": "Crop_Tomato", "wheat": "Crop_Wheat"}

# Real coordinates for the markets present in data/market_prices_by_location.csv.
# These are fixed, well-known towns, so they're hardcoded rather than geocoded
# on every request. A couple of small/ambiguous town names are deliberately
# left out rather than guessed at.
MARKET_COORDS = {
    "Amritsar": (31.63, 74.87), "Farukh Nagar": (28.45, 76.81), "Gurgaon": (28.46, 77.03),
    "Haridwar Union": (29.95, 78.16), "Khanna": (30.70, 76.22), "Khatauli": (29.28, 77.73),
    "Lakshar": (29.77, 78.03), "Ludhiana": (30.90, 75.86), "Mawana": (29.10, 77.93),
    "Meerut": (28.98, 77.71), "Muzzafarnagar": (29.47, 77.70), "Pataudi": (28.31, 76.77),
    "Rayya": (31.80, 75.13), "Roorkee": (29.85, 77.89), "Sardhana": (29.15, 77.61),
    "Sohna": (28.25, 77.07),
    # "Mehta" and "Shahpur" omitted — town name is ambiguous without a
    # reliable source, so distance to them is reported as unknown rather
    # than guessed.
}


def _haversine_km(lat1, lon1, lat2, lon2):
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


class MarketPriceModel:
    def __init__(self):
        self.df = pd.read_csv(DATA_PATH)
        self.by_location = pd.read_csv(BY_LOCATION_PATH)
        self.feature_cols = [c for c in self.df.columns if c not in LEAK_COLS + [TARGET_COL]]
        self.model = None
        self.test_r2 = None
        self.test_mae = None
        self.covered_crops = list(CROP_COLUMNS.keys())
        self._train()

    def _train(self):
        X = self.df[self.feature_cols]
        y = self.df[TARGET_COL]

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )
        eval_model = RandomForestRegressor(n_estimators=300, max_depth=14, random_state=42, n_jobs=-1)
        eval_model.fit(X_train, y_train)
        preds = eval_model.predict(X_test)
        self.test_r2 = round(r2_score(y_test, preds), 3)
        self.test_mae = round(mean_absolute_error(y_test, preds), 1)

        self.model = RandomForestRegressor(n_estimators=300, max_depth=14, random_state=42, n_jobs=-1)
        self.model.fit(X, y)

        print(
            f"[market_model] Trained RandomForestRegressor on {len(self.df)} real mandi records "
            f"(Potato/Tomato/Wheat, 4 states) | held-out R2={self.test_r2} MAE=Rs.{self.test_mae}/quintal"
        )

    def get_model_info(self):
        return {
            "algorithm": "RandomForestRegressor (scikit-learn)",
            "training_records": len(self.df),
            "covered_crops": self.covered_crops,
            "test_r2": self.test_r2,
            "test_mae_rs_per_quintal": self.test_mae,
            "dataset": "Real Agmarknet-sourced mandi price data (data/market_price_data.csv), "
                       "Haryana/Punjab/Uttar Pradesh/Uttarakhand",
            "honesty_note": "Predicts price from crop/location/arrivals only (not from that day's "
                             "min/max), so accuracy is moderate — price also depends on factors this "
                             "dataset doesn't capture (weather shocks, festival demand, transport cost).",
        }

    def is_covered(self, crop):
        return (crop or "").strip().lower() in CROP_COLUMNS

    def get_price_estimate(self, crop, state=None):
        crop_key = (crop or "").strip().lower()
        if crop_key not in CROP_COLUMNS:
            return {"covered": False}

        # Build a representative feature row: average arrivals for this crop,
        # and the state one-hot if we recognize it (else the most common state
        # for this crop in the training data).
        crop_col = CROP_COLUMNS[crop_key]
        subset = self.df[self.df[crop_col] == 1]

        row = {c: 0 for c in self.feature_cols}
        row["Arrivals (Tonnes)"] = float(subset["Arrivals (Tonnes)"].median())
        row[crop_col] = 1

        state_col = None
        if state:
            candidate = f"State Name_{state.strip().title()}"
            if candidate in self.feature_cols:
                state_col = candidate
        if not state_col:
            state_counts = subset[[c for c in self.feature_cols if c.startswith("State Name_")]].sum()
            state_col = state_counts.idxmax()
        row[state_col] = 1

        variety_col = f"Variety_{crop_key.title()}"
        if variety_col in self.feature_cols:
            row[variety_col] = 1

        input_df = pd.DataFrame([row])[self.feature_cols]
        predicted = float(self.model.predict(input_df)[0])

        actual_range = subset[TARGET_COL]
        return {
            "covered": True,
            "crop": crop_key,
            "predicted_modal_price": round(predicted, 0),
            "observed_price_range": [round(float(actual_range.min()), 0), round(float(actual_range.max()), 0)],
            "observed_median_price": round(float(actual_range.median()), 0),
            "sample_size": int(len(subset)),
            "test_r2": self.test_r2,
            "test_mae_rs_per_quintal": self.test_mae,
            "state_used": state_col.replace("State Name_", ""),
            "data_source": "real (Agmarknet mandi records, ML-predicted)",
        }

    # ------------------------------------------------------------------ #
    # Real per-market current prices (decoded from the raw mandi records,
    # not model output) — this is what a "current mandi prices" screen
    # should show: what real markets actually reported.
    # ------------------------------------------------------------------ #
    def get_market_prices(self, crop, state=None):
        crop_title = (crop or "").strip().title()
        subset = self.by_location[self.by_location["Crop"] == crop_title]
        if state:
            state_matches = subset[subset["State"].str.lower() == state.strip().lower()]
            if len(state_matches) > 0:
                subset = state_matches

        if subset.empty:
            return {"covered": False, "crop": crop}

        grouped = subset.groupby(["Market", "State", "District"])["Modal_Price"].agg(
            ["median", "min", "max", "count"]
        ).reset_index()

        markets = [{
            "market": r["Market"], "state": r["State"], "district": r["District"],
            "typical_price": round(r["median"], 0),
            "price_range": [round(r["min"], 0), round(r["max"], 0)],
            "records": int(r["count"]),
        } for _, r in grouped.sort_values("median", ascending=False).iterrows()]

        return {
            "covered": True,
            "crop": crop,
            "markets": markets,
            "data_source": "real (Agmarknet mandi records)",
            "note": "Prices are typical (median) values observed across real market records for "
                    "this crop — the dataset has no per-day timestamp, so this is a real snapshot "
                    "distribution rather than a live daily quote.",
        }

    def get_nearby_markets(self, crop, lat, lon, max_results=5):
        """Rank real markets carrying this crop by distance from the given
        coordinates. Only markets with a known, confidently-sourced
        coordinate are ranked; others are omitted rather than guessed."""
        result = self.get_market_prices(crop)
        if not result.get("covered"):
            return result

        ranked = []
        for m in result["markets"]:
            coords = MARKET_COORDS.get(m["market"])
            if not coords:
                continue
            dist = _haversine_km(lat, lon, coords[0], coords[1])
            ranked.append({**m, "distance_km": round(dist, 1), "lat": coords[0], "lon": coords[1]})

        ranked.sort(key=lambda m: m["distance_km"])
        return {
            "covered": bool(ranked),
            "crop": crop,
            "markets": ranked[:max_results],
            "data_source": "real (Agmarknet mandi records + fixed real market coordinates)",
        }
