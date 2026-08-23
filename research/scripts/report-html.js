#!/usr/bin/env node
// =============================================================================
// Instagram Research — HTML report generator
// Reads the (Claude-corrected) raw-posts.json + transcripts + hook screenshots
// and writes a styled report.html into the project folder.
// Usage: node scripts/report-html.js <project-name>
// =============================================================================

import { readFileSync, writeFileSync, existsSync, readdirSync } from 'fs';
import { join } from 'path';

const projectName = process.argv[2];
if (!projectName) {
  console.error('Usage: node scripts/report-html.js <project-name>');
  process.exit(1);
}

const projectDir = join(import.meta.dirname, '..', 'projects', projectName);
const dataFile = join(projectDir, 'raw-posts.json');
if (!existsSync(dataFile)) {
  console.error(`No raw-posts.json found in ${projectDir}. Run the scrape first.`);
  process.exit(1);
}

const data = JSON.parse(readFileSync(dataFile, 'utf8'));
const transcriptsDir = join(projectDir, 'transcripts');
const hooksDir = join(projectDir, 'hook-screenshots');

// ── helpers ──────────────────────────────────────────────────────────────────
function parseNum(s) {
  if (s == null) return 0;
  if (typeof s === 'number') return s;
  const m = String(s).trim().replace(/,/g, '').match(/^([\d.]+)\s*([KkMm])?/);
  if (!m) return 0;
  let n = parseFloat(m[1]);
  if (m[2] && /[Kk]/.test(m[2])) n *= 1000;
  if (m[2] && /[Mm]/.test(m[2])) n *= 1000000;
  return Math.round(n);
}

function fmt(n) {
  n = parseNum(n);
  if (n >= 1000000) return (n / 1000000).toFixed(1).replace(/\.0$/, '') + 'M';
  if (n >= 1000) return (n / 1000).toFixed(1).replace(/\.0$/, '') + 'K';
  return String(n);
}

function esc(s) {
  return String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function engagement(p) {
  if (p.engagement && p.engagement > 0) return parseNum(p.engagement);
  return Math.max(parseNum(p.likes), parseNum(p.views)) + parseNum(p.commentsCount);
}

function transcriptFor(p) {
  const f = join(transcriptsDir, `${p.postId}.txt`);
  return existsSync(f) ? readFileSync(f, 'utf8').trim() : '';
}

function firstSentence(text) {
  if (!text) return '';
  const m = text.match(/^.*?[.!?](?=\s|$)/);
  return (m ? m[0] : text.split('\n')[0]).trim().slice(0, 200);
}

function hookFor(p, transcript) {
  if (p.hook) return p.hook;
  if (p.type === 'reel' && transcript) return firstSentence(transcript);
  return firstSentence(p.caption);
}

// "Why it worked" signal detection
function whyItWorked(p, hook, transcript, topQuartile) {
  const reasons = [];
  const caption = p.fullCaption || p.caption || '';
  if (/comment\s+["'“]?\w+["'”]?\s+(and|to|below|for)/i.test(caption) || /comment\s+["'“][^"'”]+["'”]/i.test(caption))
    reasons.push('Comment-bait CTA — drives comments, which the algorithm rewards hardest');
  if (/\d/.test(hook))
    reasons.push('Specific number in the hook — concrete beats vague, triggers specificity bias');
  if (/\b(framework|method|system|formula|blueprint|playbook)\b/i.test(hook + ' ' + caption))
    reasons.push('Named framework/system — packages the value, feels ownable and saveable');
  if (hook.length > 0 && hook.length < 60)
    reasons.push('Short, punchy hook — lands within the first second of reading');
  if (/\?/.test(hook))
    reasons.push('Question hook — opens a loop the viewer stays to close');
  if (/\b(vs\.?|versus|instead of|not .+ but)\b/i.test(hook))
    reasons.push('Comparison framing — conflict/contrast stops the scroll');
  if (/\bin \d+\s*(second|minute|hour|day|week|month)s?\b/i.test(hook + ' ' + caption))
    reasons.push('Time promise — a concrete payoff deadline');
  if (engagement(p) >= topQuartile)
    reasons.push('Top-quartile engagement for this scrape — the niche demonstrably wants this');
  return reasons;
}

function visualHook(p, transcript) {
  const t = ((p.fullCaption || p.caption || '') + ' ' + transcript).toLowerCase();
  if (/split.?screen/.test(t)) return 'Split screen';
  if (/whiteboard/.test(t)) return 'Whiteboard explainer';
  if (/screen.?(record|share|capture)|screenshot/.test(t)) return 'Screen recording';
  if (/podcast|interview|mic\b/.test(t)) return 'Podcast/interview clip';
  if (/vlog|day in the life|pov/.test(t)) return 'Vlog / POV footage';
  if (/meme|skit/.test(t)) return 'Meme/skit format';
  if (p.type === 'image') return 'Static graphic / carousel slide';
  return 'Talking head with text overlay';
}

// ── data prep ────────────────────────────────────────────────────────────────
const posts = [...(data.posts || [])].sort((a, b) => engagement(b) - engagement(a));
const engValues = posts.map(engagement).sort((a, b) => a - b);
const topQuartile = engValues[Math.floor(engValues.length * 0.75)] || 0;
const transcribed = posts.filter(p => transcriptFor(p)).length;
const withHookShots = posts.filter(p => existsSync(join(hooksDir, `${p.postId}_0s.jpg`))).length;
const topLikes = Math.max(0, ...posts.map(p => parseNum(p.likes)));
const reelPct = posts.length ? Math.round(100 * posts.filter(p => p.type === 'reel').length / posts.length) : 0;

const top6 = posts.slice(0, 6).map((p, i) => {
  const transcript = transcriptFor(p);
  const hook = hookFor(p, transcript);
  return { p, i, transcript, hook, reasons: whyItWorked(p, hook, transcript, topQuartile), visual: visualHook(p, transcript) };
});

// ── winning patterns ─────────────────────────────────────────────────────────
const patterns = [];
patterns.push({
  title: 'Format breakdown',
  body: `${data.reels ?? posts.filter(p => p.type === 'reel').length} Reels vs ${data.images ?? posts.filter(p => p.type === 'image').length} static posts scraped — ${reelPct}% of what performs in this niche is video. ${reelPct >= 60 ? 'Reels are the dominant format here; prioritize video.' : 'Static/carousel still holds real ground in this niche.'}`
});
const ctaCount = posts.filter(p => /comment\s+["'“]?\w+/i.test(p.fullCaption || p.caption || '')).length;
patterns.push({
  title: 'Comment CTA usage',
  body: `${ctaCount} of ${posts.length} posts use a "comment X and I'll send it" style CTA. ${ctaCount / Math.max(posts.length, 1) > 0.25 ? 'This is a core engagement engine in the niche — comments trigger DMs and boost reach.' : 'Not dominant here, but the posts that use it tend to over-perform.'}`
});
const shortHooks = top6.filter(t => t.hook.length < 60).length;
const numberHooks = top6.filter(t => /\d/.test(t.hook)).length;
patterns.push({
  title: 'Hook analysis',
  body: `Of the top 6: ${shortHooks} open with a hook under 60 characters, ${numberHooks} put a specific number in the first line. The winning openers state a concrete outcome, problem, or contrarian claim — none open with a greeting or context-setting.`
});
const themeWords = {};
for (const t of top6) {
  const text = (t.hook + ' ' + (t.p.caption || '')).toLowerCase();
  for (const w of text.match(/[a-z]{5,}/g) || []) {
    if (['about', 'their', 'there', 'these', 'those', 'which', 'because', 'people', 'going', 'really', 'thing', 'things'].includes(w)) continue;
    themeWords[w] = (themeWords[w] || 0) + 1;
  }
}
const topThemes = Object.entries(themeWords).filter(([, c]) => c > 1)
  .sort((a, b) => b[1] - a[1]).slice(0, 8).map(([w]) => w);
patterns.push({
  title: 'Content themes',
  body: topThemes.length ? `Recurring vocabulary across top performers: ${topThemes.join(', ')}. These are the concepts the niche audience is actively rewarding right now.` : 'Not enough overlapping vocabulary across top posts to call a theme — the niche rewards variety.'
});

// ── HTML ─────────────────────────────────────────────────────────────────────
const cardsHtml = top6.map(({ p, i, transcript, hook, reasons, visual }) => {
  const shots = [0, 1, 2]
    .map(s => `hook-screenshots/${p.postId}_${s}s.jpg`)
    .filter(rel => existsSync(join(projectDir, rel)))
    .map(rel => `<img src="${rel}" alt="hook frame" loading="lazy">`).join('');
  return `
  <div class="card">
    <div class="card-head">
      <span class="rank">#${i + 1}</span>
      <div>
        <div class="author">@${esc(p.author || 'unknown')}</div>
        <div class="meta">${esc(p.type || 'post')} · ${esc(p.dateText || p.date || '')} · ${esc(p.source || '')}</div>
      </div>
      <div class="eng">
        ${p.views ? `<span>▶ ${fmt(p.views)}</span>` : ''}
        <span>♥ ${fmt(p.likes)}</span>
        <span>💬 ${fmt(p.commentsCount)}</span>
      </div>
    </div>
    ${shots ? `<div class="shots">${shots}</div>` : ''}
    <div class="row"><span class="label">Visual hook</span> ${esc(visual)}</div>
    <div class="row hook"><span class="label">${p.slideHook ? 'Slide hook' : 'Spoken hook'}</span> “${esc(hook)}”</div>
    ${transcript ? `<details><summary>Full transcript (${transcript.split(/\s+/).length} words)</summary><div class="transcript">${esc(transcript)}</div></details>` : ''}
    ${reasons.length ? `<div class="why"><span class="label">Why it worked</span><ul>${reasons.map(r => `<li>${esc(r)}</li>`).join('')}</ul></div>` : ''}
    ${p.caption ? `<div class="caption">${esc(p.caption.slice(0, 220))}${p.caption.length > 220 ? '…' : ''}</div>` : ''}
    <a class="link" href="${esc(p.url || 'https://www.instagram.com' + (p.href || ''))}" target="_blank">Open post ↗</a>
  </div>`;
}).join('\n');

const patternsHtml = patterns.map(pt => `
  <div class="pattern">
    <h3>${esc(pt.title)}</h3>
    <p>${esc(pt.body)}</p>
  </div>`).join('\n');

const html = `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${esc(data.project)} — Instagram Research</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;800&display=swap" rel="stylesheet">
<style>
  :root { --bg:#0A0A08; --gold:#D4A843; --card:#141310; --line:#26231c; --txt:#EAE6DC; --dim:#9a937f; }
  * { box-sizing:border-box; margin:0; padding:0; }
  body { background:var(--bg); color:var(--txt); font-family:'Inter',system-ui,sans-serif; line-height:1.55; }
  .wrap { max-width:1100px; margin:0 auto; padding:48px 24px 80px; }
  .hero { border-bottom:1px solid var(--line); padding-bottom:32px; margin-bottom:32px; }
  .hero .kicker { color:var(--gold); font-weight:600; letter-spacing:.14em; text-transform:uppercase; font-size:12px; }
  .hero h1 { font-size:clamp(28px,5vw,44px); font-weight:800; margin:8px 0 10px; }
  .hero .sub { color:var(--dim); max-width:720px; }
  .hero .terms { margin-top:14px; display:flex; flex-wrap:wrap; gap:8px; }
  .hero .terms span { border:1px solid var(--line); color:var(--gold); border-radius:999px; padding:3px 12px; font-size:12px; }
  .stats { display:grid; grid-template-columns:repeat(auto-fit,minmax(140px,1fr)); gap:12px; margin-bottom:40px; }
  .stat { background:var(--card); border:1px solid var(--line); border-radius:14px; padding:16px 18px; }
  .stat b { display:block; font-size:26px; color:var(--gold); font-weight:800; }
  .stat span { color:var(--dim); font-size:12px; text-transform:uppercase; letter-spacing:.08em; }
  h2 { font-size:22px; font-weight:800; margin:40px 0 18px; }
  h2 em { color:var(--gold); font-style:normal; }
  .cards { display:grid; grid-template-columns:repeat(auto-fill,minmax(320px,1fr)); gap:18px; }
  .card { background:var(--card); border:1px solid var(--line); border-radius:16px; padding:18px; transition:transform .15s, border-color .15s; display:flex; flex-direction:column; gap:12px; }
  .card:hover { transform:translateY(-3px); border-color:var(--gold); }
  .card-head { display:flex; align-items:center; gap:12px; }
  .rank { color:var(--gold); font-weight:800; font-size:22px; min-width:38px; }
  .author { font-weight:600; }
  .meta { color:var(--dim); font-size:12px; }
  .eng { margin-left:auto; display:flex; gap:10px; color:var(--dim); font-size:13px; white-space:nowrap; }
  .shots { display:flex; gap:6px; overflow-x:auto; }
  .shots img { width:32%; min-width:90px; border-radius:8px; border:1px solid var(--line); }
  .label { display:block; color:var(--gold); font-size:11px; text-transform:uppercase; letter-spacing:.1em; margin-bottom:2px; }
  .row { font-size:14px; }
  .hook { font-weight:600; font-size:15px; }
  details summary { cursor:pointer; color:var(--dim); font-size:13px; }
  .transcript { max-height:180px; overflow-y:auto; color:var(--dim); font-size:13px; margin-top:8px; padding:10px; background:var(--bg); border-radius:8px; border:1px solid var(--line); }
  .why ul { margin:4px 0 0 18px; font-size:13px; color:var(--txt); }
  .why li { margin-bottom:3px; }
  .caption { color:var(--dim); font-size:13px; border-left:2px solid var(--line); padding-left:10px; }
  .link { color:var(--gold); font-size:13px; text-decoration:none; margin-top:auto; }
  .patterns { display:grid; grid-template-columns:repeat(auto-fit,minmax(240px,1fr)); gap:14px; }
  .pattern { background:var(--card); border:1px solid var(--line); border-radius:14px; padding:18px; }
  .pattern h3 { color:var(--gold); font-size:14px; margin-bottom:8px; }
  .pattern p { font-size:14px; color:var(--txt); }
  footer { margin-top:60px; border-top:1px solid var(--line); padding-top:20px; color:var(--dim); font-size:13px; }
  footer a { color:var(--gold); text-decoration:none; }
</style>
</head>
<body>
<div class="wrap">
  <div class="hero">
    <div class="kicker">Instagram Niche Research</div>
    <h1>${esc(data.project)}</h1>
    <div class="sub">${esc(data.niche || '')} · scraped ${esc((data.scrapedAt || '').slice(0, 10))}</div>
    <div class="terms">${(data.searchTerms || []).map(t => `<span>#${esc(t)}</span>`).join('')}
      ${(data.competitors || []).map(c => `<span>${esc(c.replace(/https?:\/\/(www\.)?instagram\.com\//, '@').replace(/\/$/, ''))}</span>`).join('')}</div>
  </div>

  <div class="stats">
    <div class="stat"><b>${posts.length}</b><span>posts analyzed</span></div>
    <div class="stat"><b>${reelPct}%</b><span>reels</span></div>
    <div class="stat"><b>${transcribed}</b><span>transcribed</span></div>
    <div class="stat"><b>${withHookShots}</b><span>visual hooks</span></div>
    <div class="stat"><b>${fmt(topLikes)}</b><span>top likes</span></div>
  </div>

  <h2>Top <em>${top6.length}</em> performers</h2>
  <div class="cards">
${cardsHtml}
  </div>

  <h2>Winning <em>patterns</em></h2>
  <div class="patterns">
${patternsHtml}
  </div>

  <footer>
    Research flow by <a href="https://www.instagram.com/leifabel11/" target="_blank">Leif Abel (@leifabel11)</a>
    · adapted for the Epifani Growth Engine
  </footer>
</div>
</body>
</html>`;

const outFile = join(projectDir, 'report.html');
writeFileSync(outFile, html);
console.log(`Report written: ${outFile}`);
console.log(`Posts: ${posts.length} | transcribed: ${transcribed} | top card count: ${top6.length}`);
