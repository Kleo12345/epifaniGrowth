# 🚀 Epifani Growth Engine — Implementation Plan

> **Goal:** Build a fully automated content marketing machine that pulls live AI predictions from the Epifani portal, generates branded short-form videos and posts, and schedules them across TikTok, Instagram Reels, and YouTube Shorts — funneling viewers to epifani.com.

---

## 📋 User Acquisition Strategy — The Big Picture

Before code, here's **why this works** and what the full list of growth levers looks like:

| # | Strategy | Effort | Expected Impact |
|---|----------|--------|----------------|
| 1 | **AI Short-Form Video Content** (TikTok/Reels/Shorts) | Medium | ⭐⭐⭐⭐⭐ Highest ROI — viral potential |
| 2 | **Twitter/X Bot** — Daily pick threads with Epifani branding | Low | ⭐⭐⭐⭐ Strong community reach |
| 3 | **Affiliate / Referral System** — Users invite others for perks | Medium | ⭐⭐⭐⭐ Compounding growth |
| 4 | **Reddit Engagement** — Post in r/soccerbetting, r/sportsbetting | Low | ⭐⭐⭐ Great for credibility |
| 5 | **Telegram Channel** — Auto-publish daily picks (already exists!) | Low | ⭐⭐⭐⭐ Direct audience |
| 6 | **SEO Blog Posts** — "Best AI football predictions today" pages | Medium | ⭐⭐⭐ Long-term compounding |
| 7 | **Cold Email Outreach** — DM betting communities & tipster groups | Low | ⭐⭐ Targeted but manual |
| 8 | **Influencer Collaboration** — Partner with tipsters to promote | High | ⭐⭐⭐⭐ Massive reach if right fit |

> **Focus for this engine:** Items 1 & 2 — the automation that creates the most leverage per hour of your time.

---

## 🔍 What We're Taking from the Reference Projects

### MoneyPrinterTurbo (57k ⭐)
- **AI script generation** from a topic/keyword via LLM (GPT/Gemini)
- **Auto video assembly**: stock footage (Pexels) + voiceover (TTS) + subtitles + background music
- **Multiple aspect ratios**: 9:16 (vertical Reels/TikTok), 16:9 (YouTube)
- **Web UI + REST API** for automation

### MoneyPrinterV2 (30k ⭐)
- **YouTube Shorts Automator** with CRON scheduling
- **Twitter Bot** with automated posting
- **Modular Python architecture** — easy to extend

### What We Build On Top
Instead of generic "money" content, we plug in **Epifani's live prediction data** as the source of truth, making every video unique, data-driven, and directly branded to your portal.

---

## 🏗️ Architecture Overview

```
epifani_growth_engine/
├── core/
│   ├── prediction_fetcher.py     # Pulls picks from Epifani API
│   ├── script_generator.py       # LLM generates hook + script for each pick
│   ├── video_builder.py          # Assembles video (footage + TTS + subtitles)
│   ├── image_builder.py          # Generates static prediction cards (fallback)
│   └── scheduler.py              # CRON-based daily automation
│
├── publishers/
│   ├── tiktok_publisher.py       # Uploads to TikTok via unofficial API
│   ├── instagram_publisher.py    # Posts Reels via Instagram Graph API
│   ├── youtube_publisher.py      # Uploads Shorts via YouTube Data API v3
│   └── twitter_publisher.py      # Posts threads via Twitter/X API v2
│
├── config/
│   ├── config.json               # API keys, platform credentials, settings
│   └── templates/                # Script templates & caption templates
│
├── assets/
│   ├── branding/                 # Epifani logo, fonts, watermarks
│   ├── music/                    # Background tracks
│   └── generated/                # Output videos (auto-cleared)
│
├── web_ui/
│   └── dashboard.py              # Streamlit UI to preview & manage
│
├── main.py                       # Entry point — CLI + scheduler
├── requirements.txt
└── README.md
```

---

## 📅 Phased Build Plan

### Phase 1 — Foundation & Content Generator (Week 1)
**Goal:** Generate polished prediction images and scripts automatically.

- [ ] **1.1** Set up project structure and `config.json` with all keys
- [ ] **1.2** `prediction_fetcher.py` — call Epifani's `/api/predictions` endpoint, filter by confidence tier (Excellent/Good), return structured pick objects
- [ ] **1.3** `script_generator.py` — LLM prompt pipeline:
  - Input: `{ match, pick, confidence, odds, edge }`
  - Output: `{ hook (3s), body (30s script), caption, hashtags }`
  - Tone: hype but data-driven ("The AI has spoken 🤖⚽")
- [ ] **1.4** `image_builder.py` — Generate branded static prediction cards using Pillow:
  - Dark gradient background + Epifani logo
  - Match name, pick, confidence badge, odds
  - "Register at epifani.com" CTA
- [ ] **1.5** CLI test: `python main.py --generate-image`

---

### Phase 2 — Video Assembly Pipeline (Week 2)
**Goal:** Produce full 30–60s short-form videos from predictions.

- [ ] **2.1** Integrate **MoneyPrinterTurbo API** (run locally on port 8080):
  - POST `/api/v1/videos` with generated script + Epifani topic
  - Poll for completion, download output `.mp4`
- [ ] **2.2** `video_builder.py` — Custom video layer on top:
  - Overlay Epifani watermark / logo on MoneyPrinterTurbo output
  - Inject pick data as subtitle burn-in (ffmpeg)
  - Add intro card (0–3s): "Today's AI Pick from Epifani"
  - Add outro card (last 5s): "Register free → epifani.com"
- [ ] **2.3** Aspect ratio handling: 9:16 for TikTok/Reels, 16:9 for YouTube
- [ ] **2.4** CLI test: `python main.py --generate-video --pick <id>`

---

### Phase 3 — Multi-Platform Publishing (Week 3)
**Goal:** Auto-post content to all platforms with one command.

- [ ] **3.1** `youtube_publisher.py` — YouTube Data API v3:
  - Upload Short, set title/description/tags
  - Auto-schedule for peak time (6pm local)
- [ ] **3.2** `twitter_publisher.py` — Twitter API v2:
  - Post thread: Hook tweet → Stats tweet → CTA tweet with image
  - Auto-reply with pick result next day (W/L)
- [ ] **3.3** `instagram_publisher.py` — Meta Graph API:
  - Publish Reel with auto-caption + hashtags
  - Schedule via Content Publishing API
- [ ] **3.4** `tiktok_publisher.py` — TikTok Content Posting API:
  - Upload video with caption + sound
- [ ] **3.5** CLI test: `python main.py --publish-all --date today`

---

### Phase 4 — Scheduler, Dashboard & Analytics (Week 4)
**Goal:** Fully autonomous daily operation with performance tracking.

- [ ] **4.1** `scheduler.py` — APScheduler CRON jobs:
  - `08:00` — Fetch today's top predictions
  - `09:00` — Generate scripts + videos
  - `11:00` — Publish to all platforms
  - `23:00` — Log results (W/L from API) + reply to posts
- [ ] **4.2** Streamlit `dashboard.py`:
  - Preview today's generated content before posting
  - Toggle platforms on/off
  - View posting history + engagement metrics
  - Manual trigger buttons
- [ ] **4.3** Analytics tracker:
  - Store post IDs + metrics (views, clicks, follows) to SQLite
  - Weekly report: best-performing content type
- [ ] **4.4** Referral link injection: every post uses `?ref=tiktok` / `?ref=twitter` UTM params so you track which platform drives signups

---

## 🛠️ Tech Stack

| Layer | Tool |
|-------|------|
| Language | Python 3.11+ (Conda environment) |
| Video Generation | MoneyPrinterTurbo (local API: `localhost:8080`) |
| Video Processing | ffmpeg + moviepy |
| Image Generation | Pillow (PIL) |
| LLM | OpenAI GPT-4o or Google Gemini |
| TTS | ElevenLabs or Edge-TTS (free) |
| Scheduling | APScheduler |
| Dashboard | Streamlit |
| Storage | SQLite (via sqlite3) |
| YouTube | google-api-python-client |
| Twitter | tweepy |
| Instagram | facebook-sdk / Meta Graph API |
| TikTok | TikTok Content Posting API |
| Config | python-dotenv + config.json |

---

## 🛠️ Data & Design Specifications

### 1. Epifani API (Local Connection)
The engine will fetch data from the portal's prediction endpoint:
- **URL**: `http://localhost:3000/api/predictions`
- **Schema**:
  - `Match`: { `id`, `league`, `match`, `home_team`, `away_team`, `timestamp`, `time_str`, `predictions[]` }
  - `Prediction`: { `market`, `outcome`, `odds`, `probability`, `edge`, `is_value` }
- **Confidence Tiers**:
  - **ELITE SIGNAL**: Probability ≥ 90% (Color: `#00ff88`)
  - **HIGH CONFIDENCE**: Probability ≥ 75% (Color: `#00f2ff`)
  - **STRONG SIGNAL**: Probability ≥ 60% (Color: `#7000ff`)

### 2. Branding (Premium Dark Mode)
- **Primary Background**: `#0a0e17` (Deep Navy)
- **Secondary Background**: `#141b2d`
- **Accent Primary**: `#00f2ff` (Electric Cyan)
- **Accent Secondary**: `#7000ff` (Purple)
- **Accent Success**: `#00ff88` (Green)
- **Fonts**: `Outfit` (Headings), `Inter` (Body)
- **Logo Style**: "EPIFANI AI" in bold uppercase.


---

## 🔑 API Keys Needed

| Service | Purpose | Cost |
|---------|---------|------|
| Epifani Internal API | `localhost:3000/api/predictions` | Free |
| OpenAI / Gemini | Script generation | ~$0.01/video |
| Pexels | Stock footage for videos | Free |
| ElevenLabs | Voiceover (premium) | Free tier |
| YouTube Data API | Upload Shorts | Free |
| Twitter API v2 | Post tweets | Free (Basic) |
| Meta Graph API | Instagram Reels | Free |
| TikTok Content Posting API | Upload videos | Free |

---

## 📅 Environment Setup
- **Directory**: `/home/john/dev/python/epifaniGrowthPlan`
- **Conda Env**: `epifani-growth` (To be created)
- **Python**: 3.11
- **Portal Path**: `/home/john/dev/web_portalEpifani`


---

## 🎯 Content Strategy Per Platform

### TikTok / Instagram Reels (Primary Driver)
- **Format**: 30–45s vertical video
- **Hook**: "The AI is 87% confident on this match 🤖"
- **Body**: Show the prediction card + explain the edge
- **CTA**: "Full analysis at epifani.com (link in bio)"
- **Posting frequency**: 1–2x per day

### Twitter/X (Community Building)
- **Format**: Thread of 3 tweets
  1. "⚽ Today's #1 AI Pick: [Match] — [Prediction] @ [Odds]"
  2. "📊 Confidence: 87% | Edge: +14% | 360 models analyzed this match"
  3. "🔗 Get all today's picks FREE → epifani.com/?ref=twitter"
- **Posting frequency**: 1x per day (morning)

### YouTube Shorts (Long-term SEO)
- **Format**: 45–60s video with richer data analysis
- **Title**: "AI Predicted [Match] Correctly AGAIN 🤖 | Epifani"
- **Posting frequency**: 3–4x per week

---

## 📂 Folder Location & Security

```
/home/john/dev/epifani_growth_engine/
```

> [!IMPORTANT]
> This is a **completely separate project** located outside your `web_portalEpifani` directory. It will NOT be pushed to your main GitHub repository. It acts as a private "Growth HQ" for your marketing automation.

---

## 💻 Hardware & Performance

You have confirmed **16GB RAM (and 2x 8GB machines)**. This is **plenty** for generating 2 videos per day.

- **Ffmpeg Processing**: Will take roughly 2-5 minutes per video on your hardware.
- **Memory Usage**: Streamlit + MPT + Python will use ~2-4GB RAM during peak generation.
- **Scaling**: If you eventually want 20 videos a day, your hardware can still handle it via background scheduling.

---

## 📅 Phased Build Plan (Revised Step-by-Step)

### Phase 1 — "The Engine Core" (Immediate)
**Goal:** Connect to Epifani API and generate the first branded content.

- [ ] **1.1** Project scaffolding in `/home/john/dev/epifani_growth_engine/`
- [ ] **1.2** `prediction_fetcher.py`: Connect to `epifani.com/api/predictions`
- [ ] **1.3** `image_builder.py`: Create high-end "Prediction Cards" (Static images for Twitter/X)
- [ ] **1.4** `twitter_publisher.py`: Connect to Twitter API v2 (No approval delay)

### Phase 2 — "The Viral Video Lab" (Next)
**Goal:** Build the MoneyPrinterTurbo integration for Shorts/TikTok/Reels.

- [ ] **2.1** Setup MoneyPrinterTurbo local API
- [ ] **2.2** `video_builder.py`: Automate the flow (Script -> Pexels -> TTS -> Ffmpeg)
- [ ] **2.3** `youtube_publisher.py`: Connect to Google Cloud / YouTube API

### Phase 3 — "Social Expansion" (API Approval Dependent)
**Goal:** Go live on TikTok and Instagram once API access is granted.

- [ ] **3.1** Apply for TikTok Content Posting API (1-3 days)
- [ ] **3.2** Apply for Meta Graph API for Instagram Reels
- [ ] **3.3** Implement publishers once tokens are received.

> [!IMPORTANT]
> The Twitter publisher + image card route is the **fastest path to real users** and requires no video rendering. Start there, then add video once the pipeline is proven.

> [!NOTE]
> MoneyPrinterTurbo needs to be run as a local service (Docker or Python). Phase 2 assumes it's running on `localhost:8080`. You can skip this initially and just use static image cards.
