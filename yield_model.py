"""
yield_model.py
--------------
Expected-yield prediction, trained on real Indian government crop
production data (data/crop_yield_data.csv — 19,689 real district/state/year
records, columns: Crop, Season, State, Area, Production, Annual_Rainfall,
Fertilizer, Pesticide, Yield, Avg/Max/Min Temperature).

Coverage: 11 of the 22 crops in the crop-recommendation model have a direct
match in this yield dataset (see CROP_YIELD_MAP below). For everything
else, get_expected_yield() returns covered=False rather than a guessed
number. Coconut was deliberately excluded even though its name matches,
because this dataset records coconut yield in nuts/hectare while every
other crop here is tonnes/hectare — mixing the two would silently corrupt
the numbers, so it's left out of ML coverage rather than mislabeled.
"""

import os
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import r2_score, mean_absolute_error

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(BASE_DIR, "data", "crop_yield_data.csv")

# crop_model.py label -> dataset's Crop label
CROP_YIELD_MAP = {
    "rice": "Rice", "maize": "Maize", "chickpea": "Gram", "pigeonpeas": "Arhar/Tur",
    "mothbeans": "Moth", "mungbean": "Moong(Green Gram)", "blackgram": "Urad",
    "lentil": "Masoor", "banana": "Banana", "cotton": "Cotton(lint)", "jute": "Jute",
}

FEATURE_COLS = ["Crop", "Season", "State", "Area", "Annual_Rainfall",
                 "Fertilizer", "Pesticide", "Avg_Temperature"]
CAT_COLS = ["Crop", "Season", "State"]


class YieldModel:
    def __init__(self):
        raw = pd.read_csv(DATA_PATH)
        for c in ["Crop", "Season", "State"]:
            raw[c] = raw[c].astype(str).str.strip()

        self.df = raw[raw["Crop"].isin(CROP_YIELD_MAP.values())].copy()
        # Drop the top 1% of yield values per crop — a handful of records
        # in this dataset are clearly data-entry glitches (e.g. an area/
        # production ratio 50x the crop's normal range), and letting them
        # through would distort both the model and the reported MAE.
        self.df["_q99"] = self.df.groupby("Crop")["Yield"].transform(lambda s: s.quantile(0.99))
        self.df = self.df[self.df["Yield"] <= self.df["_q99"]].drop(columns=["_q99"])

        self.model = None
        self.columns = None
        self.test_r2 = None
        self.test_mae = None
        self._train()

    def _train(self):
        X = pd.get_dummies(self.df[FEATURE_COLS], columns=CAT_COLS)
        y = self.df["Yield"]
        self.columns = X.columns

        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        eval_model = RandomForestRegressor(n_estimators=300, max_depth=16, random_state=42, n_jobs=-1)
        eval_model.fit(X_train, y_train)
        preds = eval_model.predict(X_test)
        self.test_r2 = round(r2_score(y_test, preds), 3)
        self.test_mae = round(mean_absolute_error(y_test, preds), 3)

        self.model = RandomForestRegressor(n_estimators=300, max_depth=16, random_state=42, n_jobs=-1)
        self.model.fit(X, y)

        print(
            f"[yield_model] Trained RandomForestRegressor on {len(self.df)} real APY records "
            f"({len(CROP_YIELD_MAP)} crops) | held-out R2={self.test_r2} MAE={self.test_mae} tonnes/ha"
        )

    def get_model_info(self):
        return {
            "algorithm": "RandomForestRegressor (scikit-learn)",
            "training_records": len(self.df),
            "covered_crops": list(CROP_YIELD_MAP.keys()),
            "test_r2": self.test_r2,
            "test_mae_tonnes_per_ha": self.test_mae,
            "dataset": "Real Indian government crop-production data (data/crop_yield_data.csv), "
                       "all states, 1997-2020",
        }

    def is_covered(self, crop):
        return (crop or "").strip().lower() in CROP_YIELD_MAP

    def get_expected_yield(self, crop, state=None, season=None, rainfall=None, temperature=None):
        crop_key = (crop or "").strip().lower()
        if crop_key not in CROP_YIELD_MAP:
            return {"covered": False, "crop": crop}

        dataset_crop = CROP_YIELD_MAP[crop_key]
        subset = self.df[self.df["Crop"] == dataset_crop]

        row = {
            "Crop": dataset_crop,
            "Season": self._match_season(subset, season),
            "State": self._match_state(subset, state),
            "Area": float(subset["Area"].median()),
            "Annual_Rainfall": rainfall if rainfall is not None else float(subset["Annual_Rainfall"].median()),
            "Fertilizer": float(subset["Fertilizer"].median()),
            "Pesticide": float(subset["Pesticide"].median()),
            "Avg_Temperature": temperature if temperature is not None else float(subset["Avg_Temperature"].median()),
        }
        input_df = pd.get_dummies(pd.DataFrame([row]), columns=CAT_COLS)
        input_df = input_df.reindex(columns=self.columns, fill_value=0)

        predicted = float(self.model.predict(input_df)[0])
        observed = subset["Yield"]

        return {
            "covered": True,
            "crop": crop_key,
            "predicted_yield_tonnes_per_ha": round(predicted, 2),
            "observed_range_tonnes_per_ha": [round(float(observed.min()), 2), round(float(observed.max()), 2)],
            "observed_median_tonnes_per_ha": round(float(observed.median()), 2),
            "sample_size": int(len(subset)),
            "test_r2": self.test_r2,
            "test_mae_tonnes_per_ha": self.test_mae,
            "season_used": row["Season"],
            "state_used": row["State"],
            "data_source": "real (Indian govt APY data, ML-predicted)",
        }

    @staticmethod
    def _match_season(subset, season):
        if season:
            candidates = subset["Season"].unique()
            for c in candidates:
                if season.strip().lower() in c.lower():
                    return c
        return subset["Season"].mode().iloc[0]

    @staticmethod
    def _match_state(subset, state):
        if state:
            candidates = subset["State"].unique()
            for c in candidates:
                if state.strip().lower() == c.lower():
                    return c
        return subset["State"].mode().iloc[0]
