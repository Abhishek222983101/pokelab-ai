#!/usr/bin/env node
/**
 * P12.3 — real performance instrumentation probe (AC-22). Drives two
 * real browser pages against an already-running labd (/console for
 * panel-render counts, /game for frame-time — only the game page runs
 * the Phaser loop), submits real jobs over the real brain socket to
 * generate real event traffic, lets each page render it for a while,
 * then pulls the real window.__pokelabPerf() snapshot (web/lib/perf.ts)
 * out of each live page and merges them into var/reports/perf.json. No
 * numbers here are synthesized — every one came out of a real running
 * system.
 *
 * Usage (from web/):
 *   LABD_URL=http://127.0.0.1:7700 LABD_BRAIN_SECRET=... node scripts/perf_probe.mjs
 */
import { chromium } from "playwright";
import WebSocket from "ws";
import { writeFileSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const LABD_URL = process.env.LABD_URL ?? "http://127.0.0.1:7700";
const BRAIN_SECRET = process.env.LABD_BRAIN_SECRET;
const DURATION_S = Number(process.env.PERF_PROBE_DURATION_S ?? 15);

if (!BRAIN_SECRET) {
  console.error("LABD_BRAIN_SECRET is required (same secret labd was started with)");
  process.exit(1);
}

function wsUrl(path) {
  return LABD_URL.replace(/^http/, "ws") + path;
}

async function submitJob(kit, config) {
  return new Promise((resolve, reject) => {
    const ws = new WebSocket(wsUrl("/internal/brain"), { headers: { Authorization: `Bearer ${BRAIN_SECRET}` } });
    ws.on("open", () => ws.send(JSON.stringify({ type: "job_submit", req: kit, kit, config })));
    ws.on("message", (data) => {
      const msg = JSON.parse(data.toString());
      if (msg.type === "job_accepted") {
        resolve(msg.job_id);
        setTimeout(() => ws.close(), 500);
      }
    });
    ws.on("error", reject);
    setTimeout(() => reject(new Error(`job_submit(${kit}) timed out`)), 10_000);
  });
}

async function submitRealTraffic() {
  const jobIds = [];
  for (const [kit, config] of [
    ["smoke", { n_steps: 2000 }],
    ["materials", { n_estimators: 40, trees_per_step: 10 }],
    ["smoke", { n_steps: 2000 }],
  ]) {
    try {
      jobIds.push(await submitJob(kit, config));
    } catch (e) {
      console.warn(`submit(${kit}) failed, continuing: ${e.message}`);
    }
  }
  return jobIds;
}

// [BUG FOUND & FIXED]: an earlier version submitted jobs BEFORE the page
// connected, so their events were already sitting in the store by the
// time the page did its since=0 replay — "latency" then measured
// replay-catch-up time (seconds) instead of real live propagation (what
// AC-22 actually asks about). Fix below: connect, settle, RESET the
// buffer, then submit — every recorded sample is a genuinely live event.
async function probePage(browser, path, jobIds) {
  const page = await browser.newPage();
  await page.goto(`${LABD_URL}${path}`);
  await page.waitForTimeout(1000);
  await page.evaluate(() => window.__pokelabPerfReset());
  await page.waitForTimeout(DURATION_S * 1000);
  const snapshot = await page.evaluate(() => window.__pokelabPerf());
  await page.close();
  return snapshot;
}

async function main() {
  const browser = await chromium.launch();

  // the console page connects+settles first, THEN real traffic starts,
  // so both pages see the same live jobs
  const consolePromise = (async () => {
    const page = await browser.newPage();
    await page.goto(`${LABD_URL}/console`);
    await page.waitForTimeout(1000);
    await page.evaluate(() => window.__pokelabPerfReset());
    return page;
  })();
  const gamePromise = (async () => {
    const page = await browser.newPage();
    await page.goto(`${LABD_URL}/game`);
    await page.waitForTimeout(1000);
    await page.evaluate(() => window.__pokelabPerfReset());
    return page;
  })();
  const [consolePage, gamePage] = await Promise.all([consolePromise, gamePromise]);

  const jobIds = await submitRealTraffic();
  console.log(`submitted ${jobIds.length} real jobs:`, jobIds);
  console.log(`watching both real pages for ${DURATION_S}s while those jobs run...`);
  await new Promise((r) => setTimeout(r, DURATION_S * 1000));

  const consoleSnap = await consolePage.evaluate(() => window.__pokelabPerf());
  const gameSnap = await gamePage.evaluate(() => window.__pokelabPerf());
  await browser.close();

  // event latency + panel counts come from console (it has the DOM
  // panels); frame time comes from game (it has the Phaser loop) —
  // merge rather than pick one, since neither page alone has both
  const merged = {
    eventLatencyMs: consoleSnap.eventLatencyMs,
    frameTimeMs: gameSnap.frameTimeMs,
    panelRenderCounts: consoleSnap.panelRenderCounts,
  };

  const report = {
    probed_at: new Date().toISOString(),
    labd_url: LABD_URL,
    jobs_submitted: jobIds,
    duration_s: DURATION_S,
    ...merged,
    ac_22: {
      target_p95_ms: 150,
      measured_p95_ms: merged.eventLatencyMs.p95,
      pass: merged.eventLatencyMs.p95 !== null && merged.eventLatencyMs.p95 < 150,
    },
  };

  const outDir = join(__dirname, "..", "..", "var", "reports");
  mkdirSync(outDir, { recursive: true });
  const outPath = join(outDir, "perf.json");
  writeFileSync(outPath, JSON.stringify(report, null, 2));
  console.log(`wrote ${outPath}`);
  console.log(JSON.stringify(report, null, 2));
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
