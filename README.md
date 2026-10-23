# Warpdrobe

Warpdrobe plans your outfits around your calendar and the weather. Photograph your clothes once and
the app tags each piece. It reads your day ("interview at 2pm, 48°F and rainy") and suggests what to
wear. It also tracks cost per wear, flags clothes you never wear, and tells you which single new
item would unlock the most outfits.

**Stack:** React + TypeScript (Vite) · FastAPI · PostgreSQL / SQLite · PySpark · Gemini vision API ·
Open-Meteo · Google Calendar (iCal feed) · Docker · GitHub Actions

## How it works

```
 phone photo ──► FastAPI ──► Gemini (structured JSON) ──► tags: category, color, formality, warmth, seasons
                    │
 Google Calendar ───┤  events ──► dress code (interview → business, gym → active, …)
 Open-Meteo ────────┤  forecast ──► target warmth, coat or no coat, rain warning
                    ▼
              outfit engine ──► top 3 outfits + reasons ──► user rates / logs what they wore
                    ▲
 H&M purchases ─► PySpark ─► pairings.json (which category+color pairs are bought together)
```

### Outfit engine (`backend/app/engine.py`)

The engine builds every valid outfit (top + bottom, or a dress), then adds the best shoes and,
when it's cold, a coat. Each outfit gets four scores:

| Component | Weight | What it measures |
|---|---|---|
| Formality | 0.35 | Distance from the day's dress code (the most formal event wins). Underdressing is penalized more than overdressing |
| Pairing | 0.30 | How well each pair of pieces goes together: log-lift learned from H&M baskets, with color rules for pairs the data never saw |
| Weather | 0.25 | Warmth vs. the forecast's "feels like" temperature, season fit, and a missing-coat penalty |
| Freshness | 0.10 | Avoids pieces worn in the last few days |

Suggestions are diversified, so no top, bottom or dress appears in two of the three picks.

**Gap finder:** for 150 hypothetical items (5 categories × 10 colors × 3 formality levels), count how
many new good outfits each would create with the current closet. Show the best ones.

### Learning pairings with PySpark (`spark/pairings_job.py`)

Input is the [H&M Personalized Fashion Recommendations](https://www.kaggle.com/competitions/h-and-m-personalized-fashion-recommendations/data)
dataset: about 31.8M transactions and about 105k articles.

1. Map each article to a token like `top|white` or `bottom|navy`. Underwear, swimwear,
   cosmetics and kids' items are dropped.
2. Treat each customer's purchases on one day as a basket. Keep baskets that span 2 or more
   categories and contain at most 12 distinct tokens.
3. For every cross-category token pair, compute lift: `P(a,b) / (P(a)·P(b))`. Pairs seen in
   fewer than 50 baskets are dropped.
4. Write `data/pairings.json`, which the API loads at startup.

### Results so far

| | |
|---|---|
| H&M data processed | ~31.8M transactions, 105k articles → 2,991,233 multi-category baskets (training period, before 2020-08-22) |
| Learned pairs | 2,838 category+color pairs with ≥50 supporting baskets |
| Spark runtime | 95 s on a laptop (local mode, Windows) |
| Outfit compatibility, held-out month | **AUC 0.587** with learned pairings vs. 0.493 with color rules (≈9.8k test baskets, mean of 3 seeds) |

The compatibility test uses the last month of H&M baskets, which the model never trained on. The
scoring choices (log-lift, with color rules only as a fallback) were picked on a separate dev half
of those baskets.

### Evaluation

| What | How | Script |
|---|---|---|
| Outfit compatibility | Train on purchases before a cutoff date. Then, for held-out later baskets, check whether the scorer ranks each real basket above a fake one (the same categories with randomly swapped pieces). Report paired AUC for learned pairings vs. color rules on a fixed test half (`--part test`) | `eval/outfit_eval.py` |
| Tagging accuracy (offline) | Gemini predictions vs. hand labels on a photo set: accuracy for category, color and formality (exact and ±1) | `eval/tagging_eval.py` |
| Tagging accuracy (in app) | Every upload keeps the model's original tags. When users confirm or fix them, the admin metrics compare the two | `/api/admin/metrics` |
| User satisfaction | 1–5 star ratings on suggestions. The top pick is tracked separately | `/api/admin/metrics` |

## Running locally

Requirements: Python 3.11+, Node 20+, and Java 17+ (for Spark only).

```bash
cp .env.example .env            # then paste your Gemini API key into .env

# API
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt -r requirements-dev.txt
uvicorn app.main:app --reload   # http://localhost:8000/docs

# Web app (second terminal)
cd frontend
npm ci
npm run dev                     # http://localhost:5173
```

Without a Gemini key, uploads still work. Only the color is detected, and you pick the type
yourself.

### Pairings + evaluation

```bash
cd spark
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# put articles.csv and transactions_train.csv in one folder
python pairings_job.py --data ~/Downloads/hm-data --holdout-from 2020-08-22
cd .. && backend/.venv/bin/python eval/outfit_eval.py
```

`--sample 0.1` runs on 10% of customers for a quick test. `make_sample_data.py` writes a tiny
synthetic dataset for trying the pipeline without the download.

### Tests

```bash
cd backend && python -m pytest -q    # API, engine, calendar, weather, tagger, eval scoring
cd spark && python -m pytest -q tests # Spark job on a synthetic dataset (needs Java)
cd frontend && npm test && npm run build
```

All three suites run in GitHub Actions on every push.

## Deploying

The `Dockerfile` builds the React app and serves it from the API, so there is one service to
deploy. `render.yaml` is a Render Blueprint for it.

1. Create a free Postgres database (for example on [Neon](https://neon.tech)) and copy its
   connection string.
2. On [Render](https://render.com): **New → Blueprint**, then pick this repo. Set
   `DATABASE_URL`, `GEMINI_API_KEY`, and `ADMIN_EMAILS` (your login email).
3. Commit `data/pairings.json` after running the Spark job, so the deployed app uses learned
   pairings.

Photos are stored in the database, resized to 768px with EXIF/GPS data stripped, so no disk or
bucket is needed.

## Privacy

- Photos are private to each account and served only under random, unguessable URLs.
- Calendar access uses the calendar's private iCal link. Only event titles and times are read,
  and the server fetches only Google, Outlook and iCloud calendar hosts.
- Passwords are hashed with scrypt.

## Project layout

```
backend/   FastAPI app (app/), tests, locked requirements
frontend/  React + TypeScript app
spark/     PySpark pairing job, H&M → app category mapping, synthetic sample data
eval/      outfit and tagging evaluation scripts
data/      pairings.json produced by the Spark job
```
