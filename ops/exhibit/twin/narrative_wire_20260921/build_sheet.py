#!/usr/bin/env python3
"""把順序表與實截組成一張 `order_sheet.html`（file:// 直開，零外部資源）。

「文字稿不算交付」（人類 2026-09-21）⇒ 順序表要**看得到畫面**才算數。

## 這張板子自己會紅

一張只會把手上有的東西排漂亮的板子，缺圖的時候看起來跟齊全一模一樣。
所以這裡把三件事做成會印紅的判準：

  1 **缺圖**：表上有這一拍、`shots/` 裡沒有那一張 ⇒ 紅。
  2 **拼貼**：同一批截圖的 `base_sha256` 出現兩個以上（＝中途有人改了 index.html）
    ⇒ 紅並列出哪幾張是哪一版。有 `null` 也紅——**不知道不等於同一版**。
  3 **溶接沒跑完**：`snap_settled=false` ⇒ 紅（那一張是兩幕疊在一起）。

⚠ 單邊保證：板子綠**不代表**文案是對的，只代表「這些字確實出現在畫面上、
  而且是同一版頁面拍的」。文案對不對是人看的。

用法：python3 build_sheet.py [--shots shots] [--out order_sheet.html]
退出碼：0＝全綠；1＝有紅（**不回 0 假裝齊全**）
"""
from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_ORDER = Path("/Users/cosmopig/Documents/GitHub/.worktrees/"
                     "vacant_hm-narrwire/world3/scenes/narrative_order.json")

# 這一拍 → 那一張。`None` ＝這一拍沒有專屬截圖（理由寫在 why 欄）。
BEAT_SHOT = {
    1: (None, "引導輪播的頭一拍，沒改；它同時是幕 19 回來的那一張"),
    2: (None, "沒改"),
    3: (None, "沒改"),
    4: (None, "沒改"),
    5: ("wired_b05_arrived", None),
    6: ("wired_b06_queued", None),
    "6′-a": (None, "等待形狀那一條軌要真的等（forming 門檻 108 秒、退役 900 秒）；"
                   "?waitdemo=1 演練得到，這一批沒拍"),
    "6′-b": (None, "同上"),
    "6′-c": (None, "同上（要把後端拔掉才觸發 reach=false）"),
    "6′-d": (None, "同上（42 秒）"),
    "6′-e": (None, "同上（900 秒；?waitretire=<秒> 可現場調校）"),
    "6′-x": (None, "同上"),
    7: ("wired_b07w1_waiting", "另有 wired_b07w3_waiting＝兩位以上那一版"),
    "7冷": ("NEG_seamend0_s11", "＝把收尾層關掉那一張（冷句本來就長這樣）"),
    8: ("wired_b08_enter", None),
    9: ("wired_b09_goal", None),
    "9b": ("wired_b09b_nomatch", None),
    10: (None, "沒改"),
    11: (None, "沒改"),
    12: (None, "沒改"),
    13: (None, "沒改"),
    14: (None, "沒改"),
    15: (None, "沒改"),
    16: ("wired_b16_receiptA", None),
    17: ("wired_b17_receiptB", None),
    18: ("wired_b18_one", "另有 wired_b18_many＝兩位以上那一版"),
    19: (None, "＝第 1 拍那一張（引導自己轉回來，沒有新的板）"),
}

EXTRA = [
    ("wired_b07w3_waiting", "幕 7′ 兩位以上"),
    ("wired_b18_many", "幕 18 兩位以上"),
]

BEFORE_AFTER = [
    ("NEG_unwired_s11", "wired_b18_one",
     "s11 的句點", "接線前：烤死字串（冷迴圈那一句）", "接線後：幕 18"),
    ("NEG_unwired_s04", "wired_b08_enter",
     "s04 分身走進來", "接線前：「那是你託付的需求」（對同時在場的另外 11 位是假話）",
     "接線後：指名"),
]

NEG = [
    ("NEG_seam0_s04", "?seam=0", "文案層不掛 ⇒ s04 回到烤死字串"),
    ("NEG_seamend0_s11", "?seamend=0", "收尾層不掛 ⇒ s11 回到「這 371 格會一直重播」"),
    ("NEG_arrive0_wait", "?arrive=0", "抵達層關掉 ⇒ waiting 恆空 ⇒ 幕 7′ 不出現"),
]

CSS = """
:root{--bg:#14110d;--fg:#efe6d8;--dim:#a2968380;--card:#1e1a15;--line:#3a332a;
      --red:#e2564a;--grn:#7fc08a;--amb:#d9a441}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);
     font:15px/1.7 "Noto Sans TC","PingFang TC",system-ui,sans-serif;padding:28px}
h1{font-size:25px;margin:0 0 6px}
h2{font-size:19px;margin:34px 0 10px;border-bottom:1px solid var(--line);padding-bottom:6px}
.lede{color:#c9bda9;max-width:74ch}
.crit{border-left:3px solid var(--amb);padding:8px 14px;margin:14px 0;background:#1b1712}
.beat{background:var(--card);border:1px solid var(--line);border-radius:7px;
      padding:13px 15px;margin:11px 0}
.beat.chg{border-left:4px solid var(--amb)}
.beat.new{border-left:4px solid var(--grn)}
.n{display:inline-block;min-width:44px;font-weight:700;color:var(--amb)}
.sc{color:#8e8474;font-size:13px}
.head{font-size:19px;font-weight:700;margin:7px 0 1px}
.sub{font-size:15px;color:#cfc3af}
.was{color:#8e8474;font-size:13px;margin-top:6px;text-decoration:line-through}
.meta{font-size:12.5px;color:#8e8474;margin-top:7px}
.hon{font-size:13px;color:#b7ab97;margin-top:7px;border-left:2px solid var(--line);
     padding-left:10px;white-space:pre-wrap}
img{width:100%;max-width:780px;border:1px solid var(--line);border-radius:5px;
    display:block;margin:9px 0 3px;background:#000}
.readback{font-size:12.5px;color:#9fd8a8;background:#17201a;border:1px solid #2c3a2f;
          border-radius:5px;padding:7px 10px;margin:5px 0;white-space:pre-wrap}
.red{color:var(--red);font-weight:700}
.grn{color:var(--grn)}
.pair{display:flex;gap:16px;flex-wrap:wrap}
.pair>div{flex:1 1 430px;min-width:330px}
table{border-collapse:collapse;font-size:13px;margin:10px 0}
td,th{border:1px solid var(--line);padding:5px 9px;text-align:left;vertical-align:top}
code{background:#241f19;padding:1px 5px;border-radius:3px;font-size:12.5px}
.glance{background:#1b1712;border:1px solid var(--line);border-radius:7px;
        padding:13px 16px;white-space:pre-wrap;font-size:13.5px;line-height:1.85}
"""


def esc(s) -> str:
    return html.escape("" if s is None else str(s))


def load_shot(shots: Path, name: str):
    j = shots / f"{name}.json"
    # 板子指 JPEG（進版控的那一份）；JPEG 還沒轉出來就退回 PNG，
    # 而且**在圖說上講明白現在看的是哪一種**（有損副本不冒充原件）。
    jpg, png = shots / f"{name}.jpg", shots / f"{name}.png"
    pic = jpg if jpg.is_file() else (png if png.is_file() else None)
    if not j.is_file() or pic is None:
        return None
    try:
        d = json.loads(j.read_text(encoding="utf-8"))
    except Exception as e:
        return {"_broken": f"讀不開：{e}"}
    d["_png"] = f"shots/{pic.name}"
    d["_kind"] = "JPEG（1400 寬，有損；原始 PNG 的 sha256 在 shots_manifest.json）" \
        if pic is jpg else "PNG 原件"
    return d


def shot_block(d, name, reds: list) -> str:
    if d is None:
        reds.append(f"缺圖：{name}")
        return f'<p class="red">🔴 缺圖：shots/{esc(name)}.png（表上有這一拍，目錄裡沒有）</p>'
    if d.get("_broken"):
        reds.append(f"{name}：{d['_broken']}")
        return f'<p class="red">🔴 {esc(d["_broken"])}</p>'
    out = [f'<img src="{esc(d["_png"])}" alt="{esc(name)}">']
    out.append('<div class="readback">從頁面上讀回來：'
               f'大標「{esc(d.get("head"))}」／副標「{esc(d.get("sub"))}」\n'
               f'來源 {esc(d.get("title_ov_source"))}　'
               f'twinseam={esc(d.get("layer_twinseam_loaded"))}　'
               f'seam_ending={esc(d.get("layer_seamending_loaded"))}　'
               f'幕 {esc(d.get("scene_id"))}　檔 {esc(d.get("_kind"))}</div>')
    if d.get("snap_settled") is False:
        reds.append(f"{name}：溶接沒跑完就按了快門")
        out.append('<p class="red">🔴 snap_settled=false：這一張是兩幕疊在一起</p>')
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--shots", type=Path, default=HERE / "shots")
    ap.add_argument("--order", type=Path, default=DEFAULT_ORDER)
    ap.add_argument("--out", type=Path, default=HERE / "order_sheet.html")
    a = ap.parse_args()

    order = json.loads(a.order.read_text(encoding="utf-8"))
    reds: list[str] = []
    bases: dict[str, list[str]] = {}

    body: list[str] = []
    body.append(f"<h1>觀眾的分身接在哪裡——完整順序表 ＋ 每一句的畫面</h1>")
    body.append('<p class="lede">'
                f'narrative_order.json v{esc(order.get("version"))}'
                f'（{esc(order.get("authored"))}）。'
                f'14 個場景、{esc(order.get("beat_count"))} 拍。'
                '這張板子把表跟實截擺在一起——<b>文字稿不算交付</b>。</p>')
    body.append('<div class="crit">判準只有一條（CLAUDE.md）：'
                '<b>「觀眾走到展場前面時，這件事有沒有差別」</b>，不是「稽核員會不會問」。</div>')

    # ── 接線狀態 ──
    w = order.get("wired", {})
    body.append("<h2>0　接線（v3 最大的那個洞）</h2>")
    body.append('<div class="glance">' + esc("\n".join(w.get("_", []))) + "</div>")
    body.append(f'<table><tr><th>項目</th><th>值</th></tr>'
                f'<tr><td>installer</td><td><code>{esc(w.get("installer"))}</code></td></tr>'
                f'<tr><td>順序</td><td>{esc(w.get("order"))}</td></tr>'
                f'<tr><td>fail-closed</td><td>{esc(w.get("fail_closed"))}</td></tr>'
                f'<tr><td>sha256 接線前</td><td><code>{esc(w.get("sha256_before"))}</code></td></tr>'
                f'<tr><td>sha256 接線後</td><td><code>{esc(w.get("sha256_after"))}</code></td></tr>'
                f'</table>')

    # ── 接線前後對照 ──
    body.append("<h2>1　接線前 vs 接線後（同一頁、同一台瀏覽器，只差那三行）</h2>")
    for before, after, title, cap_b, cap_a in BEFORE_AFTER:
        db, da = load_shot(a.shots, before), load_shot(a.shots, after)
        for d in (db, da):
            if d and not d.get("_broken"):
                bases.setdefault(str(d.get("base_sha256")), []).append(d["_png"])
        body.append(f"<h3>{esc(title)}</h3><div class='pair'>")
        body.append(f"<div><p class='meta'>{esc(cap_b)}</p>{shot_block(db, before, reds)}</div>")
        body.append(f"<div><p class='meta'>{esc(cap_a)}</p>{shot_block(da, after, reds)}</div>")
        body.append("</div>")

    # ── 一眼看完的順序 ──
    body.append("<h2>2　一眼看完的順序</h2>")
    body.append('<div class="glance">'
                + esc("\n".join(order.get("order_at_a_glance", []))) + "</div>")

    # ── 逐拍 ──
    body.append("<h2>3　逐拍：表 ＋ 畫面</h2>")
    for b in order.get("beats", []):
        n = b.get("n")
        cls = {"new": "new", "change": "chg"}.get(b.get("state", ""), "")
        body.append(f'<div class="beat {cls}">')
        body.append(f'<span class="n">{esc(n)}</span>'
                    f'<span class="sc">{esc(b.get("scene"))}　'
                    f'{esc(b.get("track"))}　[{esc(b.get("state"))}]　'
                    f'{esc(b.get("what"))}</span>')
        body.append(f'<div class="head">{esc(b.get("head"))}</div>')
        body.append(f'<div class="sub">{esc(b.get("sub"))}</div>')
        if b.get("sub_many"):
            body.append(f'<div class="sub">{esc(b.get("sub_many"))}</div>')
        if b.get("was"):
            wz = b["was"]
            body.append(f'<div class="was">舊：{esc(wz.get("head"))}／{esc(wz.get("sub"))}</div>')
        if b.get("seam_role"):
            body.append(f'<div class="hon">{esc(b["seam_role"])}</div>')
        hon = b.get("honest")
        if hon:
            body.append('<div class="hon">'
                        + esc("\n".join(hon) if isinstance(hon, list) else hon) + "</div>")
        body.append(f'<div class="meta">文案的家：<code>{esc(b.get("copy_from"))}</code>'
                    + (f'　觸發：{esc(b.get("trigger"))}' if b.get("trigger") else "")
                    + "</div>")
        shot, why = BEAT_SHOT.get(n, (None, "（表上沒有登記這一拍要不要有圖）"))
        if shot:
            d = load_shot(a.shots, shot)
            if d and not d.get("_broken"):
                bases.setdefault(str(d.get("base_sha256")), []).append(d["_png"])
            body.append(shot_block(d, shot, reds))
            if why:
                body.append(f'<div class="meta">{esc(why)}</div>')
        else:
            body.append(f'<div class="meta">（沒有專屬截圖：{esc(why)}）</div>')
        body.append("</div>")

    # ── 補充張 ──
    body.append("<h2>4　補充：分支版本</h2>")
    for name, cap in EXTRA:
        d = load_shot(a.shots, name)
        if d and not d.get("_broken"):
            bases.setdefault(str(d.get("base_sha256")), []).append(d["_png"])
        body.append(f'<div class="beat"><div class="head">{esc(cap)}</div>'
                    + shot_block(d, name, reds) + "</div>")

    # ── 負控制 ──
    body.append("<h2>5　負控制：把它關掉，畫面看得出差別</h2>")
    body.append('<p class="lede">三條開關各一張，接線後的同一頁、同一台瀏覽器，'
                '只差網址參數。字不一樣，就證明那兩層真的在承重，'
                '而不是剛好烤死字串長得一樣。</p>')
    for name, flag, cap in NEG:
        d = load_shot(a.shots, name)
        if d and not d.get("_broken"):
            bases.setdefault(str(d.get("base_sha256")), []).append(d["_png"])
        body.append(f'<div class="beat"><div class="head"><code>{esc(flag)}</code></div>'
                    f'<div class="meta">{esc(cap)}</div>'
                    + shot_block(d, name, reds) + "</div>")

    # ── base 稽核 ──
    body.append("<h2>6　這些圖是不是同一版頁面拍的</h2>")
    rows = []
    for sha, pngs in sorted(bases.items(), key=lambda kv: -len(kv[1])):
        rows.append(f"<tr><td><code>{esc(sha)}</code></td><td>{len(pngs)} 張</td>"
                    f"<td>{esc('、'.join(Path(p).stem for p in pngs))}</td></tr>")
    body.append("<table><tr><th>base_sha256</th><th>張數</th><th>哪幾張</th></tr>"
                + "".join(rows) + "</table>")
    unwired = [s for s in bases if s != "None"]
    if "None" in bases:
        reds.append("有截圖的 base_sha256 是 null（不知道不等於同一版）")
        body.append('<p class="red">🔴 有 null：抓不到那一版的 sha。'
                    '<b>不知道不等於同一版。</b></p>')
    if len(unwired) > 2:
        reds.append(f"base_sha256 出現 {len(unwired)} 種（超過『接線前 + 接線後』兩版）")
        body.append(f'<p class="red">🔴 出現 {len(unwired)} 種 base：'
                    '超過「接線前一版 ＋ 接線後一版」，這一批是拼貼的。</p>')
    elif len(unwired) == 2:
        body.append('<p class="grn">✅ 剛好兩版：接線前一版、接線後一版。'
                    '這正是這張板子要對照的那兩版。</p>')
    else:
        body.append('<p class="grn">✅ 同一版。</p>')

    # ── 收尾 ──
    body.append("<h2>7　誠實邊界</h2>")
    body.append('<div class="glance">' + esc(
        "板子綠只代表兩件事：這些字確實出現在畫面上、而且是同一版頁面拍的。\n"
        "它**不代表**文案是對的——那要人看。\n"
        "\n"
        "沒拍到的：等待形狀那一整條軌（幕 6′-a…6′-e、6′-x）。門檻是真的秒數\n"
        "（forming 108 秒、讓格 42 秒、退役 900 秒），要 ?waitdemo=1 加參數演練。\n"
        "**沒拍到就寫沒拍到**，不寫 0、也不用「理論上會出現」頂替。\n"
        "\n"
        "這一批拍的是 127.0.0.1 上的一個獨立工作樹副本（跟展件本尊同一個 commit\n"
        "＋那三行）。展件本尊 8420 那一台要不要跟著接，見報告。") + "</div>")

    ok = not reds
    head_state = ('<p class="grn">✅ 全綠</p>' if ok else
                  '<p class="red">🔴 這張板子是紅的：<br>'
                  + "<br>".join(esc(r) for r in reds) + "</p>")
    body.insert(3, head_state)

    doc = ("<!doctype html><html lang='zh-Hant'><head><meta charset='utf-8'>"
           "<meta name='viewport' content='width=device-width,initial-scale=1'>"
           "<title>觀眾的分身接在哪裡</title><style>" + CSS + "</style></head><body>"
           + "\n".join(body) + "</body></html>")
    a.out.write_text(doc, encoding="utf-8")
    print(f"寫好了：{a.out}（{len(doc)} bytes）")
    if reds:
        print("🔴 紅：")
        for r in reds:
            print("   " + r)
        return 1
    print("✅ 全綠")
    return 0


if __name__ == "__main__":
    sys.exit(main())
