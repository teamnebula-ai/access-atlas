// Render docs/demo/demo.html frame by frame and encode docs/demo/access-atlas.gif.
// Needs Playwright (engine/ensure-deps.sh) and ffmpeg.  Usage: node docs/demo/record.mjs [fps]
import { createRequire } from 'node:module';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir, homedir } from 'node:os';
import { join, dirname } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { execFileSync } from 'node:child_process';

const here = dirname(fileURLToPath(import.meta.url));
const cache = process.env.ACCESS_ATLAS_CACHE || join(homedir(), '.cache', 'access-atlas');
const { chromium } = createRequire(join(cache, 'package.json'))('playwright');
const fps = Number(process.argv[2] || 12);
const frames = mkdtempSync(join(tmpdir(), 'atlas-demo-'));

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 960, height: 600 } });
await page.goto(pathToFileURL(join(here, 'demo.html')).href);
await page.waitForFunction(() => document.querySelector('#card img').complete);
const duration = await page.evaluate(() => window.DURATION);
const n = Math.ceil(duration * fps);
for (let i = 0; i < n; i++) {
  await page.evaluate(t => window.show(t), i / fps);
  await page.screenshot({ path: join(frames, `f${String(i).padStart(4, '0')}.png`) });
}
await browser.close();

const out = join(here, 'access-atlas.gif');
execFileSync('ffmpeg', ['-y', '-loglevel', 'error', '-framerate', String(fps), '-i', join(frames, 'f%04d.png'),
  '-vf', 'split[a][b];[a]palettegen=max_colors=128:stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle',
  '-loop', '0', out]);
rmSync(frames, { recursive: true, force: true });
console.log(`wrote ${out}: ${n} frames at ${fps} fps`);
