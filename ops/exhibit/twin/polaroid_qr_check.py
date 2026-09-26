"""twin/polaroid_qr_check — 拍立得上那個 QR **真的解得回官網網址嗎**（拿範例 PNG 本身解）。

## 這支在架構裡承重什麼

`qr.py` 自己沒有解碼器（它的誠實邊界 1），`tests/test_qr.py` 驗的是「模組矩陣與 segno
逐 bit 相同」——那證明編碼對，不證明**印在這張圖上、縮到手機大小、被另一支手機拍下來**
之後還解得開。人類 2026-09-26 的要求是後者，所以這一支拿**範例 PNG 本身**丟給外部解碼器
（OpenCV 的 `QRCodeDetector`；不在就明講，不當成過）。

每一張圖跑：

1. `original` —— 原圖；
2. `share_thumb` —— 縮成 540 px 寬（通訊軟體預覽圖常見的大小）；
3. `phone_photo_{10,15,20}cm` —— **模擬**手機在 10／15／20 cm 外拍另一支手機的螢幕
   （物理模型見 `CAMERA`；另加 2° 旋轉＋梯形透視、模糊、對比漂移、雜訊、JPEG q=55）。
   **門檻是 15 cm 以內**（`REQUIRED_WITHIN_CM`）；20 cm 那一格只記錄、量極限用
   （目前的版面在 20 cm 解不開——照實記在 qr_decode.json，不算過）。

**負控制**（量具量得到「解不開」與「解錯」才算數）：

* `neg_blanked` —— 同一張圖把 QR 那一塊塗成紙色 ⇒ **必須解不出任何東西**；
* `neg_other_url` —— 在同一個位置畫一個別的網址 ⇒ 解出來**必須等於那個別的網址**、
  **不等於**官網（證明比對真的在比內容，不是「解得出東西就算過」）。

`--sweep` 另外量「最小模組尺寸」：每模組 5／6／7／8／9 px × 距離 10／15／20／25 cm × 8 個亂數種子 × 兩張範例。

⚠ 誠實邊界：`phone_photo*` 是**模擬**，不是兩支真手機對拍。OpenCV 的解碼器比手機內建
相機（iOS Vision／Google ML Kit）弱，所以這是偏保守的代理量——但它仍然是代理量。
那一格要在展場用真手機掃過一次才算數（裁決檔「上線前要做的事」）。

用法：
    python3 ops/exhibit/twin/polaroid_qr_check.py <png…> --samples samples.json [--out qr_decode.json]
    python3 ops/exhibit/twin/polaroid_qr_check.py --sweep [--samples samples.json] [--out qr_sweep.json]
（要有 `opencv-python-headless`、`numpy`、Pillow；開發機上裝在拋棄式 venv 裡即可）
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import pathlib
import random
import sys
from typing import Any

HERE = pathlib.Path(__file__).resolve()
REPO = HERE.parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from ops.exhibit.twin import polaroid, qr  # noqa: E402

#: 「手機拍手機螢幕」的物理模型（寫死、寫明）。
#: 顯示端：手機頁把拍立得畫成 min(92vw, 420px) 寬；390 pt 寬的螢幕實體約 65.9 mm（iPhone 15 級距）。
#: 拍攝端：掃碼 app 分析的是 1920 px 寬的預覽畫面，水平視角 69°（手機主鏡頭 26 mm 等效）。
CAMERA = {"screen_css_w": 390, "screen_mm_w": 65.9, "polaroid_css_w": min(0.92 * 390, 420),
          "preview_px_w": 1920, "hfov_deg": 69.0}
DISTANCES_CM = (10, 15, 20)
#: 門檻：模擬的「手機拍螢幕」在這個距離以內要解得開。更遠的只記錄（量極限）。
REQUIRED_WITHIN_CM = 15
OTHER_URL = "https://example.org/not-vacant"


def camera_scale(img_w: int, distance_cm: float) -> float:
    """PNG 的 1 px 在相機預覽畫面裡是幾 px。"""
    c = CAMERA
    mm_per_img_px = (c["polaroid_css_w"] / img_w) * (c["screen_mm_w"] / c["screen_css_w"])
    frame_mm = 2 * distance_cm * 10 * math.tan(math.radians(c["hfov_deg"] / 2))
    return mm_per_img_px * c["preview_px_w"] / frame_mm


def _decoder():
    try:
        import cv2  # noqa: F401
        import numpy  # noqa: F401
    except ImportError as exc:
        raise SystemExit(f"沒有解碼器（{exc}）。這一支不會把「沒解」當成「解得開」。")
    import cv2
    return cv2.QRCodeDetector()


def _decode(det: Any, pil_img: Any) -> str | None:
    import cv2
    import numpy as np
    arr = cv2.cvtColor(np.array(pil_img.convert("RGB")), cv2.COLOR_RGB2BGR)
    text, _pts, _ = det.detectAndDecode(arr)
    return text or None


def _perspective_coeffs(src: list[tuple[float, float]], dst: list[tuple[float, float]]):
    """PIL 的 PERSPECTIVE 係數（把 dst 四角對到 src 四角）。解 8×8 線性方程。"""
    rows, rhs = [], []
    for (x, y), (u, v) in zip(src, dst):
        rows.append([u, v, 1, 0, 0, 0, -x * u, -x * v]); rhs.append(x)
        rows.append([0, 0, 0, u, v, 1, -y * u, -y * v]); rhs.append(y)
    n = 8
    a = [r[:] + [rhs[i]] for i, r in enumerate(rows)]
    for c in range(n):
        p = max(range(c, n), key=lambda r: abs(a[r][c]))
        a[c], a[p] = a[p], a[c]
        for r in range(n):
            if r != c and a[r][c]:
                f = a[r][c] / a[c][c]
                for k in range(c, n + 1):
                    a[r][k] -= f * a[c][k]
    return [a[i][n] / a[i][i] for i in range(n)]


def phone_photo(img: Any, scale: float, seed: int) -> Any:
    """模擬「手機拍螢幕」。參數刻意偏壞（寧可模擬得比現場糟）。"""
    from PIL import Image, ImageEnhance, ImageFilter
    rnd = random.Random(seed)
    w, h = img.size
    im = img.convert("RGB").resize((max(1, int(w * scale)), max(1, int(h * scale))),
                                   Image.LANCZOS)
    cw, ch = int(im.width * 1.5), int(im.height * 1.4)
    cam = Image.new("RGB", (cw, ch), (38, 36, 34))      # 手機邊框＋桌面
    cam.paste(im, ((cw - im.width) // 2, (ch - im.height) // 2))
    cam = cam.rotate(2.0, resample=Image.BICUBIC, fillcolor=(38, 36, 34))
    k = 0.04 * cw                                        # 梯形透視：上緣內縮 4%
    coeffs = _perspective_coeffs([(0, 0), (cw, 0), (cw, ch), (0, ch)],
                                 [(k, 0), (cw - k, 0), (cw, ch), (0, ch)])
    cam = cam.transform((cw, ch), Image.PERSPECTIVE, coeffs, Image.BICUBIC,
                        fillcolor=(38, 36, 34))
    cam = cam.filter(ImageFilter.GaussianBlur(0.9))
    cam = ImageEnhance.Brightness(cam).enhance(1.08)
    cam = ImageEnhance.Contrast(cam).enhance(0.82)       # 螢幕反光吃掉一截對比
    px = cam.load()
    for _ in range(cw * ch // 12):                       # 稀疏雜訊
        x, y = rnd.randrange(cw), rnd.randrange(ch)
        r, g, b = px[x, y]
        n = rnd.randint(-22, 22)
        px[x, y] = (max(0, min(255, r + n)), max(0, min(255, g + n)), max(0, min(255, b + n)))
    buf = io.BytesIO()
    cam.save(buf, "JPEG", quality=55)
    return Image.open(io.BytesIO(buf.getvalue()))


def _blank_qr(img: Any, meta: dict[str, Any]) -> Any:
    from PIL import ImageDraw
    im = img.convert("RGB").copy()
    ImageDraw.Draw(im).rectangle(meta["qr_quiet_box"], fill=polaroid.PAPER)
    return im


def _other_qr(img: Any, meta: dict[str, Any], text: str) -> Any:
    from PIL import ImageDraw
    im = _blank_qr(img, meta)
    d = ImageDraw.Draw(im)
    x0, y0, mod = meta["qr_box"][0], meta["qr_box"][1], meta["qr_module_px"]
    for r, row in enumerate(qr.matrix(text)):
        for c, v in enumerate(row):
            if v:
                d.rectangle([x0 + c * mod, y0 + r * mod, x0 + (c + 1) * mod - 1,
                             y0 + (r + 1) * mod - 1], fill=polaroid.QR_DARK)
    return im


def check_png(path: pathlib.Path, meta: dict[str, Any], det: Any) -> dict[str, Any]:
    from PIL import Image
    img = Image.open(path)
    want = polaroid.SITE_URL
    cases: dict[str, Any] = {}

    def run(name: str, im: Any, expect: str | None, required: bool = True,
            **extra: Any) -> None:
        got = _decode(det, im)
        cases[name] = {"decoded": got, "expect": expect, "ok": got == expect,
                       "required": required, "size": list(im.size), **extra}

    run("original", img, want)
    thumb = img.resize((540, int(img.height * 540 / img.width)), Image.LANCZOS)
    run("share_thumb", thumb, want)
    for i, dcm in enumerate(DISTANCES_CM):
        s = camera_scale(img.width, dcm)
        # 20 cm 是**量極限**用的（記下來，不算門檻）：判準是 15 cm 內掃得到。
        run(f"phone_photo_{dcm}cm", phone_photo(img, s, seed=100 + i), want,
            required=dcm <= REQUIRED_WITHIN_CM,
            camera_px_per_module=round(s * meta["qr_module_px"], 2))
    run("neg_blanked", _blank_qr(img, meta), None)
    run("neg_other_url", _other_qr(img, meta, OTHER_URL), OTHER_URL)
    cases["neg_other_url"]["not_site"] = cases["neg_other_url"]["decoded"] != want
    return {"file": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "cases": cases,
            "all_ok": all(c["ok"] for c in cases.values() if c["required"])}


def physical(meta: dict[str, Any]) -> dict[str, Any]:
    """手機上顯示時，QR 一個模組有多大（估算；假設寫在 CAMERA）。"""
    c = CAMERA
    module_mm = meta["qr_module_px"] * (c["polaroid_css_w"] / meta["size"][0]) \
        * (c["screen_mm_w"] / c["screen_css_w"])
    return {"assume": CAMERA, "module_px_in_png": meta["qr_module_px"],
            "qr_modules": meta["qr_modules"], "qr_version": meta["qr_version"],
            "module_mm_on_screen": round(module_mm, 3),
            "code_mm_on_screen": round(module_mm * meta["qr_modules"], 1),
            "camera_px_per_module": {f"{d}cm": round(camera_scale(meta["size"][0], d)
                                                     * meta["qr_module_px"], 2)
                                     for d in (10, 15, 20, 25)}}


def sweep(det: Any, seeds: int = 8,
          samples: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """最小模組尺寸：每模組 m px × 距離 × 種子 ⇒ 解得回官網的比例。

    用哪兩張：`samples`（`samples.json` 的前兩筆：分身真跑寫的那一句＋它的 cast）；
    沒給就用兩張沒有字的卡（一位有姿勢圖 c09、一位沒有 c08）——QR 在白邊右下角，
    那一句寫什麼不影響它，但照片與相框會。
    """
    from PIL import Image
    picks = [{"name": s["file"], "decision": s["decision_by_agent"], "cast_id": s["cast_id"]}
             for s in (samples or [])[:2]] or [
        {"name": "blank_c09", "decision": "", "cast_id": "c09"},
        {"name": "blank_c08", "decision": "", "cast_id": "c08"}]
    rows = []
    for m in (5, 6, 7, 8, 9):
        for si, s in enumerate(picks):
            png, meta = polaroid.compose(
                decision=s["decision"], cast_id=s["cast_id"],
                date_str="2026.09.26", receipt_short="0123abcd", qr_module_px=m,
                _sweep_only=True)
            img = Image.open(io.BytesIO(png))
            for dcm in (10, 15, 20, 25):
                sc = camera_scale(img.width, dcm)
                ok = sum(_decode(det, phone_photo(img, sc, seed=1000 * m + 10 * dcm + k))
                         == polaroid.SITE_URL for k in range(seeds))
                rows.append({"module_px": m, "sample": s["name"], "distance_cm": dcm,
                             "camera_px_per_module": round(sc * m, 2),
                             "decoded": ok, "of": seeds})
    return {"rows": rows}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="拍立得 QR 解碼驗收")
    ap.add_argument("pngs", nargs="*")
    ap.add_argument("--samples", default=None, help="samples.json（拿 meta 用）")
    ap.add_argument("--sweep", action="store_true", help="量最小模組尺寸")
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    det = _decoder()
    import cv2
    out: dict[str, Any] = {"decoder": f"opencv {cv2.__version__} QRCodeDetector",
                           "expect": polaroid.SITE_URL,
                           "honesty": ("phone_photo* 是模擬（物理模型＋旋轉＋透視＋模糊＋對比漂移"
                                       "＋雜訊＋JPEG），不是兩支真手機對拍；OpenCV 比手機內建相機弱，"
                                       "是偏保守的代理量。那一格要在展場實測。")}
    if a.sweep:
        samp = (json.loads(pathlib.Path(a.samples).read_text(encoding="utf-8"))["samples"]
                if a.samples else None)
        out.update(sweep(det, samples=samp))
        ok = True
    else:
        metas = {}
        if a.samples:
            for s in json.loads(pathlib.Path(a.samples).read_text(encoding="utf-8"))["samples"]:
                metas[s["file"]] = s["meta"]
        out["results"] = []
        for p in map(pathlib.Path, a.pngs):
            meta = metas.get(p.name)
            if meta is None:
                raise SystemExit(f"{p.name} 沒有 meta（給 --samples）")
            out["results"].append(check_png(p, meta, det))
        out["physical"] = physical(next(iter(metas.values())))
        out["all_ok"] = ok = all(r["all_ok"] for r in out["results"])
    txt = json.dumps(out, ensure_ascii=False, indent=2) + "\n"
    if a.out:
        pathlib.Path(a.out).write_text(txt, encoding="utf-8")
    print(txt)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
