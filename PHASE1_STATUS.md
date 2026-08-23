# Epifani Growth Engine — Phase 1 Status

## What's Built

### Project Location
```
/home/john/dev/python/epifaniGrowthPlan/engine/
```
Conda env: `epifani-growth` (Python 3.11)

### Files
| File | Purpose |
|------|---------|
| `core/prediction_fetcher.py` | Fetches predictions from Epifani API, filters by confidence + value, returns one best pick per match |
| `core/image_builder.py` | Builds branded PNG cards in square (1080×1080) and story (1080×1920) formats |
| `core/script_generator.py` | Generates 3-tweet threads via Gemini 2.0 Flash |
| `publishers/twitter_publisher.py` | Posts threads + image to Twitter/X via Tweepy v4 |
| `main.py` | CLI entry point |
| `.env.example` | Template for all credentials |

---

## Rules Applied to Predictions

| Rule | Value | Reason |
|------|-------|--------|
| Minimum confidence | 60% | Anything below is noise |
| Value bets only | `is_value=True` | Filters out picks with negative edge |
| Max displayed confidence | **88%** | 100% is a model bug — looks fake to users |
| Edge recalculated from cap | `min(prob, 0.88) − (1/odds)` | Keeps confidence + edge consistent |
| `--no-corners` flag | Excludes Corners (Dynamic Line) market | Optional — run with flag to filter these out |

---

## CLI Reference

```bash
conda activate epifani-growth
cd /home/john/dev/python/epifaniGrowthPlan/engine
```

| Command | What it does |
|---------|-------------|
| `python main.py --list-picks` | Print today's qualifying picks to terminal |
| `python main.py --list-picks --no-corners` | Same, excluding corners markets |
| `python main.py --generate-cards` | Build all card images → `assets/output/` |
| `python main.py --generate-cards --no-corners` | Cards without corners picks |
| `python main.py --dry-run --run-all` | Full pipeline preview (no posting) |
| `python main.py --run-all` | Full live run: cards + tweet threads |
| `python main.py --run-all --no-corners` | Full live run, no corners |

> **Note:** If the portal (`localhost:3000`) isn't running, the engine automatically falls back to `web_portalEpifani/public/data/predictions.json`. Start the portal with `npm run dev` for live data.

---

## What You Need to Add Before Going Live

### 1. Create your `.env` file
```bash
cp .env.example .env
```
Then fill in the values below.

---

### 2. Gemini API Key
**Purpose:** Generates tweet copy for each pick.
**Get it:** https://aistudio.google.com/apikey (free)
```
GEMINI_API_KEY=your_key_here
```

---

### 3. Twitter / X API Credentials
**Purpose:** Posts the 3-tweet threads with images.

You need a **Developer Account** with a project app that has **Read + Write** permissions.

**Get them:** https://developer.twitter.com/en/portal/dashboard

You need 4 values:
```
TWITTER_API_KEY=
TWITTER_API_SECRET=
TWITTER_ACCESS_TOKEN=
TWITTER_ACCESS_SECRET=
```

> **Important:** When generating the Access Token, make sure you select **Read and Write** permissions. The default is Read-only, which will make posting fail silently.

---

## How to Test Phase 1 (Step by Step)

### Step 1 — Verify picks are loading
```bash
python main.py --list-picks --no-corners
```
You should see a list of today's matches with confidence and tier. If it says "Portal API unreachable", that's fine — it's using the local JSON fallback.

### Step 2 — Generate cards
```bash
python main.py --generate-cards --no-corners
```
Check `engine/assets/output/` — you should see `.png` files for every pick (one square, one story per match).

### Step 3 — Dry run the full pipeline
```bash
python main.py --dry-run --run-all --no-corners
```
This will:
- Fetch picks
- Build cards
- Call Gemini to write tweet threads
- **Print** the threads to terminal without posting

Review the tweet copy. If it looks wrong, the Gemini prompt can be adjusted in `core/script_generator.py` (`_THREAD_TEMPLATE`).

### Step 4 — Go live
```bash
python main.py --run-all --no-corners
```
Threads will be posted to Twitter with the square card attached to tweet 1.

---

## Phase 2 — Plan & Decisions

### Decisions Locked In

| Decision | Choice | Notes |
|----------|--------|-------|
| MPT runtime | Raw Python process | Already cloned, no Docker needed |
| Daily posts | **Top 3 picks only** | Highest confidence, avoids flooding |
| TTS voice | **Edge-TTS** (free) | Built into MoneyPrinterTurbo |
| Post time | **09:00 GMT+2** daily | Morning before European matches |
| YouTube | Skip for now | No channel yet — add in Phase 3 |
| TikTok/Instagram | Upload-Post API | Sign up at upload-post.com first |
| Dashboard | Streamlit — yes | Build in Phase 2 |
| Language | English only | Maximum global reach |

---

### Credentials — Fill In When Ready (Code Works Without Them)

All API keys live in `engine/.env`. The code is fully built and will run — it just won't post to platforms until the real keys are in place. Add them at any point.

| Credential | Where to get it | `.env` key(s) |
|------------|----------------|---------------|
| Gemini API key | aistudio.google.com/apikey (free) | `GEMINI_API_KEY` |
| Twitter/X API | developer.twitter.com → App with Read+Write | `TWITTER_API_KEY`, `TWITTER_API_SECRET`, `TWITTER_ACCESS_TOKEN`, `TWITTER_ACCESS_SECRET` |
| Upload-Post | upload-post.com → connect TikTok + Instagram | `UPLOAD_POST_API_KEY`, `UPLOAD_POST_USERNAME` |

**Steps when you're ready to go live:**
1. Create social accounts: Twitter/X, TikTok, Instagram for Epifani
2. Sign up at upload-post.com and connect both accounts
3. Get Twitter Developer API keys (Read+Write permissions)
4. Fill in `engine/.env` and run `python main.py --run-all`

> YouTube skipped until Phase 3.

---

### Phase 2 Components to Build

| File | What it does |
|------|-------------|
| `core/video_builder.py` | Starts MPT as subprocess → waits for video → overlays Epifani watermark + intro/outro card via ffmpeg |
| `publishers/upload_post_publisher.py` | Posts video to TikTok + Instagram via Upload-Post API |
| `core/scheduler.py` | APScheduler CRON: 08:00 fetch top 3 → 09:00 build cards + videos → 09:30 post all platforms |
| `web_ui/dashboard.py` | Streamlit: preview today's cards, toggle platforms on/off, manual trigger, posting history |

### Phase 2 Components — ✅ Built

| File | Status |
|------|--------|
| `core/video_builder.py` | ✅ Built — starts MPT subprocess, polls task, ffmpeg branding overlay |
| `publishers/upload_post_publisher.py` | ✅ Built — TikTok + Instagram via Upload-Post API |
| `core/scheduler.py` | ✅ Built — APScheduler, 08:50/09:00/09:10 jobs, Europe/Athens |
| `web_ui/dashboard.py` | ✅ Built — Streamlit dashboard with preview + manual trigger |

### Updated CLI (Phase 2)

| Command | What it does |
|---------|-------------|
| `python main.py --build-videos --top 3 --no-corners` | Build branded videos via MPT |
| `python main.py --post-social --dry-run` | Preview TikTok/Instagram uploads |
| `python main.py --post-social` | Post videos to TikTok + Instagram |
| `python main.py --run-all --top 3 --no-corners` | Full pipeline: cards + videos + all platforms |
| `python scheduler.py` | Start the daily automation (runs forever) |
| `streamlit run web_ui/dashboard.py` | Launch the Streamlit dashboard |

### `--top N` flag
Added globally. Scheduler defaults to 3. CLI lets you override (e.g. `--top 5`).
