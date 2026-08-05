# Krushi — data-driven crop, soil, weather & market advisor

Krushi helps a farmer decide what to plant, how healthy their soil is, and
what it might fetch at market — using real trained ML models, real
government datasets, and live weather/location data. Every module states
plainly what is real and what is an explicitly-labeled fallback.

## Structure: separate pages, sign-in required

Every feature is its own page (`/recommend`, `/soil`, `/yield`, `/market`,
`/fertilizer`, `/profit`, `/disease`, `/water`, `/calendar`, `/dashboard`,
`/map`, `/knowledge`, `/chat`, `/about`, `/profile`) rather than one long
scrolling page — there's a persistent nav across all of them
(`templates/base.html`). **Every page and every feature API endpoint
requires a signed-in session** — `/login` is the only public page, and
`auth.page_login_required` / `auth.login_required` redirect or 401
anything else if you're not signed in.

## The 19 feature systems in this build

1. **User authentication** — registration/login, farmer profile, forgot
   password, role-based access (farmer/admin)
2. **Crop recommendation** — state/district/soil type/season inputs, top
   recommendation + 5 alternatives, expected yield, suitable season,
   profitability rating
3. **Weather integration** — live temperature/humidity/rainfall/wind/UV,
   today's weather, 7-day forecast, rain alerts, heatwave warnings
4. **Soil health analysis** — N/P/K/pH/organic carbon → health score,
   nutrient deficiency, fertilizer recommendation, improvement suggestions
5. **Market price prediction** — real current mandi prices by market,
   ML price prediction, nearest real market to your location
6. **Fertilizer recommendation** — after picking a crop, which fertilizer,
   how much, roughly what it costs, and when to apply it
7. **Disease check** — symptom-based reference matching for common crop
   diseases (see note below on why this isn't image AI)
8. **Photo/camera capture for disease records** — real upload/camera
   capture, kept for your reference, not analyzed by any model
9. **Irrigation recommendation + crop calendar** — 7-day irrigation
   schedule with a "Water Required / Next Irrigation" headline, plus a
   full sowing→fertilizer→irrigation→harvest calendar
10. **Standalone yield prediction** — area/crop/state/season → expected
    total yield in tonnes + the model's real held-out fit
11. **Profit estimation** — your entered expenses (seeds/fertilizer/
    labour/water/pesticides) vs. income from real yield × real price →
    net profit
12. **Farm dashboard** — charts built entirely from your own logged data:
    expenses by category, income vs. expenses, soil health history, water
    usage history
13. **Interactive farm map** — free Leaflet + OpenStreetMap (no API key),
    shows your real GPS location and real nearby markets
14. **Farming knowledge base** — articles, best practices, organic
    farming, pest management, real government scheme links, and an
    eligibility checker (indicative, not authoritative)
15. **Smart notifications** — rain tomorrow, fertilizer due today, harvest
    approaching, and a general fungal-disease-risk weather flag, all
    derived from your saved crop calendars and real weather
16. **AI chatbot** — real Anthropic API integration (needs your own API
    key; says so honestly if unconfigured, doesn't fake a reply)
17. **Farm records** — a unified page for crops grown, yield history,
    fertilizer usage (log it manually), expenses, and income
18. **Analytics** — monthly/yearly charts for yield, profit, water usage,
    and crop comparison, aggregated from your own real logs
19. **Admin panel** — manage farmers, view real crop/weather/market model
    status, post news announcements, extend the disease database, and a
    dashboard with active users / recommendations generated / disease
    scans (revenue is honestly reported as N/A — no billing system exists)

Everything auto-fills from your real GPS location where possible.

## What's real vs. labeled fallback

| Module | Data source | Status |
|---|---|---|
| Crop recommendation | [Crop Recommendation Dataset](https://raw.githubusercontent.com/Gladiator07/Harvestify/master/Data-processed/crop_recommendation.csv) — 2,200 real samples, 22 crops. | **Real.** `RandomForestClassifier`, held-out test accuracy shown live. |
| Expected yield | Real Indian government crop-production data, 1997-2020, all states (`data/crop_yield_data.csv`, 19,689 records). | **Real, covers 11 of 22 crops** (rice, maize, chickpea, pigeonpeas, mothbeans, mungbean, blackgram, lentil, banana, cotton, jute). `RandomForestRegressor`, held-out R²=0.93. Other crops return an explicit "not covered" message. |
| Location | Browser GPS → reverse geocoding. | **Real, accurate.** IP-based lookup is kept only as a fallback, with an explicit accuracy warning. |
| Weather (current, 7-day forecast, UV index) | [Open-Meteo](https://open-meteo.com), by exact GPS coordinates when available. | **Real, live**, no API key required. |
| Rain alerts / heatwave warnings | Rule-based thresholds applied to the real forecast above. | **Real, transparent logic.** |
| Soil health score / fertilizer guidance | India's Soil Health Card classification bands (published standard, not ML). | **Real reference ranges**, general guidance — not a substitute for a lab test. |
| Market prices (per real market) | Real Agmarknet mandi records (`data/market_prices_by_location.csv`), decoded to real market/state names. | **Real, covers potato/tomato/wheat** across 18 real markets in Haryana/Punjab/UP/Uttarakhand. |
| Market price prediction | Same dataset, `RandomForestRegressor`. | **Real, same 3-crop coverage.** Held-out R²=0.40 (modest — shown honestly). Live data.gov.in feed used instead if `MARKET_API_KEY` is set. |
| Nearest market | Real market coordinates (hardcoded for the 16 confidently-identified towns in the dataset) + haversine distance from your GPS. | **Real**, for the 3 covered crops. |
| Profitability rating | Expected yield × predicted price, ranked relative to other recommended crops. | **Real where both a yield estimate and a price estimate exist for a crop** — in practice this means the crop-recommendation set (22 crops) and the market-price set (3 crops) rarely overlap, so profitability shows "insufficient data" for most crops today. See below. |
| Fertilizer plan (quantity/cost/schedule) | Published package-of-practices N-P-K doses for major crops, converted to physical fertilizer quantities and representative bag prices. | **Real reference data, covers 12 crops.** Costs are approximate, not live pricing. |
| Irrigation schedule + "Water Required / Next Irrigation" headline | Same rule-based water-balance calculation as before, now with a one-line summary derived from the same schedule. | **Real, transparent logic.** |
| Crop calendar (sowing/fertilizer/irrigation/harvest dates) | Published crop-duration and growth-stage timing references, plus the fertilizer/irrigation data above. | **Real arithmetic on real reference data, covers 13 annual crops.** Perennial crops get a simpler seasonal-care note instead of a fabricated single harvest date. |
| Disease check | A symptom-matching reference table for common diseases (5 crops), sourced from standard plant-pathology/extension knowledge. | **Real reference data — explicitly NOT image AI.** See below for why. |
| Disease photo / camera capture | Real file upload / browser camera capture. | **Real upload, stored for your own reference — not analyzed.** |
| Standalone yield prediction | Same yield_model.py as the crop advisor, converted to total tonnes for your entered area. | **Real, same 11-crop coverage.** "Accuracy" is the model's R² expressed as a percentage — labeled as such, not classification accuracy. |
| Profit estimation | Real yield × real price (or your entered price) minus your entered expenses. | **Real arithmetic on real/user inputs.** Since the yield-covered crops (11) and price-covered crops (3) don't overlap, most crops need you to enter an expected price — the app says so rather than guessing one. |
| Farm dashboard | Your own expense/income entries, plus auto-logged soil health scores, water usage, and yield predictions whenever you're signed in. | **Real, entirely your own data.** A new account's dashboard is empty — there's no demo/seed data. |
| Interactive farm map | Leaflet.js + OpenStreetMap tiles (free, no API key) + real market coordinates. | **Real.** "Nearby weather stations" is deliberately not shown — Open-Meteo is a model-based forecast service with no public physical station location data to show. |
| Knowledge base articles / best practices / organic farming / pest management | General agronomy reference content. | **Real, general knowledge**, not sourced from a live database. |
| Knowledge base government schemes | Real, well-known central government scheme names + official URLs. | **Real names/URLs.** Amounts and eligibility criteria aren't stated, since those change and I can't verify current figures without a live search tool in this build. |
| Knowledge base videos | — | **Deliberately omitted.** I have no web-search/fetch tool in this build to find and verify real video links, and guessing them risks shipping dead or wrong URLs. Each article has a suggested search term instead. |
| Eligibility checker | A coarse rule engine over a few stable, broadly-known factors (land ownership, notified crop, tax/employment status) per scheme. | **Indicative, not authoritative** — exact eligibility rules change and I can't verify today's criteria without a live search tool. Always says to confirm on the official portal. |
| Smart notifications | Real saved crop-calendar events (fertilizer/harvest dates) + real weather forecast + your last real disease-check result. | **Real, derived from data already computed elsewhere in the app** — no separate prediction system. The "disease risk" notification is a general weather-based flag (humidity/temperature thresholds that favor fungal disease), explicitly not a diagnosis. |
| AI chatbot | Real Anthropic API call (`chat_service.py`), with a system prompt describing what Krushi's own tools actually cover. | **Real, once you add `ANTHROPIC_API_KEY`.** Without a key, the chat page says so plainly — it does not fall back to a scripted fake response. |
| Farm records (crops grown, yield, expenses, income, fertilizer usage) | Each pulled from its own real table — crops grown and yield populate automatically from the Crop Calendar and Yield Prediction tools; fertilizer usage is logged manually. | **Real, entirely your own data.** |
| Analytics (monthly/yearly yield, profit, crop comparison, water usage) | Real aggregation (sums/groupings) of the same logs behind Farm Records and the Farm Dashboard. | **Real arithmetic on real data** — no forecasting, no trend-fitting. |
| Admin: farmers / crops / weather / market panels | Real queries — user list, live model info, a live weather API call, live market model stats. | **Real, live.** |
| Admin: news | A real announcements table — admin posts, everyone sees on the home page. | **Real, but editorial content**, not an external news feed (no search tool available to pull real agri news). |
| Admin: disease database | The static reference table (read-only) plus a real form to add new crop/symptom/treatment entries, which immediately show up in the Disease Check tool. | **Real CRUD**, not a bigger pre-loaded database. |
| Admin dashboard: active users / recommendations / disease scans | Real SQL queries against the app's own tables ("active" = has a real log entry in the last 30 days). | **Real.** |
| Admin dashboard: revenue | — | **Explicitly N/A.** Krushi has no billing/subscription system in this build, so there is no real number to report — the dashboard says so instead of inventing one. |

### Why disease detection isn't an image classifier

I looked for a real, freely-usable pretrained plant-disease image model
before deciding this. I found one — a fastai-exported ResNet34 trained on
the PlantVillage dataset, from `github.com/imskr/Plant_Disease_Detection`
— and deliberately didn't use it: loading that `.pkl` export requires
fastai 1.x, which is unmaintained and doesn't install cleanly on modern
Python. Shipping it would mean either the app breaks on `pip install`, or
the feature silently doesn't work — both worse than not having it.
Training a new model from scratch would need downloading and training on
tens of thousands of PlantVillage images, which isn't realistic to do
honestly in this environment either. So `disease_reference.py` matches
described symptoms against a real reference table instead, and the photo
upload is real but is kept only as your own record, not analyzed. If you
get access to a real plant-disease image API later, it can slot in
alongside this without removing it.

### Why profitability often shows "insufficient data"

The crop-recommendation model, the yield model, and the market-price model
are each trained on a *different* real dataset, and those datasets don't
cover the same crops. Profitability needs both a real yield number and a
real price number for the *same* crop, so it only appears when a
recommended crop happens to be in both the yield dataset (11 crops) and
the market dataset (3 crops: potato, tomato, wheat) — which is rare, since
the crop-recommendation dataset's 22 crops don't actually include potato,
tomato or wheat at all. Rather than paper over that with an invented
number, the app says so. Expanding `data/market_price_data.csv` with more
crops (e.g. rice, maize) would directly fix this.

## Setup

1. Create a virtual environment and install dependencies:
   ```bash
   python -m venv venv
   source venv/bin/activate   # venv\Scripts\activate on Windows
   pip install -r requirements.txt
   ```

2. Copy the environment template (all values are optional — the app runs
   with zero keys):
   ```bash
   cp .env.example .env
   ```

3. Run the app:
   ```bash
   python app.py
   ```

4. Open `http://localhost:5000`. Click **Use my GPS location** and allow
   the browser's location permission — that drives the weather, crop
   climate values, and nearest-market lookup.

5. (Optional) Create an admin account. Admin access is **not** available
   through the public registration form — it can only be granted by
   someone with direct access to the server:
   ```bash
   python scripts/create_admin.py you@example.com "Your Name" yourpassword
   ```

The first startup takes several seconds while all three ML models train on
their bundled real datasets:
```
[ml_models] Trained RandomForest on 2200 real samples across 22 crops |
held-out test accuracy=99.3% macro-F1=99.3%
[yield_model] Trained RandomForestRegressor on 5917 real APY records
(11 crops) | held-out R2=0.934 MAE=0.456 tonnes/ha
[market_model] Trained RandomForestRegressor on 6361 real mandi records
(Potato/Tomato/Wheat, 4 states) | held-out R2=0.402 MAE=Rs.474.6/quintal
```

## Project layout

```
krushi/
├── app.py                  # Flask routes for all 5 feature systems
├── auth.py                  # Registration/login/sessions/roles/password reset
├── ml_models.py              # Crop RandomForest + irrigation rule engine
├── yield_model.py            # Expected-yield RandomForestRegressor
├── market_model.py           # Market price model + real per-market lookup + nearest market
├── market_service.py         # Wraps market_model.py, optional live data.gov.in override
├── soil_health.py             # Rule-based soil scoring / fertilizer guidance
├── fertilizer_recommendation.py  # Crop-specific fertilizer quantity/cost/schedule
├── crop_calendar.py           # Sowing/fertilizer/irrigation/harvest date calculator
├── disease_reference.py       # Symptom-matching disease reference (not image AI)
├── weather_service.py        # Open-Meteo / OpenWeatherMap + rain/heatwave alerts
├── location_service.py       # Reverse geocoding (GPS) + IP fallback
├── farm_records.py            # Expense/income/soil/water/yield logs, crop plans, fertilizer usage, analytics
├── admin_tools.py             # Admin panel backend: news, disease DB entries, real usage stats
├── notifications.py           # Rain/fertilizer/harvest/disease-risk alerts, from real saved data
├── chat_service.py            # Real Anthropic API chatbot integration
├── knowledge_base.py          # Articles, schemes, eligibility checker
├── scripts/create_admin.py   # CLI-only admin account creation
├── data/
│   ├── Crop_recommendation.csv       # real 2,200-row crop training dataset
│   ├── crop_yield_data.csv           # real 19,689-row national yield dataset
│   ├── market_price_data.csv         # real mandi price records (ML training)
│   ├── market_prices_by_location.csv # same data, decoded to real market names
│   ├── crop_info.json                # season / water need / market demand per crop
│   └── states_districts.json         # Indian states + districts for form dropdowns
├── templates/
│   ├── base.html              # shared nav/footer, extended by every page below
│   ├── login.html             # the only public page
│   ├── home.html, recommend.html, soil.html, yield.html, market.html,
│   │   fertilizer.html, profit.html, disease.html, water.html, calendar.html,
│   │   dashboard.html, records.html, analytics.html, map.html, knowledge.html,
│   │   chat.html, about.html, profile.html, admin.html
│   │   # one page per feature, all login-gated (admin.html: admin role only)
├── static/css/style.css
├── static/js/common.js        # runs on every page: nav logout, notif badge
├── static/js/script.js        # all feature logic, one initXPage() per page
├── requirements.txt
└── .env.example
```

## API endpoints

**Auth**
| Endpoint | Method | Purpose |
|---|---|---|
| `/api/auth/register` | POST | Create account (always role=farmer) |
| `/api/auth/login` | POST | Session login |
| `/api/auth/logout` | POST | Clear session |
| `/api/auth/me` | GET | Current session user |
| `/api/auth/profile` | PUT | Update farm profile (login required) |
| `/api/auth/forgot-password` | POST | Issues a reset token (returned directly — see note below) |
| `/api/auth/reset-password` | POST | Consume the token, set a new password |
| `/api/admin/users` | GET | List farmers + usage stats (admin only) |

**Core**
| Endpoint | Method | Purpose |
|---|---|---|
| `/api/model-info` | GET | Real training/evaluation stats for all 3 ML models |
| `/api/reference-data` | GET | States/districts/soil types/seasons/languages for form dropdowns |
| `/api/reverse-geocode?lat=&lon=` | GET | Real GPS coordinates → place name (preferred) |
| `/api/detect-location` | GET | IP-based fallback location (labeled as an estimate) |
| `/api/weather-by-coords?lat=&lon=` | GET | Live weather + 7-day forecast + alerts, by GPS |
| `/api/weather/<location>` | GET | Same, by place name |
| `/api/recommend-crops` | POST | Crop recommendations + yield + profitability |
| `/api/soil-health` | POST | Soil score, deficiencies, fertilizer guidance |
| `/api/water-management` | POST | 7-day irrigation schedule |
| `/api/market-trends/<crop>` | GET | ML-predicted price |
| `/api/market-prices/<crop>` | GET | Real per-market current prices |
| `/api/market-nearby/<crop>?lat=&lon=` | GET | Nearest real markets to your GPS location |
| `/api/fertilizer-plan` | POST | Crop-specific fertilizer quantity/cost/schedule |
| `/api/crop-calendar` | POST | Sowing/fertilizer/irrigation/harvest dates |
| `/api/disease-symptoms/<crop>` | GET | Symptom list to choose from for a crop |
| `/api/disease-check` | POST | Match selected symptoms to known diseases |
| `/api/disease-photo` | POST | Upload a photo (stored for reference, not analyzed) |
| `/api/yield-prediction` | POST | Standalone expected-yield tool |
| `/api/profit-estimation` | POST | Income − expenses = net profit |
| `/api/farm/expense` | POST | Log an expense (login required) |
| `/api/farm/income` | POST | Log income (login required) |
| `/api/farm/dashboard` | GET | Your dashboard data (login required) |
| `/api/knowledge-base` | GET | Articles/best practices/schemes/etc. |
| `/api/schemes/eligibility` | POST | Indicative scheme eligibility check |
| `/api/notifications` | GET | Rain/fertilizer/harvest/disease-risk alerts |
| `/api/chat` | POST | Chatbot reply (needs `ANTHROPIC_API_KEY`) |
| `/api/farm/records` | GET | Crops grown / yield / expenses / income / fertilizer usage |
| `/api/farm/fertilizer-usage` | POST | Log a fertilizer application |
| `/api/farm/analytics?period=` | GET | Monthly/yearly aggregated analytics |
| `/api/news` | GET | Public announcements (read-only) |
| `/api/admin/stats` | GET | Real usage stats (admin only) |
| `/api/admin/crops` | GET | Live model coverage (admin only) |
| `/api/admin/weather-status` | GET | Live weather API check (admin only) |
| `/api/admin/news` | GET/POST | List/post announcements (admin only) |
| `/api/admin/disease-database` | GET/POST | View/add disease reference entries (admin only) |

All of the above (except the `/api/auth/*` endpoints) require a signed-in
session — every page route does too, redirecting to `/login` if you're not
signed in.

`POST /api/recommend-crops` body:
```json
{
  "location": "Belagavi, Karnataka", "state": "Karnataka", "district": "Belagavi",
  "season": "Kharif", "lat": 15.85, "lon": 74.5,
  "n": 90, "p": 42, "k": 43, "ph": 6.5,
  "temperature": 26, "humidity": 80, "rainfall": 220
}
```
`lat`/`lon`/`temperature`/`humidity`/`rainfall` are optional — if omitted,
live weather for the location is fetched and used.

## On the forgot-password flow

This dev setup has no email service configured. Rather than pretending to
"send an email" (which would silently do nothing), `/api/auth/forgot-password`
returns the real reset token directly in its response, clearly labeled as
a dev-mode stand-in. To make this production-ready, wire a real provider
(SMTP, SendGrid, etc.) into `auth.create_password_reset()` in `auth.py` and
stop returning the token in the response.

## On admin accounts

Public registration always creates a `farmer` role — there is no way to
self-promote to admin through the API (an earlier draft of this had that
bug; it's fixed). Admin accounts are created only via
`scripts/create_admin.py`, which requires direct access to the server.

## Notes on the models

- **Crop model**: `RandomForestClassifier`, ~99% held-out accuracy — a
  clean, well-separated dataset, so treat this as "fits this dataset very
  well," not a guarantee for every real field.
- **Yield model**: `RandomForestRegressor`, R²=0.93, MAE=0.46 tonnes/ha on
  the 11 covered crops. The dataset's coconut yield is recorded in
  nuts/hectare (not tonnes/hectare like everything else), so it's
  deliberately excluded from ML coverage rather than silently mixed in.
- **Market model**: `RandomForestRegressor`, R²=0.40 — modest, and shown
  as such, because it predicts price from crop/location/arrivals only
  (not from that day's min/max, since a farmer asking "what will this
  fetch" doesn't already know today's range).
- **Soil health**: intentionally rule-based, not ML — nutrient sufficiency
  bands are a published standard, and dressing up a lookup table as "AI"
  would be dishonest.

## Tech stack

- **Backend**: Flask, session-based auth (`werkzeug.security` password
  hashing, no plaintext storage)
- **ML**: scikit-learn (3 RandomForest models)
- **Frontend**: HTML / CSS / vanilla JavaScript, browser Geolocation API,
  Chart.js (dashboard charts), Leaflet.js + OpenStreetMap (farm map, both
  free/keyless)
- **Database**: SQLite (`users`, `password_resets`, `recommendations`,
  `expenses`, `income`, `soil_health_logs`, `water_usage_logs`, `yield_logs`)
- **External APIs**: Open-Meteo (weather), a free reverse-geocoding API
  (location), ip-api.com (fallback location), data.gov.in (optional live
  market data)

## Not in this build yet

This was the last batch of the original 22-feature list. What's still not
genuinely real, by design: AI disease detection from photos (needs a
trained CV model that actually installs — see above), translated UI
strings for the 6 supported languages (the language *preference* is
stored on the profile; the UI itself is still English-only), farm records
editing/deletion (records can be added but not yet edited/removed from
the UI), and real external agri news (the "News" feature is an internal
admin-posted announcements board, not a live news feed, since there's no
search tool in this build to source and verify real articles).
