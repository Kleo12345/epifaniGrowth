#!/usr/bin/env node
// =============================================================================
// Instagram Research — Single-pass scraper (Linux / Claude-vision edition)
// For each post: navigate → full-post screenshot → engagement + caption →
//                video hook frames → audio → next.
// The full-post screenshot is what Claude reads (in the live session) to pull
// accurate likes / comments / views / caption — no API key needed.
//
// Linux setup: close the browser fully, then relaunch with remote debugging:
//   chromium --remote-debugging-port=9222        (snap chromium)
//   google-chrome --remote-debugging-port=9222   (Chrome)
// Log into instagram.com in that browser (use a personal/throwaway account,
// NOT the brand account), then run:
//   node scripts/scrape.js <project-name>
// =============================================================================

import CDP from 'chrome-remote-interface';
import { readFileSync, writeFileSync, existsSync, mkdirSync } from 'fs';
import { join } from 'path';
import { execSync } from 'child_process';
import { homedir } from 'os';

const projectName = process.argv[2];
if (!projectName) {
  console.error('Usage: node scripts/scrape.js <project-name>');
  process.exit(1);
}

const projectDir = join(import.meta.dirname, '..', 'projects', projectName);
const configFile = join(projectDir, 'config.json');
if (!existsSync(configFile)) {
  console.error(`Project not found: ${projectDir}\nCreate a config.json first.`);
  process.exit(1);
}

const config = JSON.parse(readFileSync(configFile, 'utf8'));
const outputFile = join(projectDir, 'raw-posts.json');
const transcriptsDir = join(projectDir, 'transcripts');
const hooksDir = join(projectDir, 'hook-screenshots');
const postShotsDir = join(projectDir, 'post-screenshots');

[transcriptsDir, hooksDir, postShotsDir].forEach(d => {
  if (!existsSync(d)) mkdirSync(d, { recursive: true });
});

const wait = ms => new Promise(r => setTimeout(r, ms));

function getPort() {
  const portNum = config.browserPort || 9222;
  // Use the browser-tools port file if one exists, otherwise the config/default port.
  const portFile = join(homedir(), '.browser-tools', 'port');
  if (existsSync(portFile)) {
    return parseInt(readFileSync(portFile, 'utf8'));
  }
  return portNum;
}

// yt-dlp cookie source. Snap chromium keeps its profile outside ~/.config,
// so point yt-dlp at it explicitly. Override with "cookiesFrom" in config.json.
function getCookieSpec() {
  if (config.cookiesFrom) return config.cookiesFrom;
  const snapProfile = join(homedir(), 'snap', 'chromium', 'common', 'chromium');
  if (existsSync(snapProfile)) return `chromium:${snapProfile}`;
  if (existsSync(join(homedir(), '.config', 'google-chrome'))) return 'chrome';
  return 'chromium';
}

async function getClient() {
  const port = getPort();
  let targets;
  try {
    targets = await CDP.List({ port });
  } catch (e) {
    console.error(`\nCannot connect to a browser on port ${port}.`);
    console.error('Close the browser completely, then relaunch it with:');
    console.error('  chromium --remote-debugging-port=9222        (snap chromium)');
    console.error('  google-chrome --remote-debugging-port=9222   (Chrome)\n');
    process.exit(1);
  }
  let target = targets.find(t => t.type === 'page' && t.url.includes('instagram.com'));
  if (!target) {
    target = await CDP.New({ port, url: 'https://www.instagram.com/' });
    await wait(5000);
  }
  const client = await CDP({ port, target: target.id });
  await client.Page.enable();
  await client.Runtime.enable();
  await client.DOM.enable();
  return client;
}

// Collect post links from a hashtag search page
// Grabs Instagram's "Top posts" first (the grid at the top),
// then scrolls for additional "Most recent" posts below.
async function collectSearchPosts(client, searchTerm, maxPosts) {
  const searchUrl = `https://www.instagram.com/explore/tags/${searchTerm.replace(/\s+/g, '').replace(/^#/, '')}/`;
  console.log(`  Navigating to: ${searchUrl}`);
  await client.Page.navigate({ url: searchUrl });
  await wait(5000);

  // Phase 1: Grab "Top posts" before scrolling
  const topResult = await client.Runtime.evaluate({
    expression: `
      (() => {
        const links = document.querySelectorAll('a[href*="/p/"], a[href*="/reel/"]');
        const hrefs = [];
        const seen = new Set();
        for (const l of links) {
          const h = l.getAttribute('href');
          if (!seen.has(h)) { seen.add(h); hrefs.push(h); }
        }
        return hrefs;
      })()
    `,
    returnByValue: true
  });
  const topLinks = (topResult.result.value || []).slice(0, 9);
  console.log(`  Top posts: ${topLinks.length}`);

  // Phase 2: Scroll to load "Most recent" posts
  const remainingNeeded = maxPosts - topLinks.length;
  if (remainingNeeded > 0) {
    const scrollRounds = Math.ceil(remainingNeeded / 12);
    for (let i = 0; i < scrollRounds; i++) {
      await client.Runtime.evaluate({ expression: 'window.scrollBy(0, 1500)' });
      await wait(2000);
    }
  }

  const allResult = await client.Runtime.evaluate({
    expression: `
      (() => {
        const links = document.querySelectorAll('a[href*="/p/"], a[href*="/reel/"]');
        const hrefs = [];
        const seen = new Set();
        for (const l of links) {
          const h = l.getAttribute('href');
          if (!seen.has(h)) { seen.add(h); hrefs.push(h); }
          if (hrefs.length >= ${maxPosts}) break;
        }
        return hrefs;
      })()
    `,
    returnByValue: true
  });
  const allLinks = allResult.result.value || [];

  const topSet = new Set(topLinks);
  return allLinks.map(href => ({
    href,
    section: topSet.has(href) ? 'top' : 'recent'
  }));
}

// Collect post links from a profile page
async function collectProfilePosts(client, profileUrl, maxPosts) {
  console.log(`  Navigating to: ${profileUrl}`);
  await client.Page.navigate({ url: profileUrl });
  await wait(5000);
  await client.Runtime.evaluate({ expression: 'window.scrollBy(0, 800)' });
  await wait(2000);

  const postLinks = await client.Runtime.evaluate({
    expression: `
      (() => {
        const links = document.querySelectorAll('a[href*="/p/"], a[href*="/reel/"]');
        const hrefs = [];
        const seen = new Set();
        for (const l of links) {
          const h = l.getAttribute('href');
          if (!seen.has(h)) { seen.add(h); hrefs.push(h); }
          if (hrefs.length >= ${maxPosts}) break;
        }
        return hrefs;
      })()
    `,
    returnByValue: true
  });
  return postLinks.result.value;
}

// =============================================================================
// SINGLE-PASS: scrape + screenshot + audio for ONE post
// =============================================================================
async function processPost(client, href, source) {
  const postId = href.match(/\/(p|reel)\/([\w-]+)/)?.[2] || '';
  const postUrl = href.startsWith('http') ? href : 'https://www.instagram.com' + href;
  const audioFile = join(transcriptsDir, `${postId}.m4a`);
  const postShot = join(postShotsDir, `${postId}.jpg`);
  const ssFile0 = join(hooksDir, `${postId}_0s.jpg`);

  // Skip if fully processed already (post screenshot is the key artifact for Claude)
  if (existsSync(postShot) && existsSync(audioFile) && existsSync(ssFile0)) {
    return { postId, skipped: true };
  }

  // 1. Navigate to post — wait for content to load, then pause video
  await client.Page.navigate({ url: postUrl });
  await wait(2000);

  // Wait for post content to actually render
  for (let attempt = 0; attempt < 20; attempt++) {
    const loaded = await client.Runtime.evaluate({
      expression: `(() => { const spans = document.querySelectorAll('span'); for (const s of spans) { if (s.textContent.match(/^[\\d,.]+[KkMm]?$/) && s.textContent.trim() !== '0') return true; } return false; })()`,
      returnByValue: true
    });
    if (loaded.result.value) break;
    await wait(500);
  }

  // Pause video to capture true first frames
  for (let attempt = 0; attempt < 15; attempt++) {
    const paused = await client.Runtime.evaluate({
      expression: `(() => { const v = document.querySelector('video'); if(v) { v.pause(); v.muted = true; return true; } return false; })()`,
      returnByValue: true
    });
    if (paused.result.value) break;
    await wait(300);
  }
  await wait(1000);

  // 2. FULL-POST SCREENSHOT — this is what Claude reads for engagement + caption.
  //    Captured now, while the page shows the media + likes/comments/caption panel.
  if (!existsSync(postShot)) {
    try {
      const shot = await client.Page.captureScreenshot({ format: 'jpeg', quality: 85 });
      writeFileSync(postShot, Buffer.from(shot.data, 'base64'));
    } catch (e) { /* non-fatal */ }
  }

  // 3. Extract engagement + caption + author from the DOM (baseline / fallback;
  //    Claude refines these from the screenshot in the next pipeline step).
  const data = await client.Runtime.evaluate({
    expression: `
      (() => {
        const result = { url: window.location.href };

        function parseNum(s) {
          if (!s) return 0;
          s = s.trim().replace(/,/g, '');
          const m = s.match(/^([\\d.]+)\\s*([KkMm])?/);
          if (!m) return 0;
          let n = parseFloat(m[1]);
          if (m[2] && m[2].match(/[Kk]/)) n *= 1000;
          if (m[2] && m[2].match(/[Mm]/)) n *= 1000000;
          return Math.round(n);
        }

        const buttons = document.querySelectorAll('button, [role="button"], span[role="button"]');
        for (const btn of buttons) {
          const label = (btn.getAttribute('aria-label') || '').trim();
          const likeMatch = label.match(/^([\\d,.]+[KkMm]?)\\s*like/i);
          if (likeMatch && !result.likes) result.likes = likeMatch[1];
          const viewMatch = label.match(/^([\\d,.]+[KkMm]?)\\s*(?:view|play)/i);
          if (viewMatch && !result.views) result.views = viewMatch[1];
        }

        const allSpans = document.querySelectorAll('span');
        const rawNumbers = [];
        for (const el of allSpans) {
          const t = el.textContent.trim();
          if (t.match(/^[\\d,.]+[KkMm]?$/) && t.length < 15 && t !== '0') {
            rawNumbers.push(t);
          }
          if (t.match(/^Liked by/i) && !result.likesContext) result.likesContext = t.substring(0, 150);
          const likesTextMatch = t.match(/^([\\d,.]+[KkMm]?)\\s+likes?$/i);
          if (likesTextMatch && !result.likes) result.likes = likesTextMatch[1];
          const viewsTextMatch = t.match(/^([\\d,.]+[KkMm]?)\\s+(?:views?|plays?)$/i);
          if (viewsTextMatch && !result.views) result.views = viewsTextMatch[1];
          const commentsMatch = t.match(/^View all ([\\d,.]+[KkMm]?)\\s*comments/i);
          if (commentsMatch && !result.commentsCount) result.commentsCount = commentsMatch[1];
          const commentsAlt = t.match(/^([\\d,.]+[KkMm]?)\\s+comments?$/i);
          if (commentsAlt && !result.commentsCount) result.commentsCount = commentsAlt[1];
        }

        if (result.likesContext) {
          const othersMatch = result.likesContext.match(/and ([\\d,.]+[KkMm]?) others?/i);
          if (othersMatch) result.likes = othersMatch[1];
        }

        const uniqueNums = [...new Set(rawNumbers)];
        result.rawNumbers = uniqueNums.slice(0, 10);
        const significantNums = uniqueNums.filter(n => parseNum(n) > 10);
        significantNums.sort((a, b) => parseNum(b) - parseNum(a));

        const isReel = document.querySelector('video') || window.location.href.includes('/reel/');
        if (isReel && significantNums.length >= 1) {
          if (!result.views) result.views = significantNums[0];
          if (!result.likes && significantNums.length >= 2) result.likes = significantNums[1];
          if (!result.commentsCount && significantNums.length >= 3) result.commentsCount = significantNums[2];
        } else if (significantNums.length >= 1) {
          if (!result.likes) result.likes = significantNums[0];
          if (!result.commentsCount && significantNums.length >= 2) result.commentsCount = significantNums[1];
        }

        const likesNum = parseNum(result.likes);
        const viewsNum = parseNum(result.views);
        const commentsNum = parseNum(result.commentsCount);
        result.engagement = Math.max(likesNum, viewsNum) + commentsNum;

        function isNoise(text) {
          if (!text || text.length < 5) return true;
          if (text.includes('•') && text.length < 200) return true;
          if (/^Original audio/i.test(text)) return true;
          if (text.length < 30 && /^[A-Z][\\w\\s,]+$/.test(text)) return true;
          if (/^@?\\w+Verified/i.test(text) && text.length < 50) return true;
          return false;
        }

        const h1 = document.querySelector('h1');
        const h1Text = h1 ? h1.textContent.trim() : '';
        if (h1Text && !isNoise(h1Text) && h1Text.length > 30) {
          result.caption = h1Text.substring(0, 500);
          result.fullCaption = h1Text;
        }
        if (!result.caption) {
          const spans = document.querySelectorAll('span[dir="auto"]');
          let bestCaption = '';
          for (const s of spans) {
            const t = s.textContent.trim();
            if (t.length > bestCaption.length && t.length > 30 && t.length < 10000 && !isNoise(t)) {
              bestCaption = t;
            }
          }
          if (bestCaption) {
            result.caption = bestCaption.substring(0, 500);
            result.fullCaption = bestCaption;
          }
        }
        if (!result.caption) {
          const allDivs = document.querySelectorAll('div[dir="auto"], span');
          for (const d of allDivs) {
            const t = d.textContent.trim();
            if (t.length > 50 && t.length < 5000 && !isNoise(t)) {
              result.caption = t.substring(0, 500);
              result.fullCaption = t;
              break;
            }
          }
        }
        result.caption = result.caption || '';
        result.fullCaption = result.fullCaption || '';

        result.type = (document.querySelector('video') || window.location.href.includes('/reel/')) ? 'reel' : 'image';
        const timeEl = document.querySelector('time[datetime]');
        result.date = timeEl ? timeEl.getAttribute('datetime') : '';
        result.dateText = timeEl ? timeEl.textContent : '';

        const allPageLinks = document.querySelectorAll('a[href]');
        let foundAuthor = '';
        for (const a of allPageLinks) {
          const href = a.getAttribute('href') || '';
          if (href.length > 2 && href[0] === '/' && href[href.length - 1] === '/' && href.indexOf('/', 1) === href.length - 1) {
            const username = href.slice(1, -1);
            const text = a.textContent.trim().toLowerCase().replace('verified', '');
            if (text === username.toLowerCase()) {
              foundAuthor = username;
              break;
            }
          }
        }
        result.author = foundAuthor;

        return result;
      })()
    `,
    returnByValue: true
  });

  const post = data.result.value;
  if (!post) {
    console.log('failed (page did not load)');
    return { postId, skipped: true };
  }
  post.href = href;
  post.source = source;
  post.postId = postId;
  post.hasPostScreenshot = existsSync(postShot);

  // 4. Video hook frames (reels only) — for the visual-hook display in the report
  if (post.type === 'reel' && !existsSync(ssFile0)) {
    try {
      for (const sec of [0, 1, 2]) {
        const ssFile = join(hooksDir, `${postId}_${sec}s.jpg`);
        await client.Runtime.evaluate({
          expression: `(() => { const v = document.querySelector('video'); if(v) { v.currentTime = ${sec}; } })()`,
        });
        await wait(800);
        const ss = await client.Page.captureScreenshot({ format: 'jpeg', quality: 70 });
        writeFileSync(ssFile, Buffer.from(ss.data, 'base64'));
      }
      post.hasScreenshots = true;
    } catch (e) {
      post.hasScreenshots = false;
    }
  }

  // 5. Audio download (reels only). Instagram now requires cookies even for
  //    public reels, so we pass the browser's cookies (snap chromium profile is
  //    auto-detected; override with "cookiesFrom" in config.json).
  //    Instagram also rate-limits rapid requests ("empty media response"); that's
  //    transient, so we retry with a growing cooldown and space out every reel.
  if (post.type === 'reel' && !existsSync(audioFile)) {
    const cookieSpec = getCookieSpec();
    for (let attempt = 1; attempt <= 3; attempt++) {
      try {
        execSync(
          `python3 -m yt_dlp --cookies-from-browser "${cookieSpec}" --format worstaudio --no-warnings -o "${audioFile}" "${postUrl}"`,
          { timeout: 60000, stdio: 'pipe' }
        );
        if (existsSync(audioFile)) break;
      } catch (e) {
        const msg = (e.stderr?.toString() || '') + (e.stdout?.toString() || '') + (e.message || '');
        if (/No video formats|There is no video/i.test(msg)) break; // image/carousel — no audio
        if (/empty media response/i.test(msg) && attempt < 3) { await wait(30000 * attempt); continue; }
        break;
      }
    }
    post.hasAudio = existsSync(audioFile);
    await wait(7500); // space out reel audio requests to dodge rate-limiting
  }

  return post;
}

// Parse engagement — use pre-computed score, fall back to likes/views
function parseEngagement(post) {
  if (post.engagement && post.engagement > 0) return post.engagement;
  const str = post.views || post.likes || '';
  const match = String(str).match(/([\d,.]+)\s*([KkMm])?/);
  if (!match) return 0;
  let num = parseFloat(match[1].replace(/,/g, ''));
  if (match[2]?.match(/[Kk]/)) num *= 1000;
  if (match[2]?.match(/[Mm]/)) num *= 1000000;
  return num;
}

// =============================================================================
// Main
// =============================================================================
(async () => {
  try {
    const client = await getClient();
    let allPosts = [];

    for (const term of config.searchTerms) {
      console.log(`\n========================================`);
      console.log(`  Searching: "${term}"`);
      console.log(`========================================`);

      const links = await collectSearchPosts(client, term, config.maxPostsPerSearch || 9);
      const topCount = links.filter(l => l.section === 'top').length;
      const recentCount = links.filter(l => l.section === 'recent').length;
      console.log(`  Found ${links.length} posts (${topCount} top, ${recentCount} recent)\n`);

      for (let i = 0; i < links.length; i++) {
        const { href, section } = links[i];
        const postId = href.match(/\/(p|reel)\/([\w-]+)/)?.[2] || '';
        const tag = section === 'top' ? '[TOP]' : '[RECENT]';
        process.stdout.write(`  [${i + 1}/${links.length}] ${tag} ${postId} — `);

        const post = await processPost(client, href, `${section}:${term}`);
        if (post.skipped) {
          console.log('skipped (done)');
        } else {
          const eng = post.engagement || 0;
          const engStr = eng >= 1000 ? `${(eng / 1000).toFixed(1)}K` : eng;
          const shot = post.hasPostScreenshot ? 'shot' : '';
          const audio = post.hasAudio ? 'audio' : '';
          console.log(`[${post.type}] eng:${engStr} ${[shot, audio].filter(Boolean).join(' ')}`);
          allPosts.push(post);
        }
      }
    }

    for (const profileUrl of (config.competitors || [])) {
      const handle = profileUrl.match(/instagram\.com\/([^/]+)/)?.[1] || profileUrl;
      console.log(`\n========================================`);
      console.log(`  Competitor: @${handle}`);
      console.log(`========================================`);

      const links = await collectProfilePosts(client, profileUrl, config.maxCompetitorPosts || 10);
      console.log(`  Found ${links.length} posts\n`);

      for (let i = 0; i < links.length; i++) {
        const postId = links[i].match(/\/(p|reel)\/([\w-]+)/)?.[2] || '';
        process.stdout.write(`  [${i + 1}/${links.length}] ${postId} — `);

        const post = await processPost(client, links[i], `competitor:@${handle}`);
        if (post.skipped) {
          console.log('skipped (done)');
        } else {
          const eng = post.engagement || 0;
          const engStr = eng >= 1000 ? `${(eng / 1000).toFixed(1)}K` : eng;
          console.log(`[${post.type}] eng:${engStr}`);
          allPosts.push(post);
        }
      }
    }

    // Merge with any existing raw-posts.json: posts skipped this run (already
    // captured, possibly hand-corrected in the analysis pass) must survive a
    // re-scrape. Existing corrected data wins over a re-scraped duplicate.
    if (existsSync(outputFile)) {
      try {
        const prev = JSON.parse(readFileSync(outputFile, 'utf8'));
        const prevPosts = prev.posts || [];
        const corrected = new Set(prevPosts.filter(p => p.hook).map(p => p.postId));
        const newIds = new Set(allPosts.map(p => p.postId));
        allPosts = [
          ...allPosts.filter(p => !corrected.has(p.postId)),
          ...prevPosts.filter(p => corrected.has(p.postId) || !newIds.has(p.postId)),
        ];
      } catch (e) { /* unreadable previous file — proceed with this run only */ }
    }

    const seen = new Set();
    const unique = allPosts.filter(p => {
      const key = p.href || p.url;
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });

    unique.sort((a, b) => parseEngagement(b) - parseEngagement(a));

    const output = {
      project: config.name,
      niche: config.niche,
      scrapedAt: new Date().toISOString(),
      searchTerms: config.searchTerms,
      competitors: config.competitors,
      totalPosts: unique.length,
      reels: unique.filter(p => p.type === 'reel').length,
      images: unique.filter(p => p.type === 'image').length,
      posts: unique
    };

    writeFileSync(outputFile, JSON.stringify(output, null, 2));

    console.log(`\n========================================`);
    console.log(`  Scrape complete!`);
    console.log(`  Total: ${unique.length} unique posts`);
    console.log(`  Reels: ${output.reels} | Images: ${output.images}`);
    console.log(`  Post screenshots (for Claude): ${postShotsDir}`);
    console.log(`  Hook frames: ${hooksDir}`);
    console.log(`  Audio: ${transcriptsDir}`);
    console.log(`  Data: ${outputFile}`);
    console.log(`========================================`);

    await client.close();
  } catch (err) {
    console.error('Error:', err.message);
    process.exit(1);
  }
})();
