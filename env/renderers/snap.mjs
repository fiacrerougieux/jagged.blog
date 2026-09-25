#!/usr/bin/env node
/**
 * Render browser-native formats to a PNG with headless Chromium.
 *
 *   node /renderers/snap.mjs <kind> IN OUT
 *
 * kinds: html mermaid vegalite echarts wavedrom lottie glsl pdb
 *
 * Animated kinds (html, lottie, glsl) are captured at several moments and laid
 * side by side, because a single still cannot show a sweep, a bounce or an
 * orbit. Page errors and console errors are printed: for these formats they
 * are the renderer's complaint, and the model needs them.
 */
import { createRequire } from 'node:module';
import { readFileSync, writeFileSync, mkdtempSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { join } from 'node:path';

const require = createRequire('/opt/render/');
const puppeteer = require('puppeteer-core');
const LIB = '/opt/render/node_modules';
const [kind, IN, OUT] = process.argv.slice(2);
const src = readFileSync(IN, 'utf8');
const tmp = mkdtempSync('/tmp/snap-');
// Blog export (renderers/export.sh): write media into this directory instead of a still.
const EXPORT = process.env.SNAP_EXPORT;

const page = (body, scripts = []) => `<!doctype html><html><head><meta charset="utf-8">
${scripts.map((s) => `<script src="file://${LIB}/${s}"></script>`).join('\n')}
<style>html,body{margin:0;background:#fff;font-family:sans-serif}#stage{display:inline-block;padding:16px}</style>
</head><body><div id="stage"></div><script>
window.__SRC = ${JSON.stringify(src)};
window.__EXPORT = ${JSON.stringify(Boolean(EXPORT))};
window.__fail = (e) => { window.__error = String(e && e.stack || e); window.__done = true; };
(async () => { try { ${body} } catch (e) { __fail(e); } window.__done = true; })();
</script></body></html>`;

// Evaluate a JS/JSON option file the way people actually write them:
// bare JSON, `option = {...}`, `const option = {...}`, or `export default {...}`.
const EVAL_OBJECT = `
const text = __SRC.replace(/^\\s*export\\s+default\\s+/m, 'option = ');
let value;
try { value = JSON.parse(text); } catch {
  try { value = new Function('let option; return (' + text.trim().replace(/;\\s*$/, '') + ')')(); } catch {
    value = new Function('var option; ' + text + '; return option;')();
  }
}
if (value == null || typeof value !== 'object') throw new Error('Could not find an object in the file (expected JSON, or option = {...}).');
`;

const KINDS = {
  html: { url: `file://${IN}`, frames: [0.4, 1.2, 2.0, 2.8], size: [520, 420] },
  mermaid: { html: page(`
    // Exported SVGs use real <text>: HTML labels vanish in anything that is not a browser.
    mermaid.initialize({ startOnLoad: false, securityLevel: 'loose', ...(__EXPORT ? { htmlLabels: false, flowchart: { htmlLabels: false } } : {}) });
    const { svg } = await mermaid.render('g', __SRC);
    document.getElementById('stage').innerHTML = svg;`, ['mermaid/dist/mermaid.min.js']), size: [1200, 900], fit: true },
  vegalite: { html: page(`
    const spec = JSON.parse(__SRC);
    const vg = spec.$schema && /vega\\/v/.test(spec.$schema) ? spec : vegaLite.compile(spec).spec;
    const view = new vega.View(vega.parse(vg), { renderer: 'svg' });
    document.getElementById('stage').innerHTML = await view.toSVG();`, ['vega/build/vega.min.js', 'vega-lite/build/vega-lite.min.js']), size: [1200, 900], fit: true },
  echarts: { html: page(`${EVAL_OBJECT}
    const el = document.getElementById('stage');
    el.style.width = '1100px'; el.style.height = '760px';
    const chart = echarts.init(el, null, { renderer: 'svg' });
    value.animation = false;
    chart.setOption(value);`, ['echarts/dist/echarts.min.js']), size: [1140, 800] },
  wavedrom: { html: page(`
    const obj = (0, eval)('(' + __SRC + ')');
    const el = document.getElementById('stage');
    el.innerHTML = '<div id="WaveDrom_Display_0"></div>';
    WaveDrom.RenderWaveForm(0, obj, 'WaveDrom_Display_');`, ['wavedrom/skins/default.js', 'wavedrom/wavedrom.min.js']), size: [1200, 700], fit: true },
  lottie: { html: page(`
    const data = JSON.parse(__SRC);
    const el = document.getElementById('stage');
    const w = data.w || 400, h = data.h || 400, s = Math.min(1, 360 / Math.max(w, h));
    el.style.width = w * s + 'px'; el.style.height = h * s + 'px'; el.style.padding = '0'; el.style.outline = '1px solid #ddd';
    window.__anim = lottie.loadAnimation({ container: el, renderer: 'svg', loop: false, autoplay: false, animationData: data });
    await new Promise((r) => { __anim.addEventListener('DOMLoaded', r); setTimeout(r, 3000); });
    console.log('lottie: ' + w + 'x' + h + ', ' + (data.op - data.ip) + ' frames at ' + data.fr + ' fps, ' + (data.layers || []).length + ' layers');`,
    ['lottie-web/build/player/lottie.min.js']), seek: 'lottie', frames: [0, 0.2, 0.4, 0.6, 0.8], size: [420, 420], fit: true },
  glsl: { html: page(`
    const c = document.createElement('canvas'); c.width = __EXPORT ? 960 : 480; c.height = __EXPORT ? 640 : 320;
    document.getElementById('stage').appendChild(c);
    const gl = c.getContext('webgl2', { preserveDrawingBuffer: true });
    if (!gl) throw new Error('WebGL2 unavailable in the renderer');
    const vs = '#version 300 es\\nin vec2 p; void main(){ gl_Position = vec4(p,0.,1.); }';
    const fs = '#version 300 es\\nprecision highp float;\\nuniform vec3 iResolution; uniform float iTime; uniform float iTimeDelta; uniform int iFrame; uniform vec4 iMouse; uniform vec4 iDate;\\nout vec4 _fragColor;\\n' + __SRC + '\\nvoid main(){ vec4 col = vec4(0.); mainImage(col, gl_FragCoord.xy); _fragColor = vec4(col.rgb, 1.); }';
    const sh = (t, s) => { const o = gl.createShader(t); gl.shaderSource(o, s); gl.compileShader(o);
      if (!gl.getShaderParameter(o, gl.COMPILE_STATUS)) throw new Error('GLSL compile error (line numbers include an 8-line Shadertoy header):\\n' + gl.getShaderInfoLog(o)); return o; };
    const pr = gl.createProgram(); gl.attachShader(pr, sh(gl.VERTEX_SHADER, vs)); gl.attachShader(pr, sh(gl.FRAGMENT_SHADER, fs));
    gl.linkProgram(pr); if (!gl.getProgramParameter(pr, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(pr));
    gl.useProgram(pr);
    const b = gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER, b);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1,-1,1,-1,-1,1,1,1]), gl.STATIC_DRAW);
    const loc = gl.getAttribLocation(pr, 'p'); gl.enableVertexAttribArray(loc); gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);
    window.__draw = (t) => { gl.viewport(0, 0, c.width, c.height);
      gl.uniform3f(gl.getUniformLocation(pr, 'iResolution'), c.width, c.height, 1);
      gl.uniform1f(gl.getUniformLocation(pr, 'iTime'), t);
      gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4); gl.finish(); };`), seek: 'glsl', frames: [0, 2.5, 5], size: [512, 352] },
  pdb: { html: page(`
    const el = document.getElementById('stage');
    el.style.width = '560px'; el.style.height = '560px'; el.style.padding = '0'; el.style.position = 'relative';
    const v = $3Dmol.createViewer(el, { backgroundColor: 'white', antialias: true });
    const m = v.addModel(__SRC, 'pdb');
    console.log('pdb: ' + m.selectedAtoms({}).length + ' atoms read');
    v.setStyle({}, { stick: { radius: 0.15 }, sphere: { scale: 0.25 } });
    v.setStyle({ atom: 'CA' }, { cartoon: { color: 'spectrum' }, stick: { radius: 0.15 } });
    v.addLabel; v.zoomTo(); v.render();
    window.__turn = (deg) => { v.rotate(deg, 'y'); v.render(); };`, ['3dmol/build/3Dmol-min.js']), seek: 'pdb', frames: [0, 90], size: [592, 592] },
};

const k = KINDS[kind];

/** Screenshots f0000.png.. of the stage (or the whole page) into a fresh directory, then H.264. */
async function record(tab, count, fps, step, target) {
  const dir = mkdtempSync(join(tmp, 'rec-'));
  const el = target ? await tab.$(target) : (k.fit ? await tab.$('#stage') : null);
  for (let i = 0; i < count; i++) {
    await step(i);
    const path = join(dir, `f${String(i).padStart(4, '0')}.png`);
    if (el) await el.screenshot({ path }); else await tab.screenshot({ path });
  }
  execFileSync('ffmpeg', ['-loglevel', 'error', '-y', '-framerate', String(fps), '-i', join(dir, 'f%04d.png'),
    '-vf', 'scale=trunc(iw/2)*2:trunc(ih/2)*2,format=yuv420p', '-c:v', 'libx264', '-crf', '22', '-preset', 'slow',
    '-movflags', '+faststart', join(EXPORT, 'video.mp4')]);
}

const LIVE = (title, head, body) => `<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>${title}</title>${head}
<style>html,body{margin:0;height:100%;background:#fff;overflow:hidden}#stage{width:100%;height:100%}</style>
</head><body><div id="stage"></div><script>${body}</script></body></html>`;
const json = (x) => JSON.stringify(x).replace(/</g, '\\u003c');

async function exportMedia(tab) {
  if (['mermaid', 'vegalite', 'echarts', 'wavedrom'].includes(kind)) {
    const svg = await tab.evaluate(() => {
      const el = document.querySelector('#stage svg');
      if (!el) return null;
      el.setAttribute('xmlns', 'http://www.w3.org/2000/svg');
      el.setAttribute('xmlns:xlink', 'http://www.w3.org/1999/xlink');
      return new XMLSerializer().serializeToString(el);
    });
    if (svg) writeFileSync(join(EXPORT, 'image.svg'), svg);
    const stage = await tab.$('#stage');
    await (stage && k.fit ? stage : tab).screenshot({ path: join(EXPORT, 'image.png') });
    return;
  }
  if (kind === 'html') {
    writeFileSync(join(EXPORT, 'live.html'), src);
    // CSS animations and transitions can be seeked, which makes the video exact
    // however slow the software renderer is. Anything driven from script plays
    // in real time instead.
    const plan = await tab.evaluate(() => {
      const anims = document.getAnimations();
      if (!anims.length) return null;
      let loop = 0, end = 0;
      for (const a of anims) {
        const t = a.effect.getComputedTiming();
        if (t.iterations === Infinity) loop = Math.max(loop, (t.delay || 0) + t.duration);
        else end = Math.max(end, t.endTime);
      }
      return { seconds: Math.min(8, Math.max(loop, end, 1) / 1000), loops: loop > 0 };
    });
    if (plan) {
      const fps = 30, n = Math.round(plan.seconds * fps);
      await record(tab, n, fps, (i) => tab.evaluate((t) => document.getAnimations().forEach((a) => { a.pause(); a.currentTime = t; }), (i / fps) * 1000));
      console.log(`Note: ${plan.seconds}s of CSS animation, seeked frame by frame.`);
    } else {
      const started = Date.now(); let n = 0;
      const dir = mkdtempSync(join(tmp, 'rt-'));
      while (Date.now() - started < 4000) { await tab.screenshot({ path: join(dir, `f${String(n++).padStart(4, '0')}.png`) }); }
      const fps = Math.max(1, Math.round(n / ((Date.now() - started) / 1000)));
      execFileSync('ffmpeg', ['-loglevel', 'error', '-y', '-framerate', String(fps), '-i', join(dir, 'f%04d.png'),
        '-vf', 'scale=trunc(iw/2)*2:trunc(ih/2)*2,format=yuv420p', '-c:v', 'libx264', '-crf', '22', '-movflags', '+faststart', join(EXPORT, 'video.mp4')]);
      console.log(`Note: no CSS animations to seek, so 4s were recorded in real time at about ${fps} fps; the live embed is smoother.`);
    }
    return;
  }
  if (kind === 'lottie') {
    const { total, fr } = await tab.evaluate(() => ({ total: __anim.totalFrames, fr: __anim.frameRate }));
    const step = Math.max(1, Math.ceil(total / 300));
    await record(tab, Math.ceil(total / step), Math.max(1, Math.round(fr / step)), (i) => tab.evaluate((f) => __anim.goToAndStop(f, true), i * step));
    writeFileSync(join(EXPORT, 'lottie.min.js'), readFileSync(join(LIB, 'lottie-web/build/player/lottie.min.js')));
    writeFileSync(join(EXPORT, 'live.html'), LIVE('Lottie', '<script src="lottie.min.js"></script>',
      `lottie.loadAnimation({ container: document.getElementById('stage'), renderer: 'svg', loop: true, autoplay: true, animationData: ${json(JSON.parse(src))} });`));
    return;
  }
  if (kind === 'glsl') {
    const fps = 30, seconds = Number(process.env.SNAP_SECONDS || 6);
    await record(tab, fps * seconds, fps, (i) => tab.evaluate((t) => __draw(t), i / fps), 'canvas');
    writeFileSync(join(EXPORT, 'live.html'), LIVE('Shader', '', `
const c = document.createElement('canvas'); document.getElementById('stage').appendChild(c);
c.style.width = '100%'; c.style.height = '100%'; c.style.display = 'block';
const gl = c.getContext('webgl2');
const vs = '#version 300 es\\nin vec2 p; void main(){ gl_Position = vec4(p,0.,1.); }';
const fs = '#version 300 es\\nprecision highp float;\\nuniform vec3 iResolution; uniform float iTime; uniform float iTimeDelta; uniform int iFrame; uniform vec4 iMouse; uniform vec4 iDate;\\nout vec4 _fragColor;\\n' + ${json(src)} + '\\nvoid main(){ vec4 col = vec4(0.); mainImage(col, gl_FragCoord.xy); _fragColor = vec4(col.rgb, 1.); }';
const sh = (t, s) => { const o = gl.createShader(t); gl.shaderSource(o, s); gl.compileShader(o); return o; };
const pr = gl.createProgram(); gl.attachShader(pr, sh(gl.VERTEX_SHADER, vs)); gl.attachShader(pr, sh(gl.FRAGMENT_SHADER, fs)); gl.linkProgram(pr); gl.useProgram(pr);
gl.bindBuffer(gl.ARRAY_BUFFER, gl.createBuffer()); gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1,-1,1,-1,-1,1,1,1]), gl.STATIC_DRAW);
const loc = gl.getAttribLocation(pr, 'p'); gl.enableVertexAttribArray(loc); gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);
const u = (n) => gl.getUniformLocation(pr, n); let frame = 0, last = 0;
// Off screen it stops drawing, so a long post is not spinning a GPU for nothing.
let visible = true; new IntersectionObserver(([e]) => { visible = e.isIntersecting; }).observe(c);
function draw(ms) {
  requestAnimationFrame(draw); if (!visible) return;
  const dpr = Math.min(devicePixelRatio, 2), w = c.clientWidth * dpr | 0, h = c.clientHeight * dpr | 0;
  if (c.width !== w || c.height !== h) { c.width = w; c.height = h; }
  gl.viewport(0, 0, w, h); gl.uniform3f(u('iResolution'), w, h, 1); gl.uniform1f(u('iTime'), ms / 1000);
  gl.uniform1f(u('iTimeDelta'), (ms - last) / 1000); gl.uniform1i(u('iFrame'), frame++); last = ms;
  gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
}
requestAnimationFrame(draw);`));
    return;
  }
  if (kind === 'pdb') {
    await record(tab, 72, 24, (i) => (i ? tab.evaluate(() => __turn(5)) : null), '#stage');
    writeFileSync(join(EXPORT, '3Dmol-min.js'), readFileSync(join(LIB, '3dmol/build/3Dmol-min.js')));
    writeFileSync(join(EXPORT, 'live.html'), LIVE('Molecule', '<script src="3Dmol-min.js"></script>', `
const v = $3Dmol.createViewer(document.getElementById('stage'), { backgroundColor: 'white', antialias: true });
v.addModel(${json(src)}, 'pdb');
v.setStyle({}, { stick: { radius: 0.15 }, sphere: { scale: 0.25 } });
v.zoomTo(); v.render(); v.spin('y', 0.4);
// Grabbing the molecule stops the spin, so it can be inspected.
document.getElementById('stage').addEventListener('pointerdown', () => v.spin(false), { once: true });`));
    return;
  }
}
if (!k) { console.error(`snap: unknown kind ${kind}`); process.exit(2); }

/** The contact sheet the model sees: one or several moments side by side. */
async function stills(tab) {
  const shots = [];
  const frames = k.frames ?? [null];
  const started = Date.now();
  for (const [i, f] of frames.entries()) {
    if (k.seek === 'lottie') await tab.evaluate((p) => __anim.goToAndStop(Math.floor(p * (__anim.totalFrames - 1)), true), f);
    else if (k.seek === 'glsl') await tab.evaluate((t) => __draw(t), f);
    else if (k.seek === 'pdb') { if (i) await tab.evaluate((d) => __turn(d), f - frames[i - 1]); }
    else if (f !== null) { const wait = f * 1000 - (Date.now() - started); if (wait > 0) await new Promise((r) => setTimeout(r, wait)); }
    else await new Promise((r) => setTimeout(r, 300));
    const shot = join(tmp, `f${i}.png`);
    const stage = k.url ? null : await tab.$('#stage');
    if (k.fit && stage) await stage.screenshot({ path: shot });
    else await tab.screenshot({ path: shot });
    shots.push(shot);
  }
  if (shots.length === 1) execFileSync('cp', [shots[0], OUT]);
  else execFileSync('convert', [...shots.flatMap((s) => [s]), '-bordercolor', '#bbbbbb', '-border', '1', '+append', OUT]);
  if (frames.length > 1) console.log(`${frames.length} moments, left to right: ${frames.join(', ')}${k.seek === 'lottie' ? ' (fraction of the animation)' : k.seek === 'pdb' ? ' (degrees of rotation)' : ' s'}`);
}

const browser = await puppeteer.launch({
  executablePath: process.env.CHROME_PATH || '/usr/bin/chromium',
  headless: true,
  userDataDir: join(tmp, 'profile'),
  args: ['--no-sandbox', '--disable-dev-shm-usage', '--use-angle=swiftshader', '--enable-unsafe-swiftshader',
    '--ignore-gpu-blocklist', '--allow-file-access-from-files', '--disable-crash-reporter', '--no-first-run'],
});
const problems = [];
let exitCode = 0;
try {
  const tab = await browser.newPage();
  await tab.setViewport({ width: k.size[0] + (EXPORT && kind === 'glsl' ? 480 : 0), height: k.size[1] + (EXPORT && kind === 'glsl' ? 320 : 0),
    deviceScaleFactor: EXPORT && kind !== 'glsl' ? 2 : 1 });
  tab.on('pageerror', (e) => problems.push(`page error: ${e.message}`));
  tab.on('console', (m) => {
    if (m.type() === 'error') problems.push(`console error: ${m.text()}`);
    else if (m.type() === 'log' && /^(lottie|pdb):/.test(m.text())) console.log(m.text());
  });
  if (k.url) {
    await tab.goto(k.url, { waitUntil: 'load', timeout: 20000 });
  } else {
    const file = join(tmp, 'page.html');
    writeFileSync(file, k.html);
    await tab.goto(`file://${file}`, { waitUntil: 'load', timeout: 20000 });
    await tab.waitForFunction('window.__done === true', { timeout: 30000 });
    const err = await tab.evaluate(() => window.__error);
    if (err) throw new Error(err);
  }

  if (EXPORT) await exportMedia(tab);
  else await stills(tab);
} catch (e) {
  problems.unshift(e.message);
  exitCode = 1;
} finally {
  await browser.close();
}
if (problems.length) console.error([...new Set(problems)].slice(0, 12).join('\n'));
process.exit(exitCode);
