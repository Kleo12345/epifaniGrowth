# Windows Setup Guide

Quick steps to get the Epifani Growth Engine running on Windows. Follow in order.

## 1. Install prerequisites

- **Miniconda** — https://docs.conda.io/en/latest/miniconda.html (Python 3.11+)
- **FFmpeg** — https://www.gyan.dev/ffmpeg/builds/ (download the "release essentials" zip)
  - Unzip it somewhere permanent, e.g. `C:\ffmpeg`
  - Add `C:\ffmpeg\bin` to your PATH: Windows Settings → search "Environment Variables" →
    edit the `Path` variable under "User variables" → add `C:\ffmpeg\bin`
  - Verify: open a **new** terminal and run `ffmpeg -version`
- **Git** (if you're cloning instead of copying the folder) — https://git-scm.com/download/win

Use **PowerShell** or **Command Prompt** for everything below — both work.

## 2. Get the project

Copy or clone the whole `epifaniGrowthPlan` folder (it contains `engine/` and
`MoneyPrinterTurbo/` — both are required, MoneyPrinterTurbo does the actual video
assembly) to somewhere on your machine, e.g. `C:\Users\<you>\epifaniGrowthPlan`.

## 3. Create the conda environment

```powershell
cd C:\Users\<you>\epifaniGrowthPlan
conda create -n epifani-growth python=3.11 -y
conda activate epifani-growth

cd engine
pip install -r requirements.txt

cd ..\MoneyPrinterTurbo
pip install -r requirements.txt
```

## 4. Configure credentials

```powershell
cd ..\engine
copy .env.example .env
```

Open `.env` in a text editor and fill in at least:
- `GEMINI_API_KEY` — required, scripts are generated with Gemini
- `EPIFANI_API_URL` — leave as-is if pointing at the same portal; it falls back to a
  local `predictions.json` if the portal isn't reachable
- Leave any publisher keys (Twitter, TikTok, Instagram, YouTube, ElevenLabs) blank
  until you actually need that platform — the engine skips unconfigured ones

Also copy MoneyPrinterTurbo's config and fill in its own LLM/TTS keys:

```powershell
cd ..\MoneyPrinterTurbo
copy config.example.toml config.toml
```

## 5. Run it

From `engine\`, with the conda env active:

```powershell
conda activate epifani-growth
cd C:\Users\<you>\epifaniGrowthPlan\engine

# CLI — preview today's picks, no posting
python main.py --list-picks
python main.py --dry-run --run-all

# Dashboard (recommended)
streamlit run web_ui\dashboard.py
```

The dashboard opens in your browser. Its **Start/Stop scheduler** buttons work
natively on Windows — no extra setup needed.

To control the scheduler from the terminal instead of the dashboard:

```powershell
python scheduler_ctl.py start
python scheduler_ctl.py status
python scheduler_ctl.py stop
```

## Notes

- Everything above (fonts, scheduler start/stop, MoneyPrinterTurbo launcher) was
  fixed to run natively on Windows — no WSL or Git Bash required.
- If `ffmpeg -version` fails after adding it to PATH, restart the terminal (PATH
  changes don't apply to already-open windows).
- First run of `--build-videos` / `--journey-video` will feel slow — MoneyPrinterTurbo
  downloads its models/stock assets on first use.
