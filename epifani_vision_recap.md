# 🚀 Epifani Growth Engine — New Vision & Strategy Recap

This document outlines the strategic pivot of the Epifani Content Automation Engine. We are moving away from robotic, generic prediction cards/clips and shifting toward a high-converting **"Founder's Journey / Building-in-Public"** narrative model, optionally optimized using advanced neural prediction feedback.

---

## 1. Core Positioning: Founder's Journey + Live Proof

Instead of broadcasting plain betting tip cards (which look spammy and generate low trust), you position yourself as a **developer/founder documenting the creation of a sports-prediction AI**, inspired by the visual style of creators like **GreenCode**.

### 🤝 Collaborative Scripting (Human-in-the-Loop)
Because the AI cannot guess your daily progress, the script generation will be collaborative:
1. **Daily Sync**: You and I discuss what the focus of today's video should be.
2. **Dashboard Input**: You enter a brief summary of today's milestone (e.g., *"Spent 3 hours debugging the Portuguese league data parser"*) into the Streamlit UI.
3. **Synthesis**: The engine merges your input with the live match prediction data and prompts Gemini to write a natural, first-person narrative voiceover.

### 🎭 The Animated Character & "Green Code" Vibe
To emulate the Green Code aesthetic, the video pipeline will combine:
* **The Epifani Avatar**: A stylized AI/hacker character representing the "Epifani Engine".
* **Visual Theme**: Dark tech aesthetics, code terminals, glowing graphs, and neon overlays instead of generic stock footage.
* **Audio**: A consistent, premium AI voice (via Edge-TTS or ElevenLabs) reading the voiceover script.

---

## 2. Technical Character Pipelines (Under Consideration)

To render the animated character, we can configure the engine in one of two ways:

### Option A: The Asset Loop (Recommended for Launch)
* We pre-render a library of short, high-quality loopable clips showing the Epifani character (e.g., typing at a keyboard, looking at glowing charts, pointing at the screen).
* The engine randomly selects and sequences these custom clips to fit the audio length, overlaying code animations and the prediction card at the end. 
* **Pros**: 100% free, runs instantly, no complex external video APIs needed.

### Option B: AI Talking Head Generation (Future Phase)
* The engine generates the audio file first.
* It sends the audio + a static image of the Epifani character to an animation API (such as Hedra, D-ID, or a local SadTalker model).
* The API returns a video of the character lip-syncing to the audio.
* **Pros**: High immersion, the character's mouth moves exactly to the words.
* **Cons**: Requires paid API credits or heavy local GPU computing.

---

## 3. Immediate Implementation Steps

To execute this vision, we will work through these items in order:

### ⚙️ Step 1: Initialize the New Script Engine
* Modify `engine/core/script_generator.py` and `engine/core/video_builder.py` prompts to adopt the first-person founder perspective.
* Integrate automatic "days active" tracking so Gemini automatically writes *"Day X of building Epifani..."* based on your SQLite posting database.

### 🎥 Step 2: Establish the Manual Posting Baseline
* Generate the first 3 journey videos locally using your newly added Pexels key and updated Gemini key.
* Manually upload them to TikTok, Instagram, and YouTube Shorts for a few days to establish baseline views and organic feedback.

### 🧠 Step 3: Implement TRIBE v2 (Cloud Integration)
* Set up a template script for deploying the `facebook/tribev2` model on a rented RunPod/Vast.ai container.
* Create `engine/core/tribe_evaluator.py` to handle the video upload, request predicted fMRI attention voxel scores, and trigger a rewrite loop if attention drops below a specific percentile threshold.

---

## 4. The TRIBE v2 Fallback Plan: "LLM Cognitive Critic"

If you choose not to run a cloud GPU instance for TRIBE v2, we implement a **zero-cost, zero-hardware fallback loop** using a secondary Gemini critique agent:

```
┌─────────────────────────┐
│  1. Generate Script     │ (Gemini: Writer)
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│  2. Evaluate Script     │ (Gemini: Hook/Pacing Critic)
└────────────┬────────────┘
             │
      ┌──────┴──────┐
      ▼             ▼
   [Score < 7]   [Score >= 7]
      │             │
      │ (Critique)  │
      ▼             ▼
┌───────────┐ ┌───────────┐
│ Rewriter  │ │ Compile   │ (MoneyPrinterTurbo)
└───────────┘ └───────────┘
```

* **How it works**: Gemini acts as a strict social media copy editor, evaluating Hook Strength, Narrative Pacing, and Transition Flow. It rejects scripts that feel boring, unnatural, or overly dry.
* **Why it works**: It simulates the same quality-assurance filter as TRIBE v2, running instantly and for free.

---

## 5. What We Should Do Next (Immediate Roadmap)

To bring the Epifani business engine to life, we should execute these steps in order:

### 🚀 Phase 1: Interactive Dashboard (Today)
1. **Add Story Hook Input**: Add a text area in `engine/web_ui/dashboard.py` where you can input the day's journey update (e.g., *"Spent the morning optimizing our Portuguese league stats parser"*).
2. **Update script generation logic**: Adapt `engine/core/script_generator.py` to weave the daily story update and the match prediction together into the Founder's Journey format.

### 🤖 Phase 2: The LLM Critic (Tribe Fallback)
1. **Build Critic Module**: Implement the LLM-based feedback loop so every script is vetted and auto-polished before passing to the video maker.

### 🎨 Phase 3: Visual Identity
1. **Design Character Assets**: Generate the Epifani hacker/developer character logo/graphics.
2. **Setup Background Loops**: Replace generic Pexels footage with loopable tech/code animations and the Epifani branding overlays.

