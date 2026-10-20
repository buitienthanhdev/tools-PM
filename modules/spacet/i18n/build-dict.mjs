// Merge i18n/parts/*.json (translation batches) into dict.vi.json.
// overrides.vi.json is applied at serve time by gateway.mjs and always wins.
import fs from 'node:fs';
import { fileURLToPath } from 'node:url';

const dir = fileURLToPath(new URL('./', import.meta.url));
const parts = fs.readdirSync(`${dir}parts`).filter((f) => f.endsWith('.json')).sort();
const dict = {};
let skipped = 0;
for (const file of parts) {
  const part = JSON.parse(fs.readFileSync(`${dir}parts/${file}`, 'utf8'));
  for (const [en, vi] of Object.entries(part)) {
    if (typeof vi !== 'string' || !vi.trim() || vi === en) { skipped++; continue; }
    dict[en] = vi;
  }
}
const sorted = Object.fromEntries(Object.entries(dict).sort(([a], [b]) => a.localeCompare(b)));
fs.writeFileSync(`${dir}dict.vi.json`, JSON.stringify(sorted, null, 1) + '\n');
console.log(`parts ${parts.length}, entries ${Object.keys(sorted).length}, skipped ${skipped}`);
