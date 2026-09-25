# Windows Setup Guide

Quick steps to get the Epifani Growth Engine running on Windows. Follow in order.

## 1. Install prerequisites

Open **PowerShell** (no need to run as Administrator — `winget` works either way)
and run:

```powershell
winget install -e --id Anaconda.Miniconda3
winget install -e --id Gyan.FFmpeg
winget install -e --id Git.Git
```

Close and reopen PowerShell after this (so the updated PATH and `conda` are
picked up), then verify everything is on PATH:

```powershell
conda --version
ffmpeg -version
git --version
```

If `conda` isn't recognized, open **"Anaconda Prompt (miniconda3)"** from the
Start menu instead — the installer sometimes needs that shell for `conda init`
to have taken effect — then run `conda init powershell`, close, reopen
PowerShell, and try again. If `ffmpeg` isn't recognized after reopening, log
out/in once (winget PATH updates only fully apply on next session).

**Optional — Rhubarb Lip Sync** (real phoneme-timed mouth sync for the journey
avatar; no winget package, so grab the release zip directly):

```powershell
Invoke-WebRequest -Uri "https://github.com/DanielSWolf/rhubarb-lip-sync/releases/download/v1.14.0/Rhubarb-Lip-Sync-1.14.0-Windows.zip" -OutFile "$HOME\rhubarb.zip"
Expand-Archive -Path "$HOME\rhubarb.zip" -DestinationPath "$HOME\rhubarb" -Force
[Environment]::SetEnvironmentVariable("Path", "$env:Path;$HOME\rhubarb\Rhubarb-Lip-Sync-1.14.0-Windows", "User")
Remove-Item "$HOME\rhubarb.zip"
```

Close and reopen PowerShell, then verify with `rhubarb --version`. Without it,
the journey video pipeline falls back to the old amplitude-based lip-flap —
nothing breaks, the mouth sync is just less accurate.

## 2. Get the project

```powershell
cd $HOME
git clone git@github.com:Kleo12345/epifaniGrowth.git epifaniGrowthPlan
cd epifaniGrowthPlan
```

(If you haven't set up an SSH key with GitHub on this machine, use the HTTPS
URL instead: `git clone https://github.com/Kleo12345/epifaniGrowth.git epifaniGrowthPlan`.)

This gets you `engine/` and `MoneyPrinterTurbo/` — both are required,
MoneyPrinterTurbo does the actual video assembly.

## 3. Create the conda environment

```powershell
cd $HOME\epifaniGrowthPlan
conda create -n epifani-growth python=3.11 -y
conda activate epifani-growth

cd engine
pip install -r requirements.txt

cd ..\MoneyPrinterTurbo
pip install -r requirements.txt
```

## 4. Configure credentials

```powershell
cd $HOME\epifaniGrowthPlan\engine
copy .env.example .env
notepad .env
```

Fill in at least:
- `GEMINI_API_KEY` — required, scripts are generated with Gemini
- `EPIFANI_API_URL` — leave as-is if pointing at the same portal; it falls back to a
  local `predictions.json` if the portal isn't reachable
- Leave any publisher keys (Twitter, TikTok, Instagram, YouTube, ElevenLabs) blank
  until you actually need that platform — the engine skips unconfigured ones

Save and close Notepad, then do the same for MoneyPrinterTurbo's config
(its own LLM/TTS keys):

```powershell
cd ..\MoneyPrinterTurbo
copy config.example.toml config.toml
notepad config.toml
```

## 5. Run it

From `engine\`, with the conda env active:

```powershell
conda activate epifani-growth
cd $HOME\epifaniGrowthPlan\engine

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
- If a command isn't recognized right after a `winget install`, close and reopen
  the terminal (PATH changes don't apply to already-open windows).
- First run of `--build-videos` / `--journey-video` will feel slow — MoneyPrinterTurbo
  downloads its models/stock assets on first use.
