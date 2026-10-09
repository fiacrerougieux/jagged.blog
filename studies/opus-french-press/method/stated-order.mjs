#!/usr/bin/env node
/**
 * What order a model said the French press filter goes in, beside the order it
 * drew, run by run. Reads only what is already on disk, and runs no model.
 *
 *   node harness/stated-order.mjs [model-substring]     default: opus-5.5
 *
 * Added 2026-10-09. In all five of Opus 5.5's v2 drawing runs, the order its
 * reply listed was the order it drew, right or wrong, so the question is what
 * it says while drawing and not whether it can draw what it says.
 *
 * Said: the first list the model wrote. On svg-french-press-list-first that is
 * the first write to order.txt, taken from the transcript so a later rewrite
 * does not hide it. Otherwise it is the reply's numbered or bulleted lines,
 * read in order, which is where every Opus reply so far has listed the parts.
 * Thinking is not read. "Last" is the list in the final reply, which can
 * differ: on 2026-09-23 run 3 swapped the plates in round 2.
 *
 * Drawn: the published result's order check where there is one, else the
 * order check exploded.py wrote beside the last frame.
 */
import { readdir, readFile } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import { join } from 'node:path';
import { ROOT, RUNS, readJSON, modelSlug } from './lib.mjs';

const CASES = ['svg-french-press', 'svg-french-press-list-first'];
const want = process.argv[2] ?? 'opus-5.5';

const PART = [['spiral', /spiral|spring|coil/i], ['mesh', /mesh|screen/i], ['cross', /cross/i]];
const RIGHT = 'spiral mesh cross';

/** The three filter pieces in the order the lines first name them. */
function orderOf(lines) {
  const seen = [];
  for (const l of lines) {
    const hits = PART.map(([k, rx]) => [k, l.search(rx)]).filter(([k, i]) => i >= 0 && !seen.includes(k)).sort((a, b) => a[1] - b[1]);
    for (const [k] of hits) seen.push(k);
  }
  return seen.length === 3 ? seen.join(' ') : null;
}
// Numbered or bulleted lines, or failing those a line that says "top to
// bottom" and names the pieces inline, as the 2026-10-01 run 2 reply does.
const listLines = (text) => {
  const lines = text.split('\n');
  const list = lines.filter((l) => /^\s*(?:\d+[.)]|[-*•])\s/.test(l));
  return orderOf(list) ? list : lines.filter((l) => /top to bottom|from the top/i.test(l));
};
const verdict = (o) => (o == null ? '?' : o === RIGHT ? 'right' : o === 'cross mesh spiral' ? 'upside down' : 'other');

async function said(seedDir) {
  const p = join(seedDir, 'transcript.jsonl');
  if (!existsSync(p)) return { first: null, last: null };
  const texts = [];
  let file = null;
  for (const line of (await readFile(p, 'utf8')).split('\n')) {
    if (!line.includes('"turn_end"')) continue;
    let m;
    try { m = JSON.parse(line).message; } catch { continue; }
    if (m?.role !== 'assistant') continue;
    for (const b of m.content ?? []) {
      if (b.type === 'text' && b.text?.trim()) texts.push(b.text);
      const a = b.type === 'toolCall' ? b.arguments : null;
      if (!file && a && /order\.txt$/.test(a.path ?? '') && a.content) file = a.content;
    }
  }
  const fromReply = texts.map((t) => orderOf(listLines(t))).filter(Boolean);
  return { first: file ? orderOf(file.split('\n')) : fromReply[0] ?? null, last: fromReply.at(-1) ?? null, fromFile: Boolean(file) };
}

/** Published order verdicts by run, model and seed. */
async function published() {
  const { RESULTS } = await import(join(ROOT, 'src', 'data', 'bench.ts'));
  const dir = join(ROOT, 'src', 'data', 'artifacts');
  const out = new Map();
  for (const f of (await readdir(dir)).filter((x) => x.endsWith('.json'))) {
    const m = await readJSON(join(dir, f));
    const r = m?.run && RESULTS.find((x) => x.artifact === m.name);
    if (r) out.set(`${m.run}/${modelSlug(m.model)}/seed-${m.seed}`, r.checks.order);
  }
  return out;
}

const pub = await published();
const rows = [];
for (const slug of (await readdir(RUNS)).filter((s) => /^\d{4}-/.test(s)).sort()) {
  const result = await readJSON(join(RUNS, slug, 'result.json'));
  if (!CASES.includes(result?.case?.id)) continue;
  for (const m of result.models ?? []) {
    if (!m.model.includes(want)) continue;
    for (const s of m.seeds ?? []) {
      const key = `${slug}/${modelSlug(m.model)}/seed-${s.seed}`;
      const seedDir = join(RUNS, key);
      const meta = await readJSON(join(seedDir, 'meta.json'));
      const last = (meta?.frames ?? []).filter((f) => f.hasPng).at(-1);
      const grade = last ? (last.check ?? await readJSON(join(seedDir, last.dir, 'grade.json'))) : null;
      const drawn = pub.has(key) ? pub.get(key) : grade?.checks?.order ?? null;
      const w = await said(seedDir);
      rows.push({ run: key, case: result.case.id, prompt: result.case.version ?? '', saidFirst: verdict(w.first), saidLast: verdict(w.last), fromFile: w.fromFile, drawn: drawn === true ? 'right' : drawn === false ? 'wrong' : '?' });
    }
  }
}

for (const c of CASES) {
  const rs = rows.filter((r) => r.case === c);
  if (!rs.length) continue;
  console.log(`\n${c}`);
  for (const r of rs) console.log(`  ${r.run.padEnd(62)} said first ${r.saidFirst.padEnd(11)} said last ${r.saidLast.padEnd(11)} drew ${r.drawn}${r.fromFile ? '  (first list from order.txt)' : ''}`);
  const both = rs.filter((r) => r.saidFirst !== '?' && r.drawn !== '?');
  const agree = both.filter((r) => (r.saidLast === 'right' || (r.saidLast === '?' && r.saidFirst === 'right')) === (r.drawn === 'right'));
  console.log(`  drew it right ${rs.filter((r) => r.drawn === 'right').length} of ${rs.filter((r) => r.drawn !== '?').length}; said it right first ${rs.filter((r) => r.saidFirst === 'right').length} of ${rs.filter((r) => r.saidFirst !== '?').length}; drawing matches its last list in ${agree.length} of ${both.length}`);
}
