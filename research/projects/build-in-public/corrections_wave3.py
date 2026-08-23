#!/usr/bin/env python3
"""Claude vision-pass corrections, wave 3 (2026-07-13): @thedankoe + @conniecodes.

Same rules as the previous correction files. Note: two conniecodes posts are
paid partnerships with HIDDEN like counts — their engagement is unreliable, so
they carry fresh=True purely to keep them out of the auto-punish pool.
"""
import json
from pathlib import Path

DATA = Path(__file__).parent / "raw-posts.json"

C = {
    # ── thedankoe (solopreneur lane) ──────────────────────────────
    "DaWJR-nEriA": dict(
        author="thedankoe", likes="29.9K", commentsCount="84", views=None,
        caption="You weren't meant to repeat the same day for 40-60 years.",
        hook="If you don't wake up excited and go to bed tired...",
        slideHook=True, style="STAKES", date="2026-07-03", fresh=False),
    "DYsDqo3q7WU": dict(
        author="thedankoe", likes="19.1K", commentsCount="92", views=None,
        caption="The most important decision of your life",
        hook="If you don't create a routine, you will be assigned one. If you don't find a purpose, you will be assigned one.",
        slideHook=True, style="STAKES", date="2026-05-23", fresh=False),
    "DXuLJqaFPyH": dict(
        author="thedankoe", likes="19K", commentsCount="103", views=None,
        caption="3 ideas",
        hook="If you want a rare life, you have to be delusional.",
        slideHook=True, style="CURIOSITY GAP", date="2026-04-29", fresh=False),
    "DYzmPW_K5D5": dict(
        author="thedankoe", likes="11.2K", commentsCount="84", views=None,
        caption="You have enough time",
        hook="The two to four hours you spend scrolling each day — 1,460 hours each year — is more than enough time to write a book, build a business, or get in shape.",
        style="STAKES", date="2026-05-26", fresh=False),
    "Daae91EqR7J": dict(
        author="thedankoe", likes="10.9K", commentsCount="74", views=None,
        caption="How to change your life in 1 day. If you want to talk about your interests online and build an audience, the creator bootcamp starts in 3 days. Link in bio",
        hook="The fastest way to change your life is to rip yourself out of your physical and digital environment.",
        style="CURIOSITY GAP", date="2026-07-06", fresh=False),
    "DaJYqSdhELn": dict(
        author="thedankoe", likes="7.4K", commentsCount="73", views=None,
        caption="Funnily enough, these have everything to do with making money.",
        hook="Skills that have nothing to do with money but are worth dedicating an immense amount of practice to: charisma, metacognition, critical thinking, sitting with discomfort.",
        slideHook=True, style="CURIOSITY GAP", date="2026-06-29", fresh=False),
    "Dad0qiGks3i": dict(
        author="thedankoe", likes="4.5K", commentsCount="41", views=None,
        caption="Writing changed my life. It started because I saw people on social media posting about my interests and thinking, “Hey, I could do that too.” And now it's turned into a few million followers across different platforms.",
        hook="If you don't know what to learn, start writing.",
        slideHook=True, style="ANY", date="2026-07-07", fresh=False),
    "Dak5eeiqAfM": dict(
        author="thedankoe", likes="3.4K", commentsCount="39", views=None,
        caption="Goals aren't just some self help non sense they're what determine how you perceive opportunity and act within the world",
        hook="If you don't have a goal so meaningful it makes other people's opinions irrelevant, you will lose control of your life.",
        style="STAKES", date="2026-07-10", fresh=False),

    # ── conniecodes (vibecoding lane) ─────────────────────────────
    "DYqJoeVvI8c": dict(
        author="conniecodes", likes="90.1K", commentsCount="664", views=None,
        caption="small vibe coded project 🌸 Inspired by tom boutin's quakpit on x ✨",
        hook="POV: you make a macbook app that connects to your google cal so that a little airplane flies through your screen 5 minutes before all of your meetings",
        slideHook=True, style="RESULT/FLEX", date="2026-05-23", fresh=False),
    "DZD_cTQPCWL": dict(
        author="conniecodes", likes="88.1K", commentsCount="315", views=None,
        caption="What is in my bag software eng edition (all are necessities) inspired by @javiercunat",
        hook="Backpack of a performative software engineer",
        slideHook=True, style="ANY", date="2026-06-02", fresh=False),
    "DTQqr0EkZ0S": dict(
        author="conniecodes", likes="13.9K", commentsCount="98", views=None,
        caption="ONE minute HOW TO on how to create your first API. Python + FastAPI. Super beginner friendly tutorial for your coding journey.",
        hook="I'm going to create an API with two different endpoints, it's going to take under a minute, and I'm going to show you exactly how.",
        style="RESULT/FLEX", date="2026-01-08", fresh=False),
    "DZaZX-PxkxH": dict(
        author="conniecodes", likes="11.6K", commentsCount="27", views=None,
        caption="realistic what I carry in a day as a software engineer (as a girly pop and when I don't feel like using a backpack)",
        hook="Bag of a performative girly pop software engineer",
        slideHook=True, style="ANY", date="2026-06-11", fresh=False),
    "DaLlWT_vhZc": dict(
        author="conniecodes", likes="9.8K", commentsCount="40", views=None,
        caption="Huge fan of these two books. Have you read them or heard of them? One of them is fairly new and helped a lot with my recent job search",
        hook="Two books I'm reading as a senior software engineer — and you should too.",
        style="ANY", date="2026-06-29", fresh=False),
    "DZp6jouRyf8": dict(
        author="conniecodes", likes="274", commentsCount="3", views=None,
        caption="all great sites take time to build. This is part 1 of me building my portfolio website into a beautiful, whimsical, magical site that reflects me and everything that I love. You can check it out at conniexu.com",
        hook="Software should be personal. So let's redo my portfolio.",
        style="ANY", date="2026-06-17", fresh=False),
    # paid partnerships with HIDDEN like counts — engagement unreliable,
    # fresh=True only to keep them out of the auto-punish pool
    "DZxjyURRaG9": dict(
        author="conniecodes", likes="1", commentsCount="1", views=None,
        caption="I love using Figma agent to level up my wireframes. (paid partnership) #ad",
        hook="This new Figma agent has changed my design process forever.",
        style="ANY", date="2026-06-19", fresh=True),
    "DZLLhAMPMJm": dict(
        author="conniecodes", likes="1", commentsCount="14", views=None,
        caption="Building a coffee shop finder website using @repl.it. (paid partnership)",
        hook="I'm building a website that will allow my friends and I to create detailed reviews on every coffee shop we go to in New York City.",
        style="ANY", date="2026-06-04", fresh=True),
}


def num(v):
    if v is None:
        return 0
    s = str(v).replace(",", "").strip().upper()
    mult = 1
    if s.endswith("K"):
        mult, s = 1_000, s[:-1]
    elif s.endswith("M"):
        mult, s = 1_000_000, s[:-1]
    try:
        return int(float(s) * mult)
    except ValueError:
        return 0


data = json.loads(DATA.read_text())
seen = set()
for p in data["posts"]:
    c = C.get(p["postId"])
    if not c:
        continue
    seen.add(p["postId"])
    p.update(c)
    p["engagement"] = max(num(c.get("likes")), num(c.get("views"))) + num(c.get("commentsCount"))

missing = set(C) - seen
if missing:
    print(f"!! corrections without a post: {missing}")

data["posts"].sort(key=lambda p: -p.get("engagement", 0))
DATA.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
print(f"Corrected {len(seen)} wave-3 posts; dataset {len(data['posts'])} total.")
