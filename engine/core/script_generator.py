"""
Script generation for the Epifani Growth Engine (Google Gemini).

Two output modes:
  • Twitter/X thread copy for a pick      → generate_thread / generate_all_threads
  • Founder's Journey video voiceover      → generate_journey_script
    (first-person "Day X of building Epifani" narrative, woven with the
     day's top picks, vetted by an LLM hook/pacing/flow critic loop)
"""
import os
import re
import json
import random
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

from google import genai
from dotenv import load_dotenv

from core.prediction_fetcher import Pick
from core import analytics

load_dotenv()

_gemini_client = None

def _get_client() -> genai.Client:
    global _gemini_client
    if _gemini_client is None:
        api_key = os.getenv("GEMINI_API_KEY", "")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY is not set in your .env file.")
        _gemini_client = genai.Client(api_key=api_key)
    return _gemini_client

_SYSTEM_PROMPT = """You are a hype sports content writer for Epifani AI, a premium AI football prediction platform.
Write punchy, data-driven copy that feels exciting but credible — not spammy.
Never use generic filler phrases like "Are you ready?" or "Don't miss out!".
Always keep tweet character limits (280 chars max per tweet).
Use 1–2 relevant emojis per tweet. No more."""

_THREAD_TEMPLATE = """Write a Twitter thread of exactly 3 tweets for this AI football prediction:

Match: {match}
Pick: {label}
Odds: {odds}
AI Confidence: {confidence_pct}%
Edge: +{edge_pct}%
Tier: {tier}
CTA URL: https://{cta_url}

Tweet 1 (Hook, max 240 chars): Grab attention with the match and the AI's confidence level. Be bold.
Tweet 2 (Stats, max 240 chars): Break down the confidence, edge value, and what it means. Feel like insider analysis.
Tweet 3 (CTA, max 240 chars): Drive to the site. Mention the full picks list is free. Include the URL.

Return ONLY the 3 tweets separated by the delimiter "---TWEET---". No numbering, no labels, no extra text."""


@dataclass
class ThreadCopy:
    tweet1: str   # hook
    tweet2: str   # stats
    tweet3: str   # CTA
    pick:   Pick

    def as_list(self) -> list[str]:
        return [self.tweet1, self.tweet2, self.tweet3]


import time

def call_gemini_with_retry(client, model, contents, max_retries=3, delay_secs=10):
    for attempt in range(max_retries):
        try:
            return client.models.generate_content(model=model, contents=contents)
        except Exception as e:
            err_msg = str(e)
            if "429" in err_msg or "RESOURCE_EXHAUSTED" in err_msg or "quota" in err_msg.lower():
                if attempt < max_retries - 1:
                    print(f"  ⚠ Gemini rate limited (429). Retrying in {delay_secs}s... (Attempt {attempt+1}/{max_retries})")
                    time.sleep(delay_secs)
                    continue
            raise e

def generate_thread(pick: Pick, story_highlight: str = "") -> ThreadCopy:
    """Call Gemini to generate a 3-tweet thread for the given pick."""
    story_hook = ""
    if story_highlight:
        story_hook = f"\n- Hook Tweet: Incorporate this founder's daily journey milestone: \"{story_highlight}\", explaining how it led to finding this prediction."
    else:
        story_hook = "\n- Hook Tweet: Start with a 'building in public' founder narrative (e.g. 'Day 12 of coding my sports betting AI...'). Keep it personal and first-person."

    thread_template = """Write a Twitter thread of exactly 3 tweets for this AI football prediction from a developer/founder's building-in-public perspective:

Match: {match}
Pick: {label}
Odds: {odds}
AI Confidence: {confidence_pct}%
Edge: +{edge_pct}%
Tier: {tier}
CTA URL: https://{cta_url}

Rules:
- Speak in the first-person ("I", "my AI", "we"). Keep it conversational and tech-focused.{story_hook}
- Tweet 1 (Hook, max 240 chars): Share the journey update and hook the reader, mentioning the match and the AI's confidence level.
- Tweet 2 (Stats, max 240 chars): Explain why the AI chose this pick based on the edge/probability. Feel like an insider technical analysis.
- Tweet 3 (CTA, max 240 chars): Drive to the site. Mention they can follow the journey here or get the full list of picks free at the URL.

Return ONLY the 3 tweets separated by the delimiter "---TWEET---". No numbering, no labels, no extra text."""

    prompt = thread_template.format(
        match          = pick.match,
        label          = pick.label,
        odds           = pick.odds,
        confidence_pct = pick.confidence_pct,
        edge_pct       = round(pick.edge * 100, 1),
        tier           = pick.tier,
        cta_url        = pick.cta_url,
        story_hook     = story_hook,
    )

    full_prompt = f"{_SYSTEM_PROMPT}\n\n{prompt}"
    client = _get_client()
    model_name = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
    
    response = call_gemini_with_retry(
        client=client,
        model=model_name,
        contents=full_prompt
    )
    raw = response.text.strip()

    parts = [t.strip() for t in re.split(r"---TWEET---", raw) if t.strip()]

    if len(parts) < 3:
        # Fallback: split on double newline
        parts = [t.strip() for t in raw.split("\n\n") if t.strip()]

    if len(parts) < 3:
        raise ValueError(f"Gemini returned unexpected format:\n{raw}")

    return ThreadCopy(
        tweet1 = parts[0][:280],
        tweet2 = parts[1][:280],
        tweet3 = parts[2][:280],
        pick   = pick,
    )


def generate_all_threads(picks: list[Pick], story_highlight: str = "") -> list[ThreadCopy]:
    threads = []
    for pick in picks:
        try:
            thread = generate_thread(pick, story_highlight)
            threads.append(thread)
            print(f"  ✓ Thread: {pick.match}")
        except Exception as e:
            print(f"  ✗ Thread failed for {pick.match}: {e}")
    return threads


# ══════════════════════════════════════════════════════════════════
# Founder's Journey video script engine
# ══════════════════════════════════════════════════════════════════

def project_day(on: date | None = None) -> int:
    """How many days into building Epifani we are (Day 1 = start date).

    Anchor priority:
      1. EPIFANI_START_DATE in .env (YYYY-MM-DD)
      2. earliest entry in analytics.db
      3. today (→ Day 1) if nothing else is available
    """
    on = on or date.today()
    start: date | None = None

    raw = os.getenv("EPIFANI_START_DATE", "").strip()
    if raw:
        try:
            start = datetime.strptime(raw, "%Y-%m-%d").date()
        except ValueError:
            print(f"  ⚠ EPIFANI_START_DATE='{raw}' is not YYYY-MM-DD — ignoring.")

    if start is None:
        first = analytics.earliest_post_date()
        if first:
            try:
                start = datetime.strptime(first, "%Y-%m-%d").date()
            except ValueError:
                start = None

    if start is None:
        start = on

    return max(1, (on - start).days + 1)


@dataclass
class JourneyScript:
    day: int
    milestone: str
    voiceover: str            # spoken narration (fed to TTS) — no emojis
    caption: str              # social caption (emojis/CTA OK)
    hashtags: str
    picks: list[Pick]
    critic_score: float = 0.0
    critic_notes: str = ""
    revisions: int = 0

    @property
    def word_count(self) -> int:
        return len(self.voiceover.split())

    @property
    def est_seconds(self) -> int:
        # ~2.6 spoken words/sec at a natural short-form pace
        return round(self.word_count / 2.6)


_JOURNEY_SYSTEM = """You are ghost-writing a talk-to-camera voiceover AS the founder of "Epifani" —
one solo developer building an AI football-prediction engine in public. You are literally him,
talking into his phone at the end of the day. Not a marketer, not a narrator, not a tipster.

Sound like a REAL person, not clean marketing copy. That means:
- First person, casual, a bit unpolished. Contractions always. It's fine to open mid-thought
  ("so", "okay so", "honestly", "not gonna lie", "right, so").
- Real, specific detail over slick summary. Name the actual thing that was annoying or cool today.
- A little self-deprecation / genuine feeling is good ("this took way longer than it should've").
- Vary sentence length. Short. Then a longer one that trails a bit. A fragment. Like real speech.
- NO ad rhythm (avoid three-part lists and "X, Y, and Z" polish). NO buzzwords like "seamlessly",
  "tangible", "articulate", "leverage", "game-changer", "unlock". NO hype, no "guaranteed wins",
  no "smash like". If a line sounds like a LinkedIn post or an ad, rewrite it.
The pick is just proof the thing works — mentioned like you'd mention it to a mate, not sold.
""" + """
COMPLIANCE — NEVER break these (TikTok/Meta/YouTube suppress or ban betting/tipster content):
- This is a BUILD-IN-PUBLIC TECH story. You are a developer showing an AI you're building. The pick
  is the MODEL'S OUTPUT / proof it works — never a tip and never advice to gamble.
- NEVER tell anyone to bet, stake, "back", or "tail" anything. Ban: "lock", "banker", "easy money",
  "guaranteed", "can't lose", "smash the bet", "bet slip", bookmaker/sportsbook talk, odds framed as
  a wager to place, and anything promoting gambling or affiliates.
- Refer to a pick as what the model PREDICTS and how confident it is — like sharing a result, not a
  recommendation. The only CTA is to follow the build / see the model's picks at epifanii.com.

ANTI-SCAM IDENTITY — this niche is drowning in scam tipster/capper accounts (win-rate screenshots,
urgency, "DM me for the play", guaranteed money). We are the transparent OPPOSITE, and it must show:
- Never use urgency or pressure ("act now", "don't miss", "last chance").
- Never flex a number without its sample ("93 percent" alone = capper; "93 percent over the last 58" = data).
- Admit fallibility naturally — the model misses sometimes, and saying so is the trust move scams can't copy.
- Claims should sound CHECKABLE (the record is public on epifanii.com), never take-my-word-for-it.
- Don't attack or name specific accounts — the contrast is shown, not ranted about."""

_JOURNEY_WRITER = """Write today's talk-to-camera voiceover (a TikTok/Reels/Short) as the founder.

CONTEXT
- Day {day} of building Epifani in public.
- What he actually did today (his words): "{milestone}"
- The engine's top {n_picks} picks today (drop these in casually as proof, not tips):
{picks_block}

HARD LIMIT: under {target_words} words (~{target_secs}s). Shorter is better. Cut anything that sounds written.

HOOK DIRECTION for today (the first line must stop the scroll in the first 3 seconds): {hook_style}

SHAPE (loose, not a template — it should feel like one continuous thought)
- Open with the hook direction above — a real, specific first line. NOT a slogan, NOT "Day X of...",
  NOT a status update ("today I worked on / wired up / finished..."). If the hook direction points at
  a number or outcome (RESULT/FLEX, STAKES), that number goes in the FIRST sentence — the dev work is
  what comes after to explain it, never what you lead with.
- Then tell what he actually built today and why it mattered or annoyed him. Concrete.
- Slide into the picks like an aside ("oh and the engine's calling..."), team + the call + confidence. Don't hard-sell.
{cta_direction}

RULES
- VOICEOVER is read aloud by TTS: plain spoken words only. NO emojis, hashtags, stage directions, or "[pause]".
- Write how people actually TALK, not how they write. Read it out loud in your head — if it sounds like an ad, redo it.
{caption_rule}
- HASHTAGS: 4-6 tags (build-in-public + football/AI), space-separated, each starting with #.

Return EXACTLY this format and nothing else:
===VOICEOVER===
<the spoken script>
===CAPTION===
<the caption>
===HASHTAGS===
<the hashtags>"""

_JOURNEY_CRITIC = """You are a ruthless short-form editor for a build-in-public founder channel.
Be honest — most first drafts are a 5-6. You HATE anything that sounds like marketing or AI-written copy.

VOICEOVER:
\"\"\"{voiceover}\"\"\"

Rate each 1-10:
- hook: does the FIRST line stop the scroll in 3 seconds without being a slogan/clickbait? Be strict — a generic status-update opener ("Day X...", "So today I...") is a 5 at best.
- human: does it sound like a real person talking to their phone — casual, specific, imperfect — NOT clean ad copy? Punish buzzwords ("seamlessly", "tangible", "leverage", "game-changer"), three-part lists, and LinkedIn-speak hard.
- flow: does the build story slide naturally into the pick and a soft ending?
- safe: does it stay a BUILD-IN-PUBLIC / tech story and treat any pick as the MODEL'S prediction/proof, NOT betting advice? Score 1-3 if it tells people to bet/stake/back a pick, uses "lock/banker/guaranteed/easy money", or reads like a tipster/gambling promo. Score 9-10 only if a platform moderator would see a developer talking about their AI, not gambling promotion. (A CTA asking viewers to comment a keyword to get the MODEL'S OUTPUT by DM is fine — that's a product CTA, don't punish it — unless it promises winnings or frames the DM as betting tips.)
- trust: this niche is full of SCAM capper/tipster accounts, and viewers pattern-match on shape. Would a scam-burned viewer read this as a transparent builder or as another capper? Score 1-3 if it flexes win rates with zero build/process/honesty content, uses urgency or hype, or makes claims with no sample size and no way to check them. Score 9-10 only if the numbers are tied to samples, fallibility or limits are acknowledged (or nothing needs acknowledging), and it sounds like someone showing their work, not selling a dream. (Percentages themselves are fine; a comment-gate CTA is fine.)

Return ONLY a JSON object, no markdown fences:
{{"hook": <int>, "human": <int>, "flow": <int>, "safe": <int>, "trust": <int>, "critique": "<one or two sentences of concrete, actionable fixes; if safe or trust < 8 say exactly what language to remove or add>"}}"""

_JOURNEY_REWRITE = """Revise this voiceover using the editor's note. Keep it as ONE natural spoken thought —
casual, first person, specific, imperfect, like a real founder talking to camera. Kill any marketing/ad tone
and buzzwords. Keep it spoken-word (no emojis/hashtags/labels) and roughly the same length or shorter.
If the ending asks viewers to comment a keyword, KEEP that comment-gate (same keyword) in the revision.

EDITOR NOTE: {critique}

CURRENT VOICEOVER:
\"\"\"{voiceover}\"\"\"

Return ONLY the revised voiceover text — no labels, no commentary."""

_JOURNEY_CONDENSE = """This short-form voiceover is too long. Cut it to AT MOST {max_words} words while
keeping the hook, the build story, the prediction proof (if any), and the ending CTA (if it's a
comment-the-keyword gate, keep the exact keyword). Keep it natural spoken-word — no emojis, hashtags,
labels, or stage directions. Tighten sentences, drop filler.

CURRENT VOICEOVER:
\"\"\"{voiceover}\"\"\"

Return ONLY the shortened voiceover text."""


# Rotating hook styles — the critic hook-gate is strict, and varying the opener
# stops every video starting the same way (a big "AI-generated" tell).
HOOK_STYLES = [
    "STRUGGLE — open on today's frustration/problem, blunt and specific "
    "(e.g. 'Eleven hours in and the model still can't call a draw.').",
    "STAKES — open on what's on the line, a real risk/number "
    "(e.g. 'If today's pick misses, my 30-day accuracy drops under 90.').",
    "CURIOSITY GAP — open on an intriguing, unresolved statement "
    "(e.g. 'I found the one stat that quietly breaks my whole model.').",
    "RESULT/FLEX — open with a concrete NUMBER that already exists right now — the "
    "pick's confidence, a streak, a hit-rate, a tier — NOT a status update about what "
    "you built today (e.g. '78% confidence on today's call — that's the highest all "
    "month.' or 'The model's now 9 for its last 11.'). The number IS the hook; the "
    "build story comes after, as the 'here's how' — never lead with the dev work.",
    "CONFESSION — open by admitting a mistake or something you got wrong "
    "(e.g. 'I shipped a bug today that inflated every prediction. Rough.').",
    "TRUST/ANTI-SCAM — open by calling out how scammy this niche is and positioning as "
    "the transparent opposite, without naming anyone "
    "(e.g. 'Every football prediction account you've seen is selling you something. "
    "So I'm building one where you can check the math.').",
]


# ── CTA modes ────────────────────────────────────────────────────────────────
# "site"    → soft ending: follow the build / picks free at epifanii.com.
# "comment" → comment-gate: viewers comment a keyword, the founder DMs them the
#             model's output. The niche research showed this is the growth engine
#             in build-in-public (a comment-gated reel turned 27.6K likes into
#             44.4K comments): comments feed the algorithm, the DM converts to a
#             follower, and it sidesteps link-in-bio suppression. The DM offer is
#             ALWAYS the model's output/record — never betting tips.
CTA_MODES = ("site", "comment")
# "MODEL" not "PICKS": comment-a-keyword→DM is also the signature move of scam
# capper accounts, and "picks" is their vocabulary — a tech-flavored keyword
# keeps the mechanic without the tipster smell.
COMMENT_GATE_WORD = os.getenv("COMMENT_GATE_WORD", "MODEL")


def _resolve_cta_mode(cta_mode: str | None) -> str:
    mode = (cta_mode or os.getenv("CTA_MODE", "site")).strip().lower()
    return mode if mode in CTA_MODES else "site"


def _cta_direction(cta_mode: str, offer: str) -> str:
    """The writer prompt's ending direction. `offer` is what the DM delivers
    (worded per format: today's model output vs. the model's record)."""
    if cta_mode == "comment":
        return (f'- End with a comment-gate, tossed off like an afterthought, not salesy: they comment '
                f'the word "{COMMENT_GATE_WORD}" and you\'ll DM them {offer}. One casual line (e.g. '
                f'"comment {COMMENT_GATE_WORD} and I\'ll send you what the model\'s calling today"). '
                f"The DM is the MODEL'S OUTPUT — never call it tips, advice, or anything to bet on.")
    return "- End soft and human — follow the build / the model's picks are free at epifanii.com. Not a marketing CTA."


def _caption_rule(cta_mode: str) -> str:
    if cta_mode == "comment":
        return (f'- CAPTION: the on-platform text post, 1-2 lines, 1-2 emojis ok. MUST repeat the '
                f'comment-gate ("comment {COMMENT_GATE_WORD}" → DM). NO link — the DM is the delivery.')
    return "- CAPTION: the on-platform text post, 1-2 lines, 1-2 emojis ok, include epifanii.com."


# ── Hook swipe file (built by research/scripts/build_swipe_file.py) ──────────
# Real top-performing hooks scraped from the niche. If the file exists, the
# writer gets proven openers as few-shot examples and the critic gets a
# punish-list of weak openers. Absent file = engine behaves exactly as before.
_SWIPE_FILE = Path(__file__).resolve().parents[1] / "assets" / "hooks_swipe_file.json"


def _load_swipe() -> dict:
    path = Path(os.getenv("HOOKS_SWIPE_FILE", str(_SWIPE_FILE)))
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def _hook_direction(hook_style: str) -> str:
    """The writer's hook direction: the chosen style, plus (when a swipe file
    exists) up to 3 real top-performing niche hooks of that style as few-shot
    examples — falling back to the overall best if none match the style."""
    hooks = _load_swipe().get("hooks") or []
    if not hooks:
        return hook_style
    style_name = hook_style.split("—")[0].strip().upper()
    matching = [h for h in hooks
                if h.get("hook") and h.get("style", "").upper() == style_name] or \
               [h for h in hooks if h.get("hook")]
    examples = [h["hook"] for h in matching[:3]]
    if not examples:
        return hook_style
    ex_block = "\n".join(f'  - "{e}"' for e in examples)
    return (f"{hook_style}\n"
            "REAL opening lines from top-performing videos in this niche — study their energy,"
            " specificity and rhythm, then write your OWN (do NOT copy or lightly reword them):\n"
            + ex_block)


def _critic_punish_block() -> str:
    """Low-performer opener patterns from the niche research, injected into the
    critic prompt so resemblance drags the hook score down."""
    patterns = _load_swipe().get("punish_patterns") or []
    if not patterns:
        return ""
    lines = "\n".join(f'- "{p}"' for p in patterns[:6])
    return ("\nThese openers came from LOW-performing videos in this exact niche. If the first "
            f"line resembles any of them in shape or energy, cap the hook score at 6:\n{lines}\n")


def _ensure_comment_gate(voiceover: str, cta_mode: str, offer: str) -> str:
    """In comment mode the keyword IS the mechanic — if a rewrite/condense pass
    dropped it, append a natural gate line so the funnel never silently breaks."""
    if cta_mode != "comment" or COMMENT_GATE_WORD.lower() in voiceover.lower():
        return voiceover
    print(f"  ⚠ Comment-gate keyword '{COMMENT_GATE_WORD}' missing after revisions — appending gate line.")
    return f"{voiceover.rstrip()} Oh, and comment {COMMENT_GATE_WORD} and I'll DM you {offer}."


def _pick_line(p: Pick) -> str:
    return f"- {p.match} ({p.league}): {p.label} @ {p.odds} — {p.confidence_pct}% confidence [{p.tier}]"


def _parse_sections(raw: str) -> dict:
    """Parse the ===SECTION=== delimited writer output."""
    sections = {"voiceover": "", "caption": "", "hashtags": ""}
    current = None
    for line in raw.splitlines():
        stripped = line.strip()
        if stripped.upper() == "===VOICEOVER===":
            current = "voiceover"; continue
        if stripped.upper() == "===CAPTION===":
            current = "caption"; continue
        if stripped.upper() == "===HASHTAGS===":
            current = "hashtags"; continue
        if current:
            sections[current] += line + "\n"
    return {k: v.strip() for k, v in sections.items()}


def _critique(client, model, voiceover: str) -> tuple[dict, str]:
    """Run the LLM critic. Returns (scores, critique_text).

    scores = {"hook","human","flow","safe","avg"} (floats). On unparseable output
    it returns perfect scores so a misbehaving critic never blocks the pipeline.
    """
    prompt = _JOURNEY_CRITIC.format(voiceover=voiceover)
    punish = _critic_punish_block()
    if punish:
        prompt = prompt.replace("Return ONLY a JSON object", punish + "\nReturn ONLY a JSON object")
    resp = call_gemini_with_retry(client=client, model=model, contents=prompt)
    raw = resp.text.strip()
    raw = re.sub(r"^```(?:json)?|```$", "", raw, flags=re.MULTILINE).strip()
    try:
        data = json.loads(raw)
        hook = float(data.get("hook", 0))
        human = float(data.get("human", data.get("pacing", 0)))
        flow = float(data.get("flow", 0))
        safe = float(data.get("safe", 10))    # default safe if the critic omits it
        trust = float(data.get("trust", 10))  # default trusted if the critic omits it
        avg = round((hook + human + flow) / 3, 1)
        return ({"hook": hook, "human": human, "flow": flow, "safe": safe,
                 "trust": trust, "avg": avg},
                str(data.get("critique", "")).strip())
    except (json.JSONDecodeError, ValueError):
        # If the critic misbehaves, don't block the pipeline.
        return ({"hook": 10.0, "human": 10.0, "flow": 10.0, "safe": 10.0,
                 "trust": 10.0, "avg": 10.0},
                "(critic returned unparseable output — skipped)")


def _needs_rewrite(scores: dict, min_score: float, min_hook: float, min_safe: float,
                   min_trust: float = 8.0) -> bool:
    """Ship-gate: overall quality must clear min_score, AND the hook, the
    compliance/safe axis, and the anti-scam/trust axis each have their own hard
    floor (a weak hook, betting/tipster drift, or capper-shaped content forces a
    rewrite even if the average looks fine)."""
    return (scores["avg"] < min_score
            or scores["hook"] < min_hook
            or scores["safe"] < min_safe
            or scores.get("trust", 10.0) < min_trust)


class ScriptQualityError(RuntimeError):
    """Raised when a script still fails the critic ship-gate after all revisions
    are exhausted. The caller must NOT publish `voiceover` — it never cleared
    the quality floor, it just ran out of rewrite attempts."""

    def __init__(self, scores: dict, critique: str, voiceover: str, revisions: int):
        self.scores = scores
        self.critique = critique
        self.voiceover = voiceover
        self.revisions = revisions
        super().__init__(
            f"Script failed the quality gate after {revisions} revision(s) — "
            f"avg {scores['avg']} | hook {scores['hook']} | safe {scores['safe']} "
            f"| trust {scores.get('trust', 10.0)}. Critique: {critique}"
        )


def generate_journey_script(
    picks: list[Pick],
    milestone: str,
    proof_picks: int = 2,
    min_score: float = 7.0,
    min_hook: float = 8.0,
    min_safe: float = 8.0,
    min_trust: float = 8.0,
    max_revisions: int = 2,
    hook_style: str | None = None,
    cta_mode: str | None = None,
) -> JourneyScript:
    """Generate a first-person Founder's Journey voiceover script, vetted by an LLM critic.

    picks         : today's picks (sorted best-first); top `proof_picks` are woven in as proof.
    milestone     : the founder's daily building update (from the dashboard / CLI).
    min_score     : average critic score (hook/human/flow) required to ship.
    min_hook      : hard floor on the hook axis (strict — the scroll-stopper matters most).
    min_safe      : hard floor on the compliance axis (no betting/tipster language).
    min_trust     : hard floor on the anti-scam axis (must not pattern-match capper content).
    max_revisions : how many rewrite passes to attempt before giving up.
    hook_style    : one of HOOK_STYLES; random if not given (A/B variety across videos).
    cta_mode      : "site" (link CTA, default) or "comment" (comment-gate → DM);
                    falls back to env CTA_MODE.
    """
    if not milestone or not milestone.strip():
        raise ValueError("A daily milestone is required to generate a journey script.")

    cta_mode = _resolve_cta_mode(cta_mode)
    day = project_day()
    proof = picks[:proof_picks]
    picks_block = "\n".join(_pick_line(p) for p in proof) if proof else "- (no qualifying picks today)"
    n_picks = len(proof)
    target_secs = 35
    target_words = round(target_secs * 2.6)
    hook_style = hook_style or random.choice(HOOK_STYLES)

    client = _get_client()
    model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

    writer_prompt = _JOURNEY_WRITER.format(
        day=day,
        milestone=milestone.strip(),
        n_picks=n_picks,
        picks_block=picks_block,
        target_secs=target_secs,
        target_words=target_words,
        hook_style=_hook_direction(hook_style),
        cta_direction=_cta_direction(cta_mode, "today's model output (the pick and its confidence)"),
        caption_rule=_caption_rule(cta_mode),
    )
    resp = call_gemini_with_retry(
        client=client, model=model,
        contents=f"{_JOURNEY_SYSTEM}\n\n{writer_prompt}",
    )
    sections = _parse_sections(resp.text.strip())
    voiceover = sections["voiceover"]
    if not voiceover:
        raise ValueError(f"Writer returned no voiceover. Raw output:\n{resp.text}")

    # ── Critic → rewrite loop ─────────────────────────────────────
    scores, critique = _critique(client, model, voiceover)
    revisions = 0
    while _needs_rewrite(scores, min_score, min_hook, min_safe, min_trust) and revisions < max_revisions:
        print(f"  ✎ Critic: avg {scores['avg']} | hook {scores['hook']} | safe {scores['safe']} "
              f"| trust {scores.get('trust', 10.0)} — rewriting ({revisions + 1}/{max_revisions})")
        print(f"    Critique: {critique}")
        rewrite_prompt = _JOURNEY_REWRITE.format(critique=critique, voiceover=voiceover)
        resp = call_gemini_with_retry(
            client=client, model=model,
            contents=f"{_JOURNEY_SYSTEM}\n\n{rewrite_prompt}",
        )
        voiceover = resp.text.strip()
        scores, critique = _critique(client, model, voiceover)
        revisions += 1

    # ── Hard length gate ──────────────────────────────────────────
    # The critic doesn't reliably enforce duration, so cap it explicitly:
    # condense until the voiceover fits the short-form budget.
    max_words = round(target_words * 1.2)   # ~42s ceiling
    condense_passes = 0
    while len(voiceover.split()) > max_words and condense_passes < 2:
        print(f"  ✂ Voiceover is {len(voiceover.split())} words (> {max_words}). Condensing...")
        resp = call_gemini_with_retry(
            client=client, model=model,
            contents=f"{_JOURNEY_SYSTEM}\n\n"
                     + _JOURNEY_CONDENSE.format(max_words=target_words, voiceover=voiceover),
        )
        voiceover = resp.text.strip()
        condense_passes += 1
    if condense_passes:
        scores, critique = _critique(client, model, voiceover)

    voiceover = _ensure_comment_gate(voiceover, cta_mode,
                                     "what the model's calling today")

    if _needs_rewrite(scores, min_score, min_hook, min_safe, min_trust):
        raise ScriptQualityError(scores, critique, voiceover, revisions)

    return JourneyScript(
        day=day,
        milestone=milestone.strip(),
        voiceover=voiceover,
        caption=sections["caption"],
        hashtags=sections["hashtags"],
        picks=proof,
        critic_score=scores["avg"],
        critic_notes=critique,
        revisions=revisions,
    )


_INSERT_SUGGESTER = """You are planning B-roll for a short build-in-public founder video.
Read the spoken voiceover and pick up to {max_cues} moments where a small on-screen visual
would boost engagement or act as proof:
- "code": he mentions a specific function / feature / bit of code he built
- "screenshot": he mentions the app, dashboard, a result, or something visible on screen
- "diagram": he explains an architecture, flow, or how pieces connect

For each moment, copy an EXACT short phrase (3-6 consecutive words, verbatim) from the
voiceover to anchor the visual to, name the kind, and note briefly what to show.

VOICEOVER:
\"\"\"{voiceover}\"\"\"

Return ONLY a JSON array (no markdown fences). Example:
[{{"phrase":"the function I built today","kind":"code","what":"the day-counter function","secs":4}}]
Only include a moment if a visual genuinely helps. Return 0 to {max_cues} items."""


_TRACK_WRITER = """Write a talk-to-camera voiceover (TikTok/Reels/Short) where the founder shares how his
AI model has actually been performing. This is a "receipts / track record" video — the whole point is
HONEST proof the thing works, framed as data from a system he built. NOT a betting tip, NOT a sales pitch.

THE MODEL'S RECORD (real numbers — use them, don't invent any):
{stats_block}
{winners_block}

HARD LIMIT: under {target_words} words (~{target_secs}s). Shorter is better. Cut anything that sounds written.

HOOK DIRECTION (first line must stop the scroll in 3 seconds): {hook_style}

SHAPE (loose — one continuous, real thought)
- Open with the hook using a real number from the record. NOT a slogan.
- Say plainly how the model's done and over what sample (honesty = trust: it's a sample, not a promise;
  it's wrong sometimes). Sound like a builder proud of his system, not a tipster hyping a bet.
- SAY THE MISSES out loud if the record lists them ("it got one wrong") — this niche is full of scam
  accounts that only show wins; admitting the losses is the single most credible thing in the video.
- Make the claim CHECKABLE somewhere: the record is public on epifanii.com — "don't take my word for
  it" energy, never take-my-word-for-it energy.
- Keep it a TECH/build story — "my model", "the engine", accuracy, edge — never "you should bet".
{cta_direction}

RULES
- VOICEOVER is read aloud by TTS: plain spoken words only. NO emojis, hashtags, stage directions, numbers-as-symbols spelled weird.
- Percentages are fine spoken ("ninety-three percent" or "93 percent"). Be accurate to the numbers above.
- If a rate is at or near 100%, say it as a COUNT ("it's called thirty-three of its last thirty-three") —
  never "100 percent accurate" (a spoken hundred-percent claim reads as a scam, even when true).
{caption_rule}
- HASHTAGS: 4-6 tags (build-in-public + football/AI), space-separated, each starting with #.

Return EXACTLY this format and nothing else:
===VOICEOVER===
<the spoken script>
===CAPTION===
<the caption>
===HASHTAGS===
<the hashtags>"""


def _fmt_pct(x) -> str | None:
    try:
        return f"{round(float(x) * 100)}%"
    except (TypeError, ValueError):
        return None


def _perf_stats_block(perf: dict) -> str:
    """Human-readable, accurate record for the writer prompt."""
    lines = []
    n = perf.get("sample")
    win = perf.get("windowDays")
    hr = _fmt_pct(perf.get("hitRate"))
    if hr and n:
        lines.append(f"- Overall: {hr} hit rate across {n} tracked picks"
                     + (f" over the last {win} days." if win else "."))
        # scams never show losses — surfacing the miss count is our trust move
        try:
            misses = round(n * (1 - float(perf.get("hitRate"))))
            lines.append(f"- Misses in that window: {misses} of the {n}. "
                         "(MENTION this — showing the losses is what separates us from the scam accounts.)")
        except (TypeError, ValueError):
            pass
    edge = _fmt_pct(perf.get("avgEdge"))
    if edge:
        lines.append(f"- Average edge the model flagged on its value picks: +{edge}.")
    for name in ("elite", "high", "strong"):
        t = (perf.get("tiers") or {}).get(name) or {}
        r, tn = _fmt_pct(t.get("rate")), t.get("n")
        # skip statistically-thin tiers ("100% over 1" is misleading + risky)
        if r and isinstance(tn, (int, float)) and tn >= 5:
            lines.append(f"- {name.capitalize()}-tier picks: {r} over {tn}.")
    return "\n".join(lines) if lines else "- (no settled picks yet)"


def _winners_block(winners: list[dict]) -> str:
    if not winners:
        return ""
    rows = []
    for w in winners[:3]:
        mkt = w.get("market", "")
        conf = _fmt_pct(w.get("probability"))
        rows.append(f"- Recent win: {mkt}" + (f" ({conf} model confidence)" if conf else ""))
    return "Recent winning calls (optional colour, don't list all):\n" + "\n".join(rows)


def generate_track_record_script(
    perf: dict,
    winners: list[dict] | None = None,
    hook_style: str | None = None,
    min_score: float = 7.0,
    min_hook: float = 8.0,
    min_safe: float = 8.0,
    min_trust: float = 8.0,
    max_revisions: int = 2,
    cta_mode: str | None = None,
) -> JourneyScript:
    """Generate a "Model Track Record" video script from the portal's performance data.

    perf    : dict from prediction_fetcher.fetch_performance().
    winners : optional list from fetch_recent_winners() for colour.
    cta_mode: "site" (link CTA, default) or "comment" (comment-gate → DM).
    Same critic/hook/safe gates as the journey script; reuses the JourneyScript shape.
    """
    if not perf or not perf.get("sample"):
        raise ValueError("No performance data (empty sample) to build a track-record script.")

    cta_mode = _resolve_cta_mode(cta_mode)
    target_secs = 30
    target_words = round(target_secs * 2.6)
    hook_style = hook_style or random.choice(HOOK_STYLES)

    client = _get_client()
    model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

    writer_prompt = _TRACK_WRITER.format(
        stats_block=_perf_stats_block(perf),
        winners_block=_winners_block(winners or []),
        target_secs=target_secs,
        target_words=target_words,
        hook_style=_hook_direction(hook_style),
        cta_direction=_cta_direction(cta_mode, "the model's current calls and its full record"),
        caption_rule=_caption_rule(cta_mode),
    )
    resp = call_gemini_with_retry(
        client=client, model=model,
        contents=f"{_JOURNEY_SYSTEM}\n\n{writer_prompt}",
    )
    sections = _parse_sections(resp.text.strip())
    voiceover = sections["voiceover"]
    if not voiceover:
        raise ValueError(f"Writer returned no voiceover. Raw output:\n{resp.text}")

    scores, critique = _critique(client, model, voiceover)
    revisions = 0
    while _needs_rewrite(scores, min_score, min_hook, min_safe, min_trust) and revisions < max_revisions:
        print(f"  ✎ Critic: avg {scores['avg']} | hook {scores['hook']} | safe {scores['safe']} "
              f"| trust {scores.get('trust', 10.0)} — rewriting ({revisions + 1}/{max_revisions})")
        print(f"    Critique: {critique}")
        rewrite_prompt = _JOURNEY_REWRITE.format(critique=critique, voiceover=voiceover)
        resp = call_gemini_with_retry(
            client=client, model=model,
            contents=f"{_JOURNEY_SYSTEM}\n\n{rewrite_prompt}",
        )
        voiceover = resp.text.strip()
        scores, critique = _critique(client, model, voiceover)
        revisions += 1

    max_words = round(target_words * 1.2)
    passes = 0
    while len(voiceover.split()) > max_words and passes < 2:
        print(f"  ✂ Voiceover is {len(voiceover.split())} words (> {max_words}). Condensing...")
        resp = call_gemini_with_retry(
            client=client, model=model,
            contents=f"{_JOURNEY_SYSTEM}\n\n"
                     + _JOURNEY_CONDENSE.format(max_words=target_words, voiceover=voiceover),
        )
        voiceover = resp.text.strip()
        passes += 1
    if passes:
        scores, critique = _critique(client, model, voiceover)

    voiceover = _ensure_comment_gate(voiceover, cta_mode,
                                     "the model's current calls and its record")

    if _needs_rewrite(scores, min_score, min_hook, min_safe, min_trust):
        raise ScriptQualityError(scores, critique, voiceover, revisions)

    return JourneyScript(
        day=project_day(),
        milestone="model track record",
        voiceover=voiceover,
        caption=sections["caption"],
        hashtags=sections["hashtags"],
        picks=[],
        critic_score=scores["avg"],
        critic_notes=critique,
        revisions=revisions,
    )


_PLATFORM_CAPTIONS = """Rewrite this video's caption for each platform. Same message, native to each.
Keep the compliance rule: it's a build-in-public / AI story — never betting advice, no "bet/lock/guaranteed".
{cta_note}

VOICEOVER (context): \"\"\"{voiceover}\"\"\"
BASE CAPTION: {caption}

Per platform:
- tiktok: punchy, lowercase-ish, 1 line + a few tags. Casual.
- instagram: 1-2 lines, a little more polished, 3-5 tags.
- youtube: a Shorts title-style first line + one sentence; 3-5 tags.
- x: a build-in-public tweet voice, conversational, 1-2 tags, under 260 chars.

Return ONLY a JSON object (no fences):
{{"tiktok":{{"caption":"...","hashtags":"#a #b"}},"instagram":{{"caption":"...","hashtags":"#a #b"}},"youtube":{{"caption":"...","hashtags":"#a #b"}},"x":{{"caption":"...","hashtags":"#a #b"}}}}"""

_CAPTIONS_CTA_SITE = "Always include epifanii.com."

_CAPTIONS_CTA_COMMENT = (
    'CTA rules: tiktok and instagram captions MUST carry the comment-gate '
    '("comment {word}" → DM with the model\'s output) and NO link (the DM is the delivery). '
    "youtube and x have no comment-to-DM flow, so those two include epifanii.com instead of the gate."
)


def platform_captions(script: JourneyScript, cta_mode: str | None = None) -> dict:
    """Per-platform caption + hashtag variants from one script.

    cta_mode "comment" keeps the comment-gate on TikTok/IG (no link) and swaps in the
    epifanii.com link on YouTube/X, where comment→DM doesn't exist.
    Returns {"tiktok","instagram","youtube","x": {"caption","hashtags"}}. Best-effort:
    on any failure, falls back to the script's base caption/hashtags for every platform.
    """
    base = {"caption": script.caption, "hashtags": script.hashtags}
    fallback = {p: dict(base) for p in ("tiktok", "instagram", "youtube", "x")}
    cta_note = (_CAPTIONS_CTA_COMMENT.format(word=COMMENT_GATE_WORD)
                if _resolve_cta_mode(cta_mode) == "comment" else _CAPTIONS_CTA_SITE)
    try:
        client = _get_client()
        model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
        prompt = _PLATFORM_CAPTIONS.format(voiceover=script.voiceover, caption=script.caption,
                                           cta_note=cta_note)
        resp = call_gemini_with_retry(client=client, model=model, contents=prompt)
        raw = re.sub(r"^```(?:json)?|```$", "", resp.text.strip(), flags=re.MULTILINE).strip()
        data = json.loads(raw)
    except Exception:
        return fallback
    out = {}
    for p in ("tiktok", "instagram", "youtube", "x"):
        v = data.get(p) if isinstance(data, dict) else None
        if isinstance(v, dict) and str(v.get("caption", "")).strip():
            out[p] = {"caption": str(v.get("caption", "")).strip(),
                      "hashtags": str(v.get("hashtags", script.hashtags)).strip()}
        else:
            out[p] = dict(base)
    return out


def suggest_inserts(voiceover: str, max_cues: int = 4) -> list[dict]:
    """Ask the LLM where visual inserts (code cards / screenshots / diagrams) would help.

    Returns a list of cue dicts: {"phrase","kind","what","secs"}. `phrase` is copied
    from the voiceover so it can be anchored to the caption timings; the founder still
    supplies the actual code/image. Returns [] on any failure (best-effort).
    """
    if not voiceover or not voiceover.strip():
        return []
    client = _get_client()
    model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
    prompt = _INSERT_SUGGESTER.format(voiceover=voiceover.strip(), max_cues=max_cues)
    try:
        resp = call_gemini_with_retry(client=client, model=model, contents=prompt)
        raw = re.sub(r"^```(?:json)?|```$", "", resp.text.strip(), flags=re.MULTILINE).strip()
        data = json.loads(raw)
    except Exception:
        return []
    cues = []
    for item in data if isinstance(data, list) else []:
        phrase = str(item.get("phrase", "")).strip()
        if not phrase:
            continue
        kind = str(item.get("kind", "code")).strip().lower()
        if kind not in ("code", "screenshot", "diagram"):
            kind = "code"
        try:
            secs = float(item.get("secs", 3.0))
        except (TypeError, ValueError):
            secs = 3.0
        cues.append({"phrase": phrase, "kind": kind,
                     "what": str(item.get("what", "")).strip(), "secs": secs})
    return cues[:max_cues]
