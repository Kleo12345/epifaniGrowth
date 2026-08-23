# Epifani — Viral Growth Plan (v1 draft)

> Working draft to react to and merge with your own research. Nothing here changes
> the build: we are **not** wiring auto-publishing yet. This is the distribution
> strategy the video engine feeds into.

---

## 0. The one decision everything hangs on: positioning

Our niche (AI football/soccer predictions) is a **platform-policy minefield**. On
organic (non-ad) content:

- **TikTok** removes content that "provides insights, stats, or betting strategies
  designed to influence betting outcomes," bans gambling links in bio, and
  flags/removes accounts that read as tipster/casino promo.
- **Meta (IG/FB)** is tightening: gambling promo needs affiliate registration +
  approval; unapproved betting content gets suppressed.
- **YouTube** age-gates / limits ads on gambling-adjacent content.

**Prediction-market / data products (Kalshi, Polymarket style) are treated more
leniently** than sportsbooks because they read as data/markets, not "bet now."

### → Our lane: "solo founder building an AI prediction engine, in public."
The videos are a **tech/build-in-public/founder story**. The daily pick appears as
**proof the model works** (accuracy, confidence, track record) — never as betting
advice. This is a shield, and it's already what the Founder's Journey format is.

**Do (safe, on-brand):**
- "Day X of building an AI that predicts football."
- Show the pick as a *model output* + track its hit rate over time.
- Talk code, data, the grind, wins/losses of *building*.
- CTA: "watch the build / see the model's picks free at epifanii.com."

**Don't (gets throttled/banned):**
- "Bet this," "lock of the day," odds framed as a wager to place.
- Bookmaker/affiliate links, "guaranteed," "easy money."
- Bio links to anything that looks like a sportsbook.

> Action for script engine: bake these do/don'ts into `script_generator` prompts so
> every generated script stays in the safe lane automatically. (See §7.)

---

## 1. The content strategy (what makes it spread)

Virality on short-form = **retention × shares/saves**, not view count. Three levers:

### a) Hook (first 1–3 seconds decides everything)
Data point from research: hooking viewers in the first ~15s keeps ~65% to the end;
missing the hook drops retention below ~45%. We already have a Gemini *critic* that
scores the hook — we should make the hook axis the **hardest gate** (reject < 8/10),
and A/B different hook styles:
- Struggle open: "Spent 11 hours today and my model still can't predict draws."
- Stakes open: "If this pick loses, my model's accuracy drops below 60%."
- Curiosity gap: "I found the one stat that breaks every prediction model."
- Result open: "My AI called 7 of the last 9. Here's today's."

### b) Series / formats (recurring = returning viewers = algorithm trust)
Pick 3–4 repeatable series so people know what they're subscribing to:
1. **"Day X building Epifani"** — the daily journey (current default).
2. **"Model Track Record"** — flex the model's *history*: "X% over the last N picks,"
   current streak, best runs. We DON'T do per-match "did it land" (no result data),
   so this leans on the aggregate history instead — still the single most
   trust-building thing for a prediction product, just framed as the record, not a
   scorecard. *(Killer trust format — honest, data-driven, compounding.)*
3. **"Why the model thinks X"** — 30s explainer of one prediction's reasoning
   (pre-match, framed as model logic — safe, not a wager).
4. **"Building in public: today I broke ___"** — pure dev/founder relatability.

### c) Loops & payoffs
End videos so they loop (last line feeds the first) or with an open question that
drives comments. Comments/replies = reach. Reply to every early comment with a
video when possible (TikTok/IG reward this heavily).

### d) Comment-gate CTA — BUILT into the engine (2026-07-17)
The single biggest growth mechanic found in the competitor research (liambuilds.ai:
a comment-gated reel turned 27.6K likes into **44.4K comments**): end the video with
*"comment `MODEL` and I'll DM you what the engine's calling today."*
(Keyword is `MODEL`, not `PICKS` — "picks" is scam-capper vocabulary; a tech-flavored
keyword keeps the mechanic without the tipster smell. See §1e.)
- **Why it works:** comments are the strongest algorithm signal; the DM converts a
  viewer into a follower + direct relationship; and it sidesteps link-in-bio /
  external-link suppression entirely (the DM carries the epifanii.com link).
- **How it's wired:** both script generators take `cta_mode="site"|"comment"`
  (dashboard radio, CLI `--cta`, env `CTA_MODE`; keyword via `COMMENT_GATE_WORD`).
  In comment mode the TikTok/IG captions repeat the gate and drop the link;
  YouTube/X captions keep the epifanii.com link (no comment→DM flow there).
  A post-check guarantees the keyword survives the critic's rewrite passes.
- **Compliance:** the DM offer is always framed as *the model's output/record*,
  never tips — the critic explicitly allows the gate but still nukes any
  betting-advice framing.
- **Ops note:** replying to comments with DMs is manual at first (that's fine —
  early volume is low and manual DMs feel personal); on Instagram, ManyChat can
  automate comment→DM later. Suggested default: use **comment-gate on the
  "Model Track Record" series** (highest curiosity → highest comment intent),
  site-link on everyday journey posts, then follow the data.

### e) Anti-scam positioning — BUILT into the engine (2026-07-17)
The market we sell into is saturated with scam tipster/capper accounts, and their
signature shapes (win-rate flexing, comment→DM funnels) overlap with our own
strongest mechanics. Viewers and moderators pattern-match on *shape* — so the
engine now makes the difference visible in every script:
- **Anti-scam identity in the system prompt** (applies to journey, track-record,
  and every rewrite): no urgency/pressure, no number without its sample, admit
  fallibility, claims must sound checkable, never rant at specific accounts.
- **`trust` critic axis with a hard ship-gate (≥8)** alongside `safe`: scores
  whether a scam-burned viewer would read the script as a transparent builder or
  another capper. Win-rate flexing with zero build/honesty content, hype, or
  unverifiable claims forces a rewrite.
- **Show the losses.** The track-record stats block now computes the miss count
  and the writer must say it out loud ("it got one wrong out of ninety") — the
  one move scam accounts can never copy. Near-100% rates are spoken as counts
  ("33 of its last 33"), never "100 percent accurate."
- **Checkable-record beat:** every track-record script points at the public
  record on epifanii.com — "check my math" energy, never take-my-word-for-it.
- **TRUST/ANTI-SCAM hook style** added to the A/B rotation: "Every football
  prediction account you've seen is selling you something. So I'm building one
  where you can check the math."
Transparency is the moat: it's the one differentiator the scam accounts are
structurally unable to imitate.

---

## 2. Distribution mechanics

### Platform priority (for this niche + build-in-public)
1. **TikTok** — highest organic reach for a cold-start solo account; build-in-public
   + AI both trend here.
2. **Instagram Reels** — second engine; also where "founder" audiences live.
3. **YouTube Shorts** — compounding long-tail + funnels to future long-form.
4. **X/Twitter** — build-in-public *native* home; threads + video; devs/founders.
   Lower raw reach but highest-quality audience for a data product.
5. **LinkedIn** — surprisingly strong for "I built an AI" founder content; low
   competition, B2B/credibility.

### Cadence
Research consensus: **3–5 posts/week per platform** minimum to earn algorithm
favor. Same core video, **re-captioned/re-hooked per platform** (never identical
dumps — the algorithms and audiences differ).

**Good news on our constraints:** current free tiers support this comfortably —
Gemini free ≈ 3–4 scripts/day, ElevenLabs free 10k chars/mo ≈ ~100 short scripts/mo.
So 3–5 videos/week needs **no paid upgrade** yet.

### Native upload vs API
Platforms **demote** content with watermarks from other apps and reward native
posting. Early on: **post natively / manually** (also keeps us under the "automation"
radar for a fresh account). Automate only once volume hurts (that's the parked
publishing pipeline — revisit in §8).

---

## 3. Tools to evaluate (you'll add your finds; we merge)

| Need | Tool options | Notes / pricing |
|---|---|---|
| **Cross-post + schedule** (1 upload → all platforms, per-platform captions) | **ShortSync** (free tier, ~€15/mo), **Buffer** (cheap, broad), **Repurpose.io** (~$25/mo, trigger-based automation), **Hootsuite** (heavy/legacy) | ShortSync/Buffer best for solo + budget. Repurpose.io if we want "publish once → auto-fan-out." |
| **AI clip + caption + post** (if we ever repurpose long-form) | **OpusClip**, **Bytecap** | Only relevant if you start doing long-form/streams to slice. |
| **Trend / sound / hashtag research** | TikTok Creative Center (free), Google Trends, platform native search | Match trending *sounds* early — big reach multiplier on TikTok/Reels. |
| **Hook / competitor research** | Manually study 10–20 build-in-public + AI creators; save a swipe file | Cheapest, highest ROI. Build a hook swipe-file we feed the script engine. |
| **Analytics beyond native** | Native dashboards first; add a tool only when we post enough to need it | Track watch-time %, shares, saves — not views. |

> We already generate captions/hashtags in the pipeline; a cross-poster just needs
> the finished MP4 + text. No new build required to *start* using one manually.

---

## 4. Metrics that matter (and the feedback loop)

Track per video (weekly review):
- **Avg watch % / completion** — the algorithm's #1 signal.
- **Shares + saves** — the virality signal (weight these highest).
- **Follows-per-view** — are we converting reach to audience?
- **Comments** — reach amplifier + content ideas.
- **Click-through to epifanii.com** — the business metric.
- **Model hit-rate** (for "Model vs Reality") — trust metric, our moat.

**The loop that compounds:** feed what wins back into the engine. Winning hooks →
add to the Gemini writer's few-shot examples. Losing patterns → add to the critic's
"punish" list. Over weeks the script engine literally learns our channel's voice.

---

## 5. Cold-start playbook (first accounts, weeks 1–2)

- Post **consistently before worrying about virality** — the algorithm needs ~10–20
  posts to understand and place the account.
- **Niche down hard** the first 20 videos so the algorithm can categorize us
  (AI + football-predictions + build-in-public). Don't dilute early.
- Engage 15 min/day in the niche (comment on bigger creators) to warm the account.
- Don't buy followers / don't cross-dump watermarked clips — both hurt cold-start.
- Pin a "start here / what is Epifani" video on each profile.

---

## 6. 30 / 60 / 90 day rollout

**Days 1–30 — Foundation & consistency**
- Lock positioning (§0) into the script engine.
- Stand up TikTok + IG Reels + YouTube Shorts + X profiles (consistent handle/bio,
  no risky links; bio → epifanii.com framed as "AI football predictions").
- Ship the daily "Day X" + start the "Model vs Reality" scorecard series.
- Manual native posting. 1 video/day, 5–7/week. Study analytics weekly.

**Days 31–60 — Optimize what works**
- Double down on the 1–2 series/hooks with best watch% + shares.
- Start per-platform re-captioning; test posting times.
- Begin the win/loss → script-engine feedback loop.
- Introduce a cross-poster (ShortSync/Buffer) to save time — still reviewing each.

**Days 61–90 — Scale & compound**
- If cadence hurts, revisit the parked auto-publish pipeline (§8).
- Consider 1 long-form/week (YouTube) sliced into shorts.
- Push the track record ("model is X% over 90 days") as the trust flywheel to
  epifanii.com conversions.

---

## 7. What this means for the build (engine changes, when you're ready)

None are "publishing" — all are content-quality/safety:
1. **Positioning guardrails** in `script_generator` prompts (§0 do/don'ts) so scripts
   never drift into tipster/gambling language.
2. **Harden the hook gate** in the critic (reject weak hooks harder; A/B hook styles).
3. **"Model vs Reality" script mode** — a second script template that reports whether
   yesterday's pick landed (needs result data — is match-result data in the portal
   feed? open question §8).
4. **Per-platform caption/hashtag variants** from the same script (TikTok vs YT vs X).
5. **Hook swipe-file → few-shot** and **win/loss → critic** feedback loop.

---

## 8. DECISIONS (locked 2026-07-12)

- **100% organic.** No ad spend. Everything below assumes earned reach only.
- **No per-match results**, BUT **we use the model's HISTORY/track record.** So the
  trust format is not "did this pick land" — it's **"the model's record so far"**
  (aggregate accuracy / streaks / performance over time). See revised §1b.
- **All 4 platforms at once, same core strategy** (TikTok, IG Reels, YT Shorts, X).
  Same video everywhere; only captions/hashtags get light per-platform tweaks.
- **No face — but YES to voice.** → Clone the founder's voice with ElevenLabs so
  every auto-generated video sounds like a real person, not a stock AI voice. This
  is now the #1 human-feel/trust action. Steps in §9.

### Track-record data — FOUND (2026-07-12)
Portal (`/home/john/dev/web_portalEpifani`, live at epifanii.com) exposes public,
no-auth endpoints the engine can read directly:
- `epifanii.com/api/performance/stats` → 30-day `hitRate`, `sample` (N picks),
  `avgEdge`, per-tier rates. *(Live: 93.4% over 137; strong-tier 93.1% over 58.)*
- `epifanii.com/api/performance/winners` → last 3 winning picks w/ edge & probability.
→ "Model Track Record" format is fully feasible. **Framing caution:** flex it
responsibly ("strong-tier hit 93% over the last 58"), avoid "guaranteed" tone.

### Still to confirm (small, non-blocking)
- Are `@epifani` / `@epifanii` handles free on all 4 platforms?
- Which cross-poster fits your flow (try ShortSync + Buffer free tiers).

---

## 9. Immediate next actions

**Your side:**
1. **Record voice sample** for the clone: 1–3 min of clean speech (quiet room, your
   normal speaking energy — a bit upbeat). Read anything natural (even a couple of
   these scripts). Save as wav/mp3.
2. Grab the 4 handles + set consistent bios (safe framing, link → epifanii.com).
3. Trial ShortSync + Buffer free tiers.

**My side (when you say go — all content-quality, no publishing):**
1. **Voice clone — script is READY:** `engine/tools/clone_voice.py`. Once you drop the
   sample: `python tools/clone_voice.py path/to/sample.mp3 --test` → it clones, writes
   the new `ELEVENLABS_VOICE_ID` to `.env`, and renders a test line. **Heads-up:**
   ElevenLabs Instant Voice Cloning needs a paid plan (Starter ~$5/mo); the free tier
   rejects it. That $5/mo is the one paid dependency for using your real voice.
2. **Positioning guardrails** into `script_generator` (§0 do/don'ts).
3. **"Model Track Record" script mode** — a format that flexes the model's history
   ("X% over the last N picks", current streak) as the trust flywheel. Needs the
   history data source (see §8).
4. Harden the **hook gate** + start the hook swipe-file → few-shot loop.
5. Per-platform caption/hashtag variants from one script.

Publishing automation stays parked until you say go.
