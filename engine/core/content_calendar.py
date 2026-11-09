"""
Epifani Founder's Journey — Plan A+ content calendar (44 days).

Transcribed verbatim from the "Epifani — 30-Day Build Calendar" artifact
(Plan A+ tab: https://claude.ai/artifact/U82wGL5s9pNcKH1ZnR9qT6), which is
Plan A's Foundations -> Quant Leap -> Present backbone with two extra
interlude weeks woven in so the story runs 44 days without repeating a beat.

Each entry:
  fam   : "human" | "build" | "tech" | "proof" — content family
  hook  : CONFESSION | CURIOSITY | STAKES | TRUST | STRUGGLE | FLEX
  depth : 1-5, how technical
  topic : what today's video is about
  note  : optional extra direction
  kind  : "journey" (default, the day's build/topic) or "record" (the
          weekly track-record check-in — pulls real performance data
          instead of a milestone topic)
"""

_RECORD_TOPIC = "Weekly record check-in"


def _day(day: int, fam: str, hook: str, depth: int, topic: str, note: str | None = None,
         secs: int | None = None) -> dict:
    """secs: target voiceover length for this day (None = the generator's default)."""
    return {
        "day": day,
        "fam": fam,
        "hook": hook,
        "depth": depth,
        "topic": topic,
        "note": note,
        "kind": "record" if topic == _RECORD_TOPIC else "journey",
        "secs": secs,
    }


_ENTRIES = [
    # Week 1 — shared reveal week
    _day(1, "human", "CONFESSION", 1,
         "\"I've been building this AI prediction platform for months without saying a word. "
         "Here's the honest record.\"",
         "The premise. Pinned / start-here video, so it runs longer. Right after the "
         "confession, properly explain what Epifani IS for a first-time viewer, in plain "
         "words: an AI that predicts football matches across many leagues every day; every "
         "prediction is published with its confidence BEFORE kickoff; each one is graded "
         "automatically against the real result and the market's closing odds, and nothing "
         "is deleted or curated after the fact; the daily top predictions are free on "
         "epifanii.com. Only then show today's predictions as proof, briefly.",
         secs=55),
    _day(2, "human", "CURIOSITY", 1,
         "Why Epifani publishes every single prediction, including the misses, when most "
         "prediction accounts only ever show their wins",
         "Day 1 already explained what Epifani is — don't repeat it, one line of context at "
         "most. This is the why: a record you can only trust if nothing is hidden. Speak to "
         "the stance, not a backstory — don't invent personal anecdotes, dates or numbers, "
         "and never name or attack other accounts."),
    _day(3, "proof", "TRUST", 1,
         "Why it's built to be checked — every pick is graded automatically, against the "
         "market's own closing price"),
    _day(4, "human", "CONFESSION", 1,
         "A duplicate-ID bug where one bet's result was quietly overwriting another's"),
    _day(5, "tech", "STAKES", 2,
         "The model watches its own closing-line performance and flags its own risky "
         "bet-types automatically"),
    _day(6, "human", "CONFESSION", 2,
         "The multi-day fight to make \"Belgium\" in one data source match \"Belgium\" in another"),
    _day(7, "proof", "CURIOSITY", 1, "Where this goes next — first comment-gate invite"),

    # Week 2 — The Foundations (early automation)
    _day(8, "human", "CONFESSION", 1,
         "Built a whole separate module just for the World Cup. A week and a half later, "
         "ripped it out — it didn't need to be special"),
    _day(9, "build", "STRUGGLE", 2,
         "Automating the whole data pipeline — a scheduled job that updates every league "
         "without me touching it"),
    _day(10, "human", "CONFESSION", 2,
         "Tried to clear months of accumulated old models out of the database. Gave up "
         "halfway and left it"),
    _day(11, "tech", "CURIOSITY", 2,
         "What an \"ensemble\" model actually is — many specialists voting, not one guess"),
    _day(12, "build", "STRUGGLE", 2,
         "A real money bug: some bets were losing the stake instead of returning it when "
         "they should push"),
    _day(13, "human", "STRUGGLE", 1, "Whatever's actually annoying about the build this week"),
    _day(14, "proof", "FLEX", 1, _RECORD_TOPIC, "+ reply to a comment"),

    # Week 3 — The Proof, Sideways (interlude: trust mechanics + two honest bugs)
    _day(15, "proof", "CURIOSITY", 1, "The losses, out loud — showing the picks that missed"),
    _day(16, "proof", "CURIOSITY", 2,
         "The drawdown gate — a rule that protects the whole system from itself in a bad streak"),
    _day(17, "proof", "CURIOSITY", 2,
         "Why some bet types get a trust warning instead of an outright ban"),
    _day(18, "proof", "TRUST", 1, "Why none of this is ever framed as betting advice"),
    _day(19, "human", "CONFESSION", 2,
         "The ELO data fetcher used to hang forever on a team it didn't recognize"),
    _day(20, "human", "CONFESSION", 3,
         "Found out my own backtest numbers were wrong — missing probability columns for "
         "four bet types, for who knows how long",
         note="Keep the topic's own wording. Say the backtest was missing probability columns; "
              "do not name the bet types, give dates, or say which component had the bug."),
    _day(21, "proof", "FLEX", 1, _RECORD_TOPIC, "+ reply to a comment"),

    # Week 4 — The Quant Leap (technical dial turns up here)
    _day(22, "tech", "CURIOSITY", 3,
         "What \"Kelly Criterion\" is — how a model could size a position by how sure it is, "
         "not a flat amount",
         note="Kelly fraction = (p x odds - 1) / (odds - 1) with decimal odds, where p is the "
              "model's probability. This is not the 'edge' the site publishes (that one is "
              "p - 1/odds). A made-up illustration only, and say it is made up: 55% at odds 2.0 "
              "gives 10%. Explain the intuition as a modelling idea, never as betting advice: "
              "no 'you should', no bankroll talk."),
    _day(23, "build", "STAKES", 3,
         "Built a portfolio optimizer that sizes six strategies against each other at once",
         note="Explain the idea: sizing several strategies together instead of as six separate "
              "bets. Do not invent the method, the strategies' names, weights, correlation "
              "figures or results."),
    _day(24, "tech", "CURIOSITY", 3,
         "What \"walk-forward optimization\" is — testing a strategy like you'd have "
         "actually lived it",
         note="Contrast it with one backtest over all history. Show the rolling window: train "
              "on a stretch, test on the next one, roll forward. If you use example months "
              "(train Jan-Mar, test Apr), say they are only an example. No maths notation."),
    _day(25, "human", "CONFESSION", 4,
         "The optimizer started picking suspiciously lucky outliers instead of real edges. "
         "Had to rein it in",
         note="Say only that it was reined in, as the topic says; name no specific guardrail. "
              "Do not invent dates, trade counts, weight limits or metric names."),
    _day(26, "tech", "STAKES", 4,
         "Teaching the model to be honest about its own confidence — calibration",
         note="Explain calibration plainly: when the model says 55%, does it win about 55% of "
              "the time? Group picks into probability bands and compare. Quote no results; the "
              "check is being built. If the site's average edge comes up, say it averages only "
              "the picks where the model saw a positive edge, so it cannot be compared with the "
              "overall return. Never promise calibration will fix the record."),
    _day(27, "human", "CONFESSION", 2,
         "\"Reverted a big problem\" — the day something broke badly enough to just undo everything",
         note="Do not invent what broke, how long it took or what it cost."),
    _day(28, "proof", "FLEX", 1, _RECORD_TOPIC, "+ reply to a comment"),

    # Week 5 — The Machinery, Up Close (interlude: the self-monitoring system)
    _day(29, "tech", "CURIOSITY", 3,
         "AutoML — letting the computer search for its own best settings instead of me guessing",
         note="Do not name AutoML tools or quote results."),
    _day(30, "tech", "CURIOSITY", 3,
         "Specialist stacking — dozens of models each focused on one bet type, blended by "
         "a referee model",
         note="Do not invent model counts or bet-type names."),
    _day(31, "build", "STAKES", 3,
         "Built a health system that watches the model itself and can trigger its own retraining",
         note="Do not name specific health metrics or retraining triggers."),
    _day(32, "human", "CONFESSION", 2,
         "A real commit message from that week, word for word: \"I think I fixed the "
         "autonomous health system, but we have to test it first\"",
         note="Quote only this commit message; do not invent other messages or the outcome."),
    _day(33, "human", "CONFESSION", 2,
         "Shipped a fix that made things worse. Reverted it, guarded against it differently instead",
         note="Do not name the specific fix or what it broke."),
    _day(34, "build", "CURIOSITY", 2,
         "Built a 3D map of how my own codebase connects, just to understand my own system",
         note="Do not name the visualisation tool or quote graph numbers."),
    _day(35, "proof", "FLEX", 1, _RECORD_TOPIC, "+ reply to a comment"),

    # Week 6 — The Present (forward-looking, closes the arc)
    _day(36, "tech", "CURIOSITY", 3,
         "What \"closing line value\" is, and why it matters more than a single win or loss",
         note="Explain the idea; claim no closing-line figure for the model."),
    _day(37, "proof", "FLEX", 2,
         "Built a scoreboard that shows what's actually working, market by market",
         note="Show the idea of the scoreboard; quote no market's results or numbers."),
    _day(38, "build", "STRUGGLE", 1, "Whatever's actually true that day",
         note="Keep it honest and general; do not invent a specific struggle."),
    _day(39, "proof", "FLEX", 1, _RECORD_TOPIC),
    _day(40, "proof", "CURIOSITY", 1, "Answering the most-asked question so far",
         note="Do not invent a question or claim how often it was asked."),
    _day(41, "human", "CONFESSION", 2, "Whatever's actually true that day",
         note="Keep it honest and general; do not invent a specific confession."),
    _day(42, "tech", "CURIOSITY", 2, "A tease of what's next for the model",
         note="Promise no specific feature, result or date."),
    _day(43, "proof", "FLEX", 1, _RECORD_TOPIC),
    _day(44, "build", "FLEX", 1,
         "Six weeks of talking about it publicly — what actually changed",
         note="Quote no follower counts or record numbers."),
]

PLAN_A_PLUS: dict[int, dict] = {e["day"]: e for e in _ENTRIES}
CALENDAR_LENGTH = len(PLAN_A_PLUS)


def calendar_entry(day: int) -> dict | None:
    """The Plan A+ entry for `day` (1-44), or None once the calendar runs out."""
    return PLAN_A_PLUS.get(day)
