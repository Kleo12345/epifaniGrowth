#!/usr/bin/env python3
"""Claude vision-pass corrections for the competitor-profile scrape (2026-07-13).

Same rules as corrections.py: values read off post screenshots, hooks from
spoken transcript first sentence / slide text / caption fallback. ASR garble
lightly repaired against the on-video text ("The launch has dropped" →
"Anthropic just dropped"). Engagement recomputed as max(likes,views)+comments.
"""
import json
from pathlib import Path

DATA = Path(__file__).parent / "raw-posts.json"

C = {
    # ── liambuilds.ai ─────────────────────────────────────────────
    "DR73YoFj1zt": dict(
        author="liambuilds.ai", likes="55.8K", commentsCount="227", views=None,
        caption="Two builders. Two completely different stacks. One uses only free tools. The other pays for every premium upgrade. Same goal. Different paths. The real question: does paid actually make you better?",
        hook="I pay for the highest tier GPT at 120 dollars a month because I need reliability and the best reasoning.",
        style="CURIOSITY GAP", date="2025-12-06", fresh=False),
    "DTBD9xRkRCG": dict(
        author="liambuilds.ai", likes="27.6K", commentsCount="44.4K", views=None,
        caption="I forced ChatGPT to audit itself. What it revealed was disturbing. Location. Device. Behavior patterns. Even a psychological profile built from how I type. You have a shadow profile too - you just can't see it. Comment “prompt” and I'll send you the audit code.",
        hook="I just forced ChatGPT to run a forensic audit on itself, and what it found was actually kind of terrifying.",
        style="CURIOSITY GAP", date="2026-01-02", fresh=False),
    "DSD-lXJjM33": dict(
        author="liambuilds.ai", likes="10.7K", commentsCount="151", views=None,
        caption="Most people are stuck at level one and don't even know it. Here's exactly how to upgrade your workflow.",
        hook="Paying ChatGPT 20 dollars a month is bad. Paying the OpenAI API for only the tokens you use is good. Running DeepSeek locally on your own computer is excellent.",
        style="CURIOSITY GAP", date="2025-12-10", fresh=False),
    "DaYxEXshrCa": dict(
        author="liambuilds.ai", likes="1.8K", commentsCount="113", views=None,
        caption="Building my own AI machine. Home hardware runs the future. Comment “$” and I'll DM you the exact build 👇",
        hook="BUILDING MY AT HOME AI MACHINE.",
        slideHook=True, style="RESULT/FLEX", date="2026-07-05", fresh=False),
    "DaWBAuVhr-O": dict(
        author="liambuilds.ai", likes="189", commentsCount="40", views=None,
        caption="Claude can now run Higgsfield for you, and this changes how I make content. Comment “MCP” and I'll DM you the link to get started.",
        hook="Anthropic just dropped the most powerful AI model on the planet, again, and it's completely insane.",
        style="CURIOSITY GAP", date="2026-07-03", fresh=False),
    "DaRUMaxM8ui": dict(
        author="liambuilds.ai", likes="177", commentsCount="45", views=None,
        caption="Higgsfield + Claude = what agencies charge $10K for. Claude writes the scripts. Higgsfield generates the B-roll. I film the talking head. The brand pays me direct. No agency in the middle. Comment “$” and I'll DM you the exact workflow 👇",
        hook="WHAT AGENCIES CHARGE $10K FOR",
        slideHook=True, style="RESULT/FLEX", date="2026-07-02", fresh=False),
    "DaUBWHSsOUi": dict(
        author="liambuilds.ai", likes="208", commentsCount="7", views=None,
        caption="Claude did my video work today while I did everything else. This is a real timelapse from today's work session. No editor open. No render queue. I just review what comes out. Comment “MCP” and I'll DM you the link.",
        hook="Claude did my video work today while I did everything else.",
        style="RESULT/FLEX", date="2026-07-03", fresh=False),
    "Dadjn29hwZ9": dict(
        author="liambuilds.ai", likes="116", commentsCount="29", views=None,
        caption="Claude's most capable model, Fable 5, is back online — and I connected it to @higgsfield.ai through MCP to see what one sentence could actually build.",
        hook="Anthropic's most powerful model is back. Fable 5 is the one the government said was too powerful to be released.",
        style="CURIOSITY GAP", date="2026-07-07", fresh=False),

    # ── adam.badar ────────────────────────────────────────────────
    "DZNbSveSI7F": dict(
        author="adam.badar", likes="6.9K", commentsCount="26", views=None,
        caption="My bag as a startup founder 💻 Inspired by @conniecodes #founder #buildinpublic #fyp #tech #claude",
        hook="Backpack of a Performative Startup Founder",
        slideHook=True, style="ANY", date="2026-06-08", fresh=False),
    "DZfx_15SSRT": dict(
        author="adam.badar", likes="1.5K", commentsCount="41", views=None,
        caption="Do you know all of these? 🧐 I'm building my startup in public. follow @adam.badar if you wanna see my journey.",
        hook="Let's see if you actually know about startups: MVP, ICP, Pre-Seed, Series A, Safe, Bridge Round...",
        style="CURIOSITY GAP", date="2026-06-15", fresh=False),
    "DaJag99ybnF": dict(
        author="adam.badar", likes="810", commentsCount="11", views=None,
        caption="Do you know all of these? 🧐 I'm building my startup in public.",
        hook="Let's see if you actually know startup marketing: CAC, LTV, conversion rate, top of the funnel...",
        style="CURIOSITY GAP", date="2026-07-01", fresh=False),
    "DZVU3pay2M_": dict(
        author="adam.badar", likes="436", commentsCount="34", views=None,
        caption="Comment “TOOLS” and I'll send you my full list 👇 If you want to learn more about building with AI, follow @adam.badar",
        hook="For coding, this is decent, this is good, this is insane. For writing, this is terrible, this is good and this is incredible.",
        style="CURIOSITY GAP", date="2026-06-10", fresh=False),
    "DaglaDvS4PS": dict(
        author="adam.badar", likes="146", commentsCount="12", views=None,
        caption="Every startup is built on two things: product and customers. Claude Code's release solved the product half. But the best product in the world is worthless without customers. Bavlio.com is Claude Code for customers.",
        hook="The release of Claude Code made it possible for anyone creative and dedicated to build a product — but even the best product is irrelevant without someone to use it.",
        style="ANY", date="2026-07-08", fresh=False),
    "DZIzHXPnO15": dict(
        author="adam.badar", likes="70", commentsCount="8", views=None,
        caption="These 6 books completely changed how I think as an entrepreneur 📚 If you want to cut through the noise, comment “BOOKS” 👇 and I'll send you a complete list of my recommendations.",
        hook="6 Books Every Entrepreneur Should Read",
        slideHook=True, style="ANY", date="2026-06-03", fresh=False),
    "DZSkc-DHAgi": dict(
        author="adam.badar", likes="63", commentsCount="9", views=None,
        caption="Everyone is selling AI hype. Very few people are asking what the tool actually helps you produce. This carousel breaks down: Hype vs Value, Attention vs Utility, Noise vs Signal. Featuring: openclaw, Claude code, notebooklm, Claude design, Gemini cli, and Codex.",
        hook="AI Tools: Hype vs. Value",
        slideHook=True, style="ANY", date="2026-06-07", fresh=False),

    # ── jackorrofficial ───────────────────────────────────────────
    "DZ7ZErsR_G6": dict(
        author="jackorrofficial", likes="935", commentsCount="69", views=None,
        caption="On the App Store now >> #launchday #fitnessapp #startups #founder",
        hook="Today I officially launched my app. Most fitness apps seem designed for your grandma or The Rock, with literally no in between.",
        style="RESULT/FLEX", date="2026-06-23", fresh=False),
    "DYAXcNcRzGO": dict(
        author="jackorrofficial", likes="492", commentsCount="54", views=None,
        caption="i'm building everything in public, so join the journey 🤘 #toronto #startup #internship #entrepreneurship",
        hook="I just rejected my summer internship to build a startup in Toronto. And no, I didn't raise a million dollars or drop out of some Ivy League school.",
        style="STAKES", date="2026-05-06", fresh=False),
    "DaspqIYRRxc": dict(
        author="jackorrofficial", likes="186", commentsCount="23", views=None,
        caption="it's gonna be big #founder #startup #entrepreneurship #20s",
        hook="I recently learned you should never respond to a DM from a stranger online, especially one with lots of followers.",
        style="CURIOSITY GAP", date="2026-07-13", fresh=True),
    "DadXEBUOcaF": dict(
        author="jackorrofficial", likes="108", commentsCount="11", views=None,
        caption="maybe it's time to just take that risk #entrepreneurship #risk #success #founder",
        hook="Let me get this straight: you drive a car without understanding how the airbag protects you, but you won't take a risk on yourself.",
        style="STAKES", date="2026-07-07", fresh=False),
    "Dal6XOCN02B": dict(
        author="jackorrofficial", likes="96", commentsCount="4", views=None,
        caption="it's the thing I've been living by #entrepreneurship #founder #success #startups",
        hook="The most successful people I know would never tell you to focus on money — they'd tell you to focus on this one thing.",
        style="CURIOSITY GAP", date="2026-07-11", fresh=False),
    "DajQEo_t_k5": dict(
        author="jackorrofficial", likes="91", commentsCount="4", views=None,
        caption="stay away from these plz #founder #entrepreneurship #startups #success",
        hook="Tacky things that bottom-barrel founders do that you should avoid at all costs: introducing yourself as a founder before you say your name...",
        style="CURIOSITY GAP", date="2026-07-09", fresh=False),
    "DaoSpW_xJ9t": dict(
        author="jackorrofficial", likes="57", commentsCount="7", views=None,
        caption="these are ones I can promise I'll be staying away from #founder #success #entrepreneurship",
        hook="Purchases that no successful founder is making if they actually want to be in the top one percent.",
        style="CURIOSITY GAP", date="2026-07-11", fresh=False),

    # ── briceiscoding (IG is his secondary channel — low signal) ──
    "DYIf937DtgW": dict(
        author="briceiscoding", likes="7", commentsCount="1", views=None,
        caption="Nouvelle vidéo YouTube ! J'ai (re)codé le jeu iconique Flappy Bird des années 2000 pour y entraîner 100 cobayes et dénicher LE champion qui battra tous les records !",
        hook="(RE)CODER LE JEU LE PLUS ÉNERVANT DU MONDE POUR NE PLUS JAMAIS PERDRE",
        slideHook=True, style="ANY", date="2026-05-09", fresh=False),
    "DWvWtzpjD1Q": dict(
        author="briceiscoding", likes="6", commentsCount="1", views=None,
        caption="Nouvelle vidéo YouTube en ligne ! Je me suis amusé à vibe coder une petite application pour générer un BUILD 3D en moins de 3s dans le jeu Minecraft, à partir d'une simple IMAGE trouvée sur Google !",
        hook="J'AI CRÉÉ L'OUTIL ULTIME QUI TRANSFORME UNE IMAGE EN BUILD 3D DANS MINECRAFT !",
        slideHook=True, style="ANY", date="2026-04-05", fresh=False),
    "DaaZJumIGXM": dict(
        author="briceiscoding", likes="5", commentsCount=None, views=None,
        caption="Major IV COD / HalloW @hallow_fr #callofduty #esport #m8win #gentlematesesport",
        hook="Major IV COD / HalloW",
        style="ANY", date="2026-07-06", fresh=False),
    "DaaYYUiIZqs": dict(
        author="briceiscoding", likes="3", commentsCount=None, views=None,
        caption="Major IV COD #m8win #callofduty #esport",
        hook="Major IV COD",
        style="ANY", date="2026-07-06", fresh=False),
    "DaaXJTdCLu9": dict(
        author="briceiscoding", likes="4", commentsCount=None, views=None,
        caption="COD Major IV #m8win #callofduty #gentlemates #gentlematesesport #esport",
        hook="COD Major IV",
        style="ANY", date="2026-07-06", fresh=False),
    "DaXc5i3qPi6": dict(
        author="briceiscoding", likes="8", commentsCount=None, views=None,
        caption="INSCRIVEZ-VOUS ICI POUR TEST LA BETA : https://pleasedontche.at — Je sais que cest long mais ça arrive, et vous allez pouvoir m'aider ! J'essaie de la rendre l'algo plus fiable encore.",
        hook="Inscrivez-vous ici pour tester la bêta de mon anti-cheat.",
        style="ANY", date="2026-07-04", fresh=False),
    "DYuAzPHjoPK": dict(
        author="briceiscoding", likes="3", commentsCount=None, views=None,
        caption="Meilleur achat en terme de laptop. Ça n'est qu'un MacBook Air mais il fait déjà mieux le taff que 99% des pc du marché.",
        hook="Meilleur achat en terme de laptop.",
        style="ANY", date="2026-05-24", fresh=False),

    # re-scraped duplicate — restore yesterday's corrected values
    "DakX2RZOp4R": dict(
        author="briceiscoding", likes="5", commentsCount="1", views=None,
        caption="Do you realize what's happening? The indie hacker / developer community… Sometimes I stop for a few seconds and think: We're building an insane amount of stuff every single day.",
        hook="Do you realize what's happening?",
        style="CURIOSITY GAP", date="2026-07-09", fresh=False),
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
print(f"Corrected {len(seen)} competitor posts; dataset {len(data['posts'])} total.")
for p in data["posts"][:12]:
    print(f"  {p['engagement']:>8}  @{p['author']:<22} {p['hook'][:62]}")
