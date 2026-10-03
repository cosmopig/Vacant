import { BUDGET_RE } from "./re.js";
import { readFileSync } from "node:fs";
const g = new RegExp(BUDGET_RE.source, "gi");
for (const f of process.argv.slice(2)) {
  let t; try { t = readFileSync(f, "utf8"); } catch (e) { continue; }
  const ms = [...t.matchAll(g)].map(m => m[0]);
  if (ms.length) console.log(f, JSON.stringify(ms.slice(0,5)));
}
