#!/usr/bin/env python3
"""D2′ 材料產生器：虛構產品頁的來源組、三個週期的事實級改動、封存的改動清單。

一組（set）＝1 張索引頁＋5 張產品頁。每張產品頁有 9 個屬性（散文＋規格表＋版本紀錄），
報告範本問其中 4 個屬性 × 5 個產品＝20 條宣稱。

每個週期（1..3）：
- 「事實改動」：挑 1 張還沒改過的產品頁（5 張的 20%），改它 2 個**被問到的**屬性（宣稱受影響）。
- 「雜訊改動」：挑另 1 張產品頁，只改**沒被問到的**屬性（頁面雜湊變了，宣稱不受影響）。
版本號改動時，舊版本移進版本紀錄（舊值仍留在頁面上，真實網站就是這樣）。

輸出（--out 底下）：
  sets/<set>/cycle_<k>/site/{index.html,p1.html..p5.html}   k=0..3，每個週期的完整網站
  sets/<set>/template.md                                       給 agent 的空白報告
  manifest.json      全部的真值與改動（**封存**：agent 看不到；只把它的 sha256 寫進計畫）
  manifest.sha256

決定性：同一個 --seed 產生逐位元相同的輸出。純標準函式庫。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import random

SYL_A = ["Nim", "Vor", "Kel", "Zan", "Quil", "Mer", "Tor", "Sav", "Pell", "Dra", "Ost", "Lun", "Fen", "Gal", "Rho", "Bex"]
SYL_B = ["bra", "eta", "ix", "ora", "una", "ent", "ari", "ello", "oss", "ivo", "ance", "yra", "et", "ondo"]
NOUN = ["Cloud", "Desk", "Flow", "Base", "Sync", "Works", "Hub", "Stack", "Ledger", "Board"]
CITIES = ["Tallinn", "Porto", "Leipzig", "Gdansk", "Valencia", "Tampere", "Graz", "Bergen", "Lyon", "Brno",
          "Turku", "Ghent", "Malmo", "Utrecht", "Aarhus", "Cork"]
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]

# 屬性：key, 標籤, 產生器, 改動器
ATTRS = ["price", "version", "team", "rate", "storage", "trial", "founded", "city", "support"]
LABEL = {"price": "monthly price per seat", "version": "latest version", "team": "maximum team size",
         "rate": "API rate limit", "storage": "storage per user", "trial": "free trial length",
         "founded": "year founded", "city": "headquarters city", "support": "support hours"}
ASKABLE = ["price", "version", "team", "rate", "storage", "trial"]   # 會變的屬性才會被問
NOISE = ["support", "storage", "trial", "team", "rate", "price"]     # 雜訊改動從「沒被問到的」裡挑


def fmt(attr: str, v) -> str:
    if attr == "price":
        return f"${v}"
    if attr == "version":
        return "v" + ".".join(map(str, v))
    if attr == "team":
        return f"{v:,} members"
    if attr == "rate":
        return f"{v:,} requests per minute"
    if attr == "storage":
        return f"{v} GB"
    if attr == "trial":
        return f"{v} days"
    if attr == "founded":
        return str(v)
    if attr == "city":
        return v
    if attr == "support":
        return v
    raise KeyError(attr)


def gen_value(attr: str, rng: random.Random):
    if attr == "price":
        return rng.choice([9, 12, 14, 18, 19, 24, 29, 32, 39, 44, 49, 59, 64, 79])
    if attr == "version":
        return [rng.randint(1, 9), rng.randint(0, 19), rng.randint(0, 12)]
    if attr == "team":
        return rng.choice([25, 40, 50, 75, 120, 150, 200, 250, 400, 500, 750, 1000, 2500])
    if attr == "rate":
        return rng.choice([60, 90, 120, 300, 450, 600, 900, 1200, 1800, 2400, 3000])
    if attr == "storage":
        return rng.choice([5, 10, 15, 20, 30, 50, 75, 100, 250])
    if attr == "trial":
        return rng.choice([7, 10, 14, 21, 30, 45, 60])
    if attr == "founded":
        return rng.randint(2004, 2021)
    if attr == "city":
        return rng.choice(CITIES)
    if attr == "support":
        a, b = sorted(rng.sample(range(6, 22), 2))
        return f"{rng.choice(DAYS)}–{rng.choice(['Friday', 'Saturday', 'Sunday'])}, {a:02d}:00–{b:02d}:00 UTC"
    raise KeyError(attr)


def change_value(attr: str, old, rng: random.Random):
    for _ in range(100):
        if attr == "version":
            a, b, c = old
            new = rng.choice([[a, b, c + 1], [a, b + 1, 0], [a + 1, 0, 0]])
        else:
            new = gen_value(attr, rng)
        if new != old and fmt(attr, new) != fmt(attr, old):
            return new
    raise RuntimeError("no change found")


def render_product(name: str, a: dict, history: list, rng_seed: int) -> str:
    r = random.Random(rng_seed)      # 版面固定（同一頁各週期只差值）
    opener = r.choice(["is a collaboration suite for small teams", "is a workflow tool used by agencies",
                       "is a shared workspace for operations teams", "is a planning tool for distributed teams"])
    p1 = (f"<p>{name} {opener}. The company was founded in {fmt('founded', a['founded'])} and is headquartered "
          f"in {fmt('city', a['city'])}. The current release is {fmt('version', a['version'])}.</p>")
    p2 = (f"<p>Plans start at {fmt('price', a['price'])} per seat per month, billed annually. A single workspace "
          f"supports up to {fmt('team', a['team'])}, and every user gets {fmt('storage', a['storage'])} of storage. "
          f"New accounts get a free trial of {fmt('trial', a['trial'])}.</p>")
    p3 = (f"<p>The public API allows {fmt('rate', a['rate'])} per token. Human support is available "
          f"{fmt('support', a['support'])}.</p>")
    rows = "".join(f"<tr><td>{LABEL[k]}</td><td>{fmt(k, a[k])}</td></tr>" for k in ATTRS)
    hist = "".join(f"<li>{fmt('version', v)}</li>" for v in history) or "<li>(none listed)</li>"
    return (f"<!doctype html><html><head><meta charset=\"utf-8\"><title>{name}</title></head><body>\n"
            f"<h1>{name}</h1>\n{p1}\n{p2}\n{p3}\n<h2>Specifications</h2>\n<table>{rows}</table>\n"
            f"<h2>Previous versions</h2>\n<ul>{hist}</ul>\n</body></html>\n")


def render_index(set_id: str, names: list[str]) -> str:
    items = "".join(f"<li><a href=\"p{i + 1}.html\">{n}</a> — p{i + 1}.html</li>" for i, n in enumerate(names))
    return (f"<!doctype html><html><head><meta charset=\"utf-8\"><title>Directory {set_id}</title></head><body>\n"
            f"<h1>Product directory</h1>\n<p>Each product has its own page.</p>\n<ul>{items}</ul>\n</body></html>\n")


def make_set(set_id: str, rng: random.Random) -> dict:
    names: list[str] = []
    while len(names) < 5:
        n = f"{rng.choice(SYL_A)}{rng.choice(SYL_B)} {rng.choice(NOUN)}"
        if n not in names and n.split()[0] not in {x.split()[0] for x in names}:
            names.append(n)
    asked = sorted(rng.sample(ASKABLE, 4), key=ASKABLE.index)
    prods = []
    for n in names:
        a = {k: gen_value(k, rng) for k in ATTRS}
        hist = []
        v = list(a["version"])
        for _ in range(rng.randint(1, 3)):          # 版本紀錄：比現在舊的幾版
            v = [v[0], max(v[1] - rng.randint(1, 3), 0), rng.randint(0, 9)] if v[1] > 0 else [max(v[0] - 1, 0), rng.randint(5, 15), rng.randint(0, 9)]
            if v != a["version"] and v not in hist:
                hist.append(list(v))
        prods.append({"name": n, "attrs": a, "history": hist, "layout_seed": rng.randint(0, 10**9)})
    noise_attrs = [k for k in NOISE if k not in asked]
    cycles = []
    fact_pool = list(range(5))
    rng.shuffle(fact_pool)
    for k in (1, 2, 3):
        fp = fact_pool[k - 1]
        npg = rng.choice([i for i in range(5) if i != fp])
        changed = sorted(rng.sample(asked, 2), key=asked.index)
        cycles.append({"cycle": k, "fact_page": fp, "fact_attrs": changed,
                       "noise_page": npg, "noise_attr": rng.choice(noise_attrs)})
    return {"set": set_id, "names": names, "asked": asked, "products": prods, "cycles": cycles}


def template(s: dict) -> str:
    lines = ["# Product comparison", "", "Fill in every ____ with the value exactly as the product's page states it.", ""]
    for i, n in enumerate(s["names"]):
        lines.append(f"## {n}")
        for k in s["asked"]:
            lines.append(f"- {n} — {LABEL[k]}: ____")
        lines.append("")
    return "\n".join(lines)


def build(seed: int, n_sets: int, out: pathlib.Path) -> dict:
    rng = random.Random(seed)
    manifest = {"schema": "vacant.d2.manifest/1", "seed": seed, "n_sets": n_sets, "sets": []}
    for si in range(n_sets):
        set_id = f"s{si + 1:02d}"
        s = make_set(set_id, rng)
        sdir = out / "sets" / set_id
        (sdir).mkdir(parents=True, exist_ok=True)
        (sdir / "template.md").write_text(template(s), encoding="utf-8")
        state = [{"attrs": dict(p["attrs"]), "history": [list(h) for h in p["history"]]} for p in s["products"]]
        truth = []          # truth[k][claim_id] = 字串值
        pages = []          # pages[k][page] = sha256
        crng = random.Random(seed * 1000 + si)
        for k in range(4):
            if k > 0:
                c = s["cycles"][k - 1]
                st = state[c["fact_page"]]
                for at in c["fact_attrs"]:
                    old = st["attrs"][at]
                    st["attrs"][at] = change_value(at, old, crng)
                    if at == "version":
                        st["history"].insert(0, list(old))
                ns = state[c["noise_page"]]
                ns["attrs"][c["noise_attr"]] = change_value(c["noise_attr"], ns["attrs"][c["noise_attr"]], crng)
            site = sdir / f"cycle_{k}" / "site"
            site.mkdir(parents=True, exist_ok=True)
            (site / "index.html").write_text(render_index(set_id, s["names"]), encoding="utf-8")
            ph = {"index.html": hashlib.sha256((site / "index.html").read_bytes()).hexdigest()}
            for i, p in enumerate(s["products"]):
                html = render_product(p["name"], state[i]["attrs"], state[i]["history"], p["layout_seed"])
                (site / f"p{i + 1}.html").write_text(html, encoding="utf-8")
                ph[f"p{i + 1}.html"] = hashlib.sha256(html.encode()).hexdigest()
            pages.append(ph)
            truth.append({f"p{i + 1}.{at}": fmt(at, state[i]["attrs"][at])
                          for i in range(5) for at in s["asked"]})
        s["claims"] = [{"id": f"p{i + 1}.{at}", "product": s["names"][i], "attr": at, "label": LABEL[at],
                        "source_page": f"p{i + 1}.html",
                        "template_line": f"- {s['names'][i]} — {LABEL[at]}: "} for i in range(5) for at in s["asked"]]
        s["truth"] = truth
        s["page_sha256"] = pages
        manifest["sets"].append(s)
    body = json.dumps(manifest, ensure_ascii=False, indent=1, sort_keys=True)
    (out / "manifest.json").write_text(body, encoding="utf-8")
    h = hashlib.sha256(body.encode()).hexdigest()
    (out / "manifest.sha256").write_text(h + "\n")
    return {"manifest_sha256": h, "sets": n_sets}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--sets", type=int, required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    out = pathlib.Path(a.out).expanduser()
    if out.exists() and any(out.iterdir()):
        raise SystemExit(f"refusing to overwrite non-empty {out}")
    out.mkdir(parents=True, exist_ok=True)
    print(json.dumps(build(a.seed, a.sets, out)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
