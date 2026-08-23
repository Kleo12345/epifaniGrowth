# Instagram Hook Research → Engine Swipe File

Scrapes top-performing Instagram posts in a niche, transcribes every Reel,
extracts the winning **hooks**, and feeds them into the script engine
(`engine/core/script_generator.py`) as few-shot examples — plus a punish-list
of weak openers for the critic. Adapted for Linux from Leif Abel's
(@leifabel11) Instagram Research Tool.

**Run this WITH Claude in a session** — one pipeline step (reading the post
screenshots to pull accurate engagement numbers and captions) is done by
Claude's vision, not a script. That's what makes it work without any API key.

## Ground rules (from the growth plan)

- **Research build-in-public / indie-hacker / AI-founder content**, NOT
  `#footballpredictions` — top tipster content is exactly what the compliance
  guardrails forbid imitating.
- **Log into Instagram with a personal/throwaway account, never @epifani** —
  scraping through a logged-in session carries account risk.

## Prerequisites

Node 18+, Python 3, ffmpeg, plus: `pip install yt-dlp faster-whisper`
and `npm install` in this folder.

## Run (in order)

1. **Launch the browser with remote debugging** (close it fully first):
   ```
   chromium --remote-debugging-port=9222          # snap chromium
   google-chrome --remote-debugging-port=9222     # Chrome
   ```
   Log into instagram.com in that window and keep the tab in the
   **foreground** during the scrape (background tabs give blank screenshots).

2. **Scrape** (revisits are skipped, safe to re-run):
   ```
   node scripts/scrape.js build-in-public
   ```

3. **Transcribe** the downloaded Reel audio:
   ```
   python3 scripts/transcribe.py build-in-public
   ```

4. **Claude analysis step** (no script): Claude reads every screenshot in
   `projects/<name>/post-screenshots/`, corrects `author / likes / comments /
   views / caption` in `raw-posts.json`, sets each post's `hook` (spoken first
   sentence for Reels, slide text for carousels, caption first sentence as
   fallback), optionally sets `style` (one of the engine's HOOK_STYLES), then
   recomputes `engagement = max(likes, views) + comments` and re-sorts.
   The screenshot always wins over the scraper's numbers.

5. **Report** (styled HTML, opens locally):
   ```
   node scripts/report-html.js build-in-public
   xdg-open projects/build-in-public/report.html
   ```

6. **Build the engine swipe file** — this is the actual payoff:
   ```
   python3 scripts/build_swipe_file.py build-in-public
   ```
   Writes `engine/assets/hooks_swipe_file.json`. From then on every
   journey/track-record script generation automatically shows the writer
   proven hooks matching the day's hook style, and the critic punishes
   resemblance to the low-performer patterns. Delete the file to switch the
   engine back to swipe-free behavior.

## Config

`projects/<name>/config.json` — `searchTerms` (hashtags), `competitors`
(profile URLs), `maxPostsPerSearch`, and optional `cookiesFrom` to override
the yt-dlp cookie source (snap chromium is auto-detected).
