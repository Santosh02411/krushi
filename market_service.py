"""
market_service.py
------------------
Market price data, in priority order:

  1. data.gov.in live Agmarknet feed, if MARKET_API_KEY is set and the
     request succeeds (real, live, any crop the feed covers).
  2. The locally trained MarketPriceModel (real historical mandi data,
     ML-predicted) — currently covers potato, tomato and wheat.
  3. For anything else: an explicit "not covered" response. No invented
     numbers, no silent simulation — the frontend shows this honestly.
"""

import requests

from market_model import MarketPriceModel

DATA_GOV_RESOURCE_ID = "9ef84268-d588-465a-a308-a864a43d0070"
DATA_GOV_URL = f"https://api.data.gov.in/resource/{DATA_GOV_RESOURCE_ID}"


class MarketService:
    def __init__(self, api_key=None):
        self.api_key = api_key
        self.model = MarketPriceModel()

    def get_model_info(self):
        return self.model.get_model_info()

    def get_price_estimate(self, crop, state=None):
        if self.api_key:
            live = self._fetch_data_gov_in(crop, state)
            if live:
                return live

        estimate = self.model.get_price_estimate(crop, state=state)
        if estimate.get("covered"):
            return estimate

        return {
            "covered": False,
            "crop": crop,
            "data_source": "none",
            "message": (
                f"No real market dataset is loaded for '{crop}' yet. Real ML-predicted prices are "
                f"currently available for: {', '.join(self.model.covered_crops)}. Add more Agmarknet "
                f"data to data/market_price_data.csv, or set MARKET_API_KEY for live data.gov.in prices, "
                f"to extend coverage."
            ),
        }

    def get_market_prices(self, crop, state=None):
        result = self.model.get_market_prices(crop, state=state)
        if not result.get("covered"):
            result["message"] = (
                f"No real per-market price records for '{crop}'. Real coverage: "
                f"{', '.join(self.model.covered_crops)}."
            )
        return result

    def get_nearby_markets(self, crop, lat, lon, max_results=5):
        result = self.model.get_nearby_markets(crop, lat, lon, max_results=max_results)
        if not result.get("covered"):
            result["message"] = (
                f"No nearby real market data for '{crop}' with a known coordinate. Real coverage: "
                f"{', '.join(self.model.covered_crops)} in Haryana/Punjab/Uttar Pradesh/Uttarakhand."
            )
        return result

    # ------------------------------------------------------------------ #
    # Real live source (used only if MARKET_API_KEY is configured)
    # ------------------------------------------------------------------ #
    def _fetch_data_gov_in(self, crop, state=None):
        try:
            params = {"api-key": self.api_key, "format": "json", "limit": 20,
                      "filters[commodity]": crop.title()}
            if state:
                params["filters[state]"] = state
            resp = requests.get(DATA_GOV_URL, params=params, timeout=10)
            resp.raise_for_status()
            records = resp.json().get("records", [])

            prices = []
            for r in records:
                try:
                    price = float(r.get("modal_price", 0))
                except (TypeError, ValueError):
                    continue
                if price > 0:
                    prices.append(price)
            if not prices:
                return None

            return {
                "covered": True,
                "crop": crop,
                "predicted_modal_price": round(sum(prices) / len(prices), 0),
                "observed_price_range": [min(prices), max(prices)],
                "sample_size": len(prices),
                "data_source": "real (data.gov.in, live)",
            }
        except Exception as e:
            print(f"[market_service] data.gov.in fetch failed, falling back: {e}")
            return None

    def get_market_news(self, crop=None):
        """Illustrative agri-market news items (static, not a live news feed)."""
        news_items = [
            {"title": "Monsoon outlook watched closely by Kharif growers",
             "summary": "Timely, well-distributed rainfall is the single biggest driver of "
                         "Kharif crop yields and prices.",
             "impact": "neutral"},
            {"title": "Storage and cold-chain access affects perishable crop prices",
             "summary": "Crops like tomato and potato see large price swings where cold "
                         "storage is limited.",
             "impact": "neutral"},
        ]
        if crop:
            matched = [n for n in news_items if crop.lower() in (n["title"] + n["summary"]).lower()]
            return matched or news_items
        return news_items
