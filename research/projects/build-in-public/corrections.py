#!/usr/bin/env python3
"""Claude vision-pass corrections for the build-in-public scrape (2026-07-12).

Every value below was read off the post screenshots (source of truth), with
hooks taken from the spoken transcript first sentence (Reels), on-video/slide
text (music-only Reels + images), or caption first sentence as fallback.
"fresh" = posted within ~48h of the scrape → engagement not settled, never
used for the punish list.
"""
import json
from pathlib import Path

DATA = Path(__file__).parent / "raw-posts.json"

# postId -> corrections read from the screenshot + transcript
C = {
    "DZfeN6JBbS9": dict(  # 10xaiengineer — AI news flex, music only
        author="10xaiengineer", likes="261.2K", commentsCount="2K", views=None,
        caption="As of today, June 12, 2026, Elon Musk is not only the richest person in the world, but he is officially crossing the unprecedented $1 trillion net worth mark, making him the first verified trillionaire in history.",
        hook="Elon Musk Officially Hits $1.1 Trillion Net Worth, Becoming the World's First Trillionaire",
        slideHook=True, style="RESULT/FLEX", date="2026-06-12", fresh=False),
    "DZphPkXSAbi": dict(  # adam.badar — contrarian mantra, music only
        author="adam.badar", likes="85.7K", commentsCount="494", views=None,
        caption="Life is hard. Make it harder. Start your own company. Follow to make ur business easier 👀",
        hook="Life is Hard. Make it Harder. Start your own company.",
        slideHook=True, style="CURIOSITY GAP", date="2026-06-17", fresh=False),
    "DYVrkfXsjDC": dict(  # liambuilds.ai — mantra over b-roll, music only
        author="liambuilds.ai", likes="29K", commentsCount="241", views=None,
        caption="Days stack. Work compounds. That's the whole point. Show up. Repeat. The work speaks later.",
        hook="Just keep building.",
        slideHook=True, style="ANY", date="2026-05-15", fresh=False),
    "DZDnyi4pvBv": dict(  # jackorrofficial — rapid-fire jargon test
        author="jackorrofficial", likes="27.8K", commentsCount="297", views=None,
        caption="threw some niche niche ones in there #startup #founder #buildinpublic",
        hook="Let's see if you actually know about startups.",
        style="CURIOSITY GAP", date="2026-06-01", fresh=False),
    "DaldjGDswAN": dict(  # sebas.techbusiness — domain checklist
        author="sebas.techbusiness", likes="130", commentsCount="2", views=None,
        caption="Buying the domain feels like the “we're official” moment. You find the name. It's available. You buy it. And for a second, it feels like the app is basically launched. But this is where a lot of founders quietly create a mess they'll have to clean up later.",
        hook="Buying the domain feels like the “we're official” moment.",
        style="ANY", date="2026-07-10", fresh=False),
    "DOE8g4Xkb5m": dict(  # maggieindata — paid partnership ad
        author="maggieindata", likes="91", commentsCount="6", views=None,
        caption="From chaos to clarity 🔥→🙏 Building an AI startup means you're juggling 10 roles at once. But you don't have to do sales the hard way! (paid partnership with @zoominfo)",
        hook="If you're in the early stage of building a startup, you probably feel like this.",
        style="STRUGGLE", date="2025-09-02", fresh=False),
    "Daso1p5tfgV": dict(  # novaroapp — product promo carousel
        author="novaroapp", likes="90", commentsCount=None, views=None,
        caption="Stop waiting for the “perfect time.” Start building the career you actually want —one mission at a time. 🚀",
        hook="Stop wasting time wondering what to do next.",
        slideHook=True, style="ANY", date="2026-07-12", fresh=True),
    "DaZK5psT3dG": dict(  # altussnyman_official — comment-bait resource
        author="altussnyman_official", likes="26", commentsCount="25", views=None,
        caption="Comment “API” if you want the free GitHub repo from this video. This repo gives you access to 1,400+ free public APIs across categories like finance, news, jobs, programming, sports data, and more.",
        hook="This secret GitHub repo gives you access to over 1,400 free APIs.",
        style="CURIOSITY GAP", date="2026-07-05", fresh=False),
    "DAeNOMwuBrG": dict(punish=True,   # planatic.ai — branding wordplay launch post
        author="planatic.ai", likes="38", commentsCount="9", views=None,
        caption="DON'T BE A LUNATIC, BE A PLANATIC. Just like a cactus blossoms in the harsh desert, Planatic has emerged from the minds of engineering students...",
        hook="DON'T BE A LUNATIC, BE A PLANATIC.",
        style="ANY", date="2024-09-28", fresh=False),
    "DaF-qmbBQIP": dict(  # aistartup.fren — AI news take
        author="aistartup.fren", likes="31", commentsCount="1", views=None,
        caption="OpenAI released GPT 5.6 and we can't use it #aistartup #aiagents #openai #anthropic",
        hook="OpenAI just released their best model, GPT 5.6, and we cannot use it.",
        style="CURIOSITY GAP", date="2026-06-27", fresh=False),
    "DasgNE1Ir8K": dict(  # egwumarvellous_ — day-1 intro vlog
        author="egwumarvellous_", likes="14", commentsCount="6", views=None,
        caption="Everyone starts somewhere. This is mine. I'm building in public, learning as I go, and sharing the journey. If you're on a similar path, follow along. 🚀",
        hook="For the last few years, I've been helping a lot of people grow online — and I'm about to change that.",
        style="ANY", date="2026-07-12", fresh=True),
    "DMLoSoxthTH": dict(punish=True,   # necodex — corporate webinar flyer
        author="necodex", likes="12", commentsCount=None, views=None,
        caption="Hiring for your AI startup? Don't leave it to chance... Join our FREE webinar \"Hiring Insights for AI Entrepreneurs\".",
        hook="HIRING INSIGHTS FOR AI ENTREPRENEURS — attract and hire the best talent",
        slideHook=True, style="ANY", date="2025-07-16", fresh=False),
    "Dashb3fuzeC": dict(  # startupideasdailyx — relatable meme
        author="startupideasdailyx", likes="5", commentsCount="1", views=None,
        caption="Subscribe to halfbaked and thank me later!",
        hook="Me at 2 AM trying to brainstorm a low-competition startup idea from scratch...",
        slideHook=True, style="STRUGGLE", date="2026-07-12", fresh=True),
    "DasgzZ4KgR3": dict(  # capitalshiftz — Hindi biz story
        author="capitalshiftz", likes="4", commentsCount=None, views=None,
        caption="3 Employees $1.8 Billion Company! 🤯",
        hook="How many employees do you think a 1.8 billion dollar company has? Three.",
        style="CURIOSITY GAP", date="2026-07-12", fresh=True),
    "Dasoht1MeNC": dict(  # rehberinapp — Turkish day-25 build log
        author="rehberinapp", likes="3", commentsCount=None, views=None,
        caption="Gençlerin kariyer sorunlarını çözecek girişimi sıfırdan inşa ediyorum. Gün 25",
        hook="Gençlerin kariyer sorunlarını çözecek girişimi sıfırdan inşa ediyorum. Gün 25",
        style="ANY", date="2026-07-12", fresh=True),
    "DarjJ2GiVAP": dict(  # buildingwith_megan — unhinged-money meme
        author="buildingwith_megan", likes="3", commentsCount=None, views=None,
        caption="Found my first user today! It's my mom, but still counting it. 🥰",
        hook="I'm genuinely broke and need money fast — what is the most diabolical legal thing you've done to make money? Something actually UNHINGED.",
        slideHook=True, style="STRUGGLE", date="2026-07-12", fresh=True),
    "DaqIY0rD4gi": dict(punish=True,   # lsetuk — incubator flyer
        author="lsetuk", likes="2", commentsCount="1", views=None,
        caption="Ready to Turn Your Startup Idea into Reality? Take the first step towards entrepreneurial success with the LSET Startup Incubator.",
        hook="READY TO BUILD SOMETHING EXTRAORDINARY?",
        slideHook=True, style="ANY", date="2026-07-11", fresh=False),
    "DakyrvHjW3Y": dict(punish=True,   # ari4sin — generic status selfie
        author="ari4sin", likes="1", commentsCount="1", views=None,
        caption="Last stretch for today friends!",
        hook="Last stretch for today friends!",
        style="ANY", date="2026-07-09", fresh=False),
    "DakX2RZOp4R": dict(  # briceiscoding — community observation
        author="briceiscoding", likes="5", commentsCount="1", views=None,
        caption="Do you realize what's happening? The indie hacker / developer community… Sometimes I stop for a few seconds and think: We're building an insane amount of stuff every single day.",
        hook="Do you realize what's happening?",
        style="CURIOSITY GAP", date="2026-07-09", fresh=False),
    "Daewab6DXmw": dict(  # learningwith_miless — relatable meme
        author="learningwith_miless", likes="1", commentsCount=None, views=None,
        caption="This might be a side project now, but watch me turn it into my main gig. The grind is real. 🚀",
        hook="My friends are arguing about reality TV while I'm over here on Replit trying to figure out why my API isn't returning data. Help.",
        slideHook=True, style="STRUGGLE", date="2026-07-07", fresh=False),
    "DasntzBk_DJ": dict(winner=True,   # build_with_oliver — POV Stripe meme
        author="build_with_oliver", likes="1", commentsCount=None, views=None,
        caption="Don't wait for permission to build. The internet is your canvas. Paint something awesome. #doitnow #buildinpublic",
        hook="POV: waking up to another Stripe notification from an app I built on Replit in one weekend, realizing I spent 4 years at a desk job for nothing",
        slideHook=True, style="CONFESSION", date="2026-07-12", fresh=True),
    "Dasoq2jPy9F": dict(  # klyvenai — product promo
        author="klyvenai", likes="1", commentsCount=None, views=None,
        caption="Every founder starts here. Papers everywhere. Ideas scattered. No system. No plan. KlyvenAI clears the noise and gives you one place to build from.",
        hook="Every founder starts here.",
        style="ANY", date="2026-07-12", fresh=True),
    "Dasqi3juwfB": dict(  # surfnettechnologies — salesy framework pitch
        author="surfnettechnologies", likes=None, commentsCount=None, views=None,
        caption="Build A Software Business FAST 4 Step Viral Framework Revealed!",
        hook="In the Next 60 Minutes, I'm Going to Build an Entire Software Business. Live.",
        slideHook=True, style="STAKES", date="2026-07-12", fresh=True),
    "DasqukDjJe3": dict(winner=True,   # suraj.hustle — founder-story carousel (was misattributed to "instagram")
        author="suraj.hustle", likes=None, commentsCount=None, views=None,
        caption="He wrote the first line of code alone. Six months later, Wix bought the company for $80M cash and he never took a single dollar of outside funding. No cofounder. No investors. No board. Just one developer, an AI app-builder called Base44, and a laptop.",
        hook="SOLD FOR $80M. ALONE. No team. No funding. Just him and a laptop.",
        slideHook=True, style="RESULT/FLEX", date="2026-07-12", fresh=True),
    "DbKwMkbulVQ": dict(  # monicaaurajewellery — 15s old at capture
        author="monicaaurajewellery", likes=None, commentsCount=None, views=None,
        caption="AURA 022 of 365 ✨ Teach first, sell later. Valuable content builds trust, stronger relationships, and loyal customers over time.",
        hook="One decision I made while building my brand: I don't want to sell just a pair of earrings, I want to sell the complete jewellery set.",
        style="ANY", date="2026-07-12", fresh=True),
    "Dar5XdGIsNT": dict(  # one_day_hq — idea vs investable company
        author="one_day_hq", likes="6", commentsCount=None, views=None,
        caption="Question. Do you know the difference between a great idea and an investable company? Most founders don't. One is about potential. The other is about evidence.",
        hook="Most founders confuse two completely different things: having a great idea and having an investable company.",
        style="CURIOSITY GAP", date="2026-07-12", fresh=True),
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
        print(f"!! no correction for {p['postId']}")
        continue
    seen.add(p["postId"])
    p.update(c)
    p["engagement"] = max(num(c.get("likes")), num(c.get("views"))) + num(c.get("commentsCount"))

missing = set(C) - seen
if missing:
    print(f"!! corrections without a post: {missing}")

data["posts"].sort(key=lambda p: -p.get("engagement", 0))
DATA.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
print(f"Corrected {len(seen)}/{len(data['posts'])} posts, re-sorted by engagement.")
for p in data["posts"][:8]:
    print(f"  {p['engagement']:>8}  @{p['author']:<22} {p['hook'][:60]}")
