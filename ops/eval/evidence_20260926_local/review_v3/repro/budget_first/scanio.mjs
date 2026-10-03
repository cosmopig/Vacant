import { BUDGET_RE } from "./re.js";
import { readFileSync } from "node:fs";
const g = new RegExp(BUDGET_RE.source, "gi");
const lines = readFileSync(process.argv[2], "utf8").split("\n").filter(Boolean);
const seen = new Map(); let n=0;
for (const l of lines) {
  let o; try { o = JSON.parse(l); } catch (e) { continue; }
  if (!String(o.tag||"").startsWith("v3local")) continue;
  const ms = (o.request_from_agent||{}).messages || [];
  const sys = ms.filter(m => m.role === "system" || m.role === "developer").map(m => typeof m.content === "string" ? m.content : JSON.stringify(m.content)).join("\n");
  n++;
  const matches = [...sys.matchAll(g)].map(m => m[0]);
  const k = JSON.stringify(matches);
  seen.set(k, (seen.get(k)||0)+1);
}
console.log("v3local requests:", n);
for (const [k,v] of seen) console.log(v, k);
