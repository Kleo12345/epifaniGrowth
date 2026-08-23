#!/usr/bin/env python3
"""Build the engine's hook swipe file from research project data.

Reads one or more (Claude-corrected) raw-posts.json files, extracts each
post's hook, classifies it into one of the engine's HOOK_STYLES, and writes
engine/assets/hooks_swipe_file.json — which core/script_generator.py picks up
automatically as few-shot examples for the writer and a punish-list for the
critic.

Usage:
  python3 scripts/build_swipe_file.py <project> [<project> ...]
        [--top 20] [--out ../engine/assets/hooks_swipe_file.json]

Posts may carry a manual "style" field (set during the Claude analysis step) —
that always wins over the keyword heuristic here.
"""
import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

RESEARCH_DIR = Path(__file__).resolve().parent.parent
DEFAULT_OUT = RESEARCH_DIR.parent / "engine" / "assets" / "hooks_swipe_file.json"

# Must match the style names in engine/core/script_generator.py HOOK_STYLES.
STYLE_RULES = [
    ("CONFESSION", re.compile(
        r"\bi (was wrong|messed|screwed|failed|broke|shipped a bug|made a (huge |big )?mistake|"
        r"lost|wasted|regret|shouldn'?t have|almost (quit|gave up))\b", re.I)),
    ("STAKES", re.compile(
        r"\b(if (this|it|i) .{0,30}(fail|miss|lose|flop)|on the line|last chance|"
        r"or i (lose|quit|shut)|\$\d|risk(ing)? (it all|everything))\b", re.I)),
    ("RESULT/FLEX", re.compile(
        r"\b(just (hit|crossed|passed|closed|reached|made)|went from .{0,20} to|"
        r"\d+ (users|followers|downloads|sales|mrr)|best (week|month|day)|"
        r"made \$|\d{2,}%|in \d+ (days|weeks|months) i)\b", re.I)),
    ("STRUGGLE", re.compile(
        r"\b(struggl|frustrat|stuck|still (can'?t|doesn'?t|won'?t)|"
        r"\d+ (hours?|days?) (in|later|of)|hardest|annoying|nightmare|"
        r"nobody tells you how hard)\b", re.I)),
    ("CURIOSITY GAP", re.compile(
        r"\b(nobody (talks about|tells you)|no one|the (one|only) (thing|stat|reason)|"
        r"here'?s (what|why|how)|the secret|what i found|you('?re| are) (probably )?doing .{0,20} wrong|"
        r"i found (a|the|one))\b", re.I)),
]


def classify(hook: str) -> str:
    for style, rx in STYLE_RULES:
        if rx.search(hook):
            return style
    if hook.rstrip().endswith("?"):
        return "CURIOSITY GAP"
    return "ANY"


def engagement(post: dict) -> int:
    def num(v):
        if isinstance(v, (int, float)):
            return int(v)
        m = re.match(r"([\d,.]+)\s*([KkMm])?", str(v or "").replace(",", ""))
        if not m:
            return 0
        n = float(m.group(1))
        if m.group(2) and m.group(2) in "Kk":
            n *= 1_000
        if m.group(2) and m.group(2) in "Mm":
            n *= 1_000_000
        return int(n)

    e = num(post.get("engagement"))
    return e if e > 0 else max(num(post.get("likes")), num(post.get("views"))) + num(post.get("commentsCount"))


def first_sentence(text: str) -> str:
    text = (text or "").strip()
    if not text:
        return ""
    m = re.match(r".*?[.!?](?=\s|$)", text)
    return (m.group(0) if m else text.splitlines()[0]).strip()[:200]


def hook_for(post: dict, transcripts_dir: Path) -> str:
    if post.get("hook"):
        return str(post["hook"]).strip()[:200]
    txt = transcripts_dir / f"{post.get('postId', '')}.txt"
    if post.get("type") == "reel" and txt.exists():
        return first_sentence(txt.read_text())
    return first_sentence(post.get("caption", ""))


def main():
    parser = argparse.ArgumentParser(description="Build hooks_swipe_file.json for the engine")
    parser.add_argument("projects", nargs="+", help="project name(s) under research/projects/")
    parser.add_argument("--top", type=int, default=20, help="how many winning hooks to keep (default 20)")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help=f"output path (default {DEFAULT_OUT})")
    args = parser.parse_args()

    all_posts = []
    for name in args.projects:
        data_file = RESEARCH_DIR / "projects" / name / "raw-posts.json"
        if not data_file.exists():
            raise SystemExit(f"raw-posts.json not found for project '{name}' ({data_file})")
        data = json.loads(data_file.read_text())
        tdir = RESEARCH_DIR / "projects" / name / "transcripts"
        for p in data.get("posts", []):
            hook = hook_for(p, tdir)
            if not hook or len(hook) < 12:
                continue
            all_posts.append({
                "hook": hook,
                "style": (p.get("style") or classify(hook)).upper(),
                "engagement": engagement(p),
                "type": p.get("type", ""),
                "author": p.get("author", ""),
                "source": f"{name}/{p.get('source', '')}",
                "fresh": bool(p.get("fresh")),
                # analyst overrides set during the Claude vision pass:
                # winner=True force-includes (e.g. a great hook on a too-fresh
                # post), punish=True force-excludes and joins the punish list.
                "winner": bool(p.get("winner")),
                "punish": bool(p.get("punish")),
            })

    if not all_posts:
        raise SystemExit("No usable hooks found — did the scrape + Claude analysis step run?")

    # de-dup on hook text, keep the higher-engagement copy
    seen = {}
    for h in sorted(all_posts, key=lambda x: -x["engagement"]):
        key = h["hook"].lower()
        if key not in seen:
            seen[key] = h
    ranked = list(seen.values())

    # Winners: analyst-forced picks first, then top N by engagement — but never
    # from the bottom quartile (a large --top on a small scrape must not promote
    # junk hooks into the few-shots) and never a punish-flagged post.
    cutoff = ranked[int(len(ranked) * 0.75)]["engagement"] if len(ranked) >= 8 else 0
    forced = [h for h in ranked if h["winner"] and not h["punish"]]
    auto = [h for h in ranked
            if h["engagement"] > cutoff and not h["punish"] and h not in forced]
    # forced picks always survive the --top cap; auto picks fill the rest
    winners = sorted(forced + auto[: max(args.top - len(forced), 0)],
                     key=lambda h: -h["engagement"])

    # Punish list: analyst-flagged posts first, filled up from the bottom
    # engagement quartile. Posts flagged "fresh" (scraped within ~48h of
    # posting) are never auto-punished — their low engagement reflects recency,
    # not a bad hook.
    losers = [h["hook"] for h in ranked if h["punish"]]
    losers += [h["hook"] for h in ranked
               if h["engagement"] <= cutoff and not h["fresh"]
               and not h["punish"] and not h["winner"]]
    losers = losers[:6]
    winners = [{k: v for k, v in h.items() if k not in ("fresh", "winner", "punish")}
               for h in winners]

    out = {
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "projects": args.projects,
        "hooks": winners,
        "punish_patterns": losers,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n")

    by_style = {}
    for h in winners:
        by_style[h["style"]] = by_style.get(h["style"], 0) + 1
    print(f"Swipe file written: {args.out}")
    print(f"  winning hooks: {len(winners)}  (styles: {by_style})")
    print(f"  punish patterns: {len(losers)}")


if __name__ == "__main__":
    main()
