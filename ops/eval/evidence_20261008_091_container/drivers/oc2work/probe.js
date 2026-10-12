import { appendFileSync } from "node:fs";
const OUT = "/tmp/probe_ctx.txt";
function desc(o, depth, seen) {
  if (o === null || o === undefined) return String(o);
  if (typeof o === "function") return "fn";
  if (typeof o !== "object") return typeof o;
  if (seen.has(o) || depth > 2) return "obj";
  seen.add(o);
  const keys = new Set(Object.keys(o));
  let p = Object.getPrototypeOf(o);
  while (p && p !== Object.prototype) { for (const k of Object.getOwnPropertyNames(p)) if (k !== "constructor") keys.add(k); p = Object.getPrototypeOf(p); }
  const r = {};
  for (const k of keys) { try { r[k] = desc(o[k], depth + 1, seen); } catch (e) { r[k] = "err"; } }
  return r;
}
async function setup(ctx) {
  appendFileSync(OUT, JSON.stringify(desc(ctx, 0, new Set()), null, 1) + "\n");
  return async () => {};
}
export default { id: "probe", setup };
