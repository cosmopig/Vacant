"""r1392（2026-11-10）：NOW.md 紅線「凍結 4 檔＋filing 6 sha256」轉抄守衛（審查指示 #4 機械化）。

背景（vq-el4.80）：NOW.md 紅線段是每輪輪首提示唯一重注入的凍結／受控解凍契約行，逐字引用
  各檔行數／blob（或 sha256）前綴＋g25 filing（6 sha256）；r1550 起反映 11-13 裁決 §3
  受控解凍（extract.py/checks.py 現行基線自磁碟重算，非轉抄）
磁碟上的真實檔已有機械錨（test_reqloop_frozen_anchors.py 釘 repair/extract 之
blob＋行數、filing code 三 sha256；freeze_check 釘 filing 3/3＋3/3），但「NOW.md
引文 vs 磁碟」本身此前無任何機械檢查——簿記覆寫時轉抄錯一個 hash 前綴／行數，
或契約行整行被刪掉，全部仍守衛全綠。這是 H-0 同型（綠燈來自沒量該量的）、
I-4（未測量不是通過）；本輪審查指示 #4 明文要求「寫入 STATE.md 與 NOW.md 的
hash 與數值，必須直接自磁碟實際計算獲取，嚴禁轉抄未經驗證的暫存字串」。

本文件把該約束固化成測試（與 test_reqloop_frozen_anchors.py 同型：純 Python、
violations 清單、負控制先跑）：

  - redline_violations()：解析 NOW.md 紅線契約行，逐條對磁碟核實。hash 族由
    「blob」关键字判定：有＝git blob sha1（sha1(b"blob <len>\\0"+content)，與
    git hash-object 同式）；無＝檔案內容 sha256（filing 同口徑）。filing 聲明
    「（N sha256）」：N 與 filing 實際 sha256 欄位數一致、且每欄位皆非 null
    64-hex（r1288：null pin＝未測量，不得過）。filing 值 vs 磁碟之錨仍在
    anchors／freeze_check（分工，非重疊）。
  - 綠燈測試：現行 NOW.md 紅線與磁碟逐條一致（漂移即紅）。
  - 負控制（4 例）：hash 前綴差一位／行數差一／filing 計數差一／契約行被刪——
    皆必須被判違規，證明綠燈不是空轉。

本文件只讀受測文件與 NOW.md，不寫任何共享狀態；臨時副本走 pytest tmp_path。
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import re

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
NOW = REPO_ROOT / "NOW.md"
FILING = REPO_ROOT / "ops" / "audits" / "g25_all_gates_filing.json"

# 紅線契約行起始（NOW.md 紅線段「凍結／受控解凍」行；前綴精確匹配，不誤傷狀態段）。
# r1550（2026-11-13，票 P20261113_0344-1）：11-13 裁決 §3 受控解凍後，4 檔中 2 檔
# （extract.py/checks.py）為「受控解凍＋現行基線錨」，2 檔（repair.py/run_eval.py）仍凍結；
# 前綴由「凍結 4 檔不改」改為「凍結／受控解凍」以誠實反映制度（內容仍逐條自磁碟核實）。
REDLINE_PREFIX = "- 凍結／受控解凍"

# 紅線引文檔名 → repo 內真實路徑（紅線只引檔名；映射即契約的一部分）。
PATHS = {
    "repair.py": REPO_ROOT / "vacant_network" / "reqloop" / "repair.py",
    "extract.py": REPO_ROOT / "vacant_network" / "reqloop" / "extract.py",
    "checks.py": REPO_ROOT / "vacant_network" / "reqloop" / "checks.py",
    "run_eval.py": REPO_ROOT / "ops" / "reqloop" / "extract" / "run_eval.py",
}


def git_blob_sha1(raw: bytes) -> str:
    """git blob hash = sha1(b"blob <len>\\0" + content)，與 git hash-object 同式。"""
    return hashlib.sha1(b"blob %d\0" % len(raw) + raw).hexdigest()


def _collect_sha256_fields(obj, out: list) -> None:
    """收集 JSON 中所有 key 為 "sha256" 的值（含 null）；其它鍵遞迴。"""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "sha256":
                out.append(v)
            else:
                _collect_sha256_fields(v, out)
    elif isinstance(obj, list):
        for v in obj:
            _collect_sha256_fields(v, out)


def redline_violations(now_path: pathlib.Path = NOW) -> list[str]:
    """NOW.md 紅線契約行 vs 磁碟的違規清單；空列表＝逐條一致。"""
    if not now_path.is_file():
        return [f"NOW.md 不存在: {now_path}"]
    lines = now_path.read_text(encoding="utf-8").splitlines()
    redline = next((l for l in lines if l.startswith(REDLINE_PREFIX)), None)
    if redline is None:
        return [f"NOW.md 紅線缺「{REDLINE_PREFIX}…」契約行（契約消失不是 OK，I-4）"]

    out: list[str] = []
    for name, path in PATHS.items():
        esc = re.escape(name)
        m = re.search(rf"{esc} (\d+) 行／blob ([0-9a-f]{{8}})…", redline)
        if m:
            want_lines, want_blob = int(m.group(1)), m.group(2)
            if not path.is_file():
                out.append(f"{name} 磁碟缺檔: {path}")
                continue
            raw = path.read_bytes()
            got_lines = raw.count(b"\n")
            if got_lines != want_lines:
                out.append(f"{name} 行數漂移: 紅線 {want_lines}, 實際 {got_lines}")
            got_blob = git_blob_sha1(raw)[:8]
            if got_blob != want_blob:
                out.append(f"{name} blob 前綴漂移: 紅線 {want_blob}, 實際 {got_blob}")
            continue
        m = re.search(rf"{esc} ([0-9a-f]{{8}})…", redline)
        if m:
            want_sha = m.group(1)
            if not path.is_file():
                out.append(f"{name} 磁碟缺檔: {path}")
                continue
            got_sha = hashlib.sha256(path.read_bytes()).hexdigest()[:8]
            if got_sha != want_sha:
                out.append(f"{name} sha256 前綴漂移: 紅線 {want_sha}, 實際 {got_sha}")
            continue
        out.append(f"紅線未引用 {name}（契約缺失或格式變了？）")

    m = re.search(r"g25 filing（(\d+) sha256）", redline)
    if m is None:
        out.append("紅線缺「g25 filing（N sha256）」聲明（契約缺失或格式變了？）")
    elif not FILING.is_file():
        out.append(f"filing 不存在: {FILING}")
    else:
        want_n = int(m.group(1))
        fields: list = []
        _collect_sha256_fields(json.loads(FILING.read_text(encoding="utf-8")), fields)
        if len(fields) != want_n:
            out.append(f"filing sha256 欄位數漂移: 紅線 {want_n}, 實際 {len(fields)}")
        for i, v in enumerate(fields):
            if not (isinstance(v, str) and re.fullmatch(r"[0-9a-f]{64}", v)):
                out.append(
                    f"filing sha256[{i}] 非非 null 64-hex（null pin＝未測量，r1288）: {v!r}"
                )
    return out


def _mutate_redline(now_path: pathlib.Path, tmp_path: pathlib.Path,
                    old: str, new: str) -> pathlib.Path:
    """負控制工具：只在紅線契約行內做 old→new 替換（self-checking：舊串不在＝setup 錯）。"""
    text = now_path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    for i, l in enumerate(lines):
        if l.startswith(REDLINE_PREFIX):
            assert old in l, f"負控制 setup 錯：{old!r} 不在紅線行: {l!r}"
            lines[i] = l.replace(old, new, 1)
            dst = tmp_path / "NOW_mutated.md"
            dst.write_text("".join(lines), encoding="utf-8")
            return dst
    raise AssertionError("負控制 setup 錯：找不到紅線契約行")


def _drop_redline(now_path: pathlib.Path, tmp_path: pathlib.Path) -> pathlib.Path:
    """負控制工具：整行刪除紅線契約行（模擬簿記覆寫時契約行被抹掉）。"""
    text = now_path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    kept = [l for l in lines if not l.startswith(REDLINE_PREFIX)]
    assert len(kept) == len(lines) - 1, "負控制 setup 錯：紅線行不存在或不止一行"
    dst = tmp_path / "NOW_dropped.md"
    dst.write_text("".join(kept), encoding="utf-8")
    return dst


# ── 綠燈 ─────────────────────────────────────────────────────────────────────


def test_now_redline_claims_match_disk():
    """綠燈：NOW.md 紅線契約行之行數／hash 前綴／filing 計數聲明與磁碟逐條一致。

    任何轉抄漂移（hash 前綴差一位、行數差一、filing 計數不符、欄位 null）即紅——
    審查指示 #4：簿記 hash 必須直接自磁碟計算，嚴禁轉抄未經驗證的字串。
    """
    v = redline_violations()
    assert v == [], (
        "NOW.md 紅線「凍結 4 檔＋filing」聲明須與磁碟逐條一致"
        "（轉抄筆誤即紅；修正請以 sha256sum／git hash-object／wc -l 重算後改紅線）: "
    ) + "; ".join(v)


# ── 負控制（證明綠燈不是空轉；I-4：未測量不是通過）──────────────────────────


def test_guard_detects_transcribed_hash_drift(tmp_path: pathlib.Path):
    """紅線 blob 前綴差一位（5147f8c3→5147f8c4）必須被抓住——既有守衛都不讀 NOW.md，
    此為本守衛獨立的缺口閉環。"""
    mutated = _mutate_redline(NOW, tmp_path, "5147f8c3", "5147f8c4")
    v = redline_violations(mutated)
    assert any("repair.py" in s and "blob 前綴漂移" in s for s in v), f"未抓出 repair.py hash 轉抄漂移: {v}"
    assert not any("extract.py" in s for s in v), f"extract.py 未改卻被誤判: {v}"


def test_guard_detects_transcribed_line_count_drift(tmp_path: pathlib.Path):
    """紅線行數差一（2795→2794）必須被抓住（wc -l 口徑）。"""
    mutated = _mutate_redline(NOW, tmp_path, "2795 行／blob", "2794 行／blob")
    v = redline_violations(mutated)
    assert any("repair.py" in s and "行數漂移" in s for s in v), f"未抓出 repair.py 行數轉抄漂移: {v}"
    assert not any("blob 前綴漂移" in s for s in v), f"hash 未改卻被誤判: {v}"


def test_guard_detects_filing_count_drift(tmp_path: pathlib.Path):
    """紅線「（6 sha256）」改「（5 sha256）」必須被抓住（filing 實為 6 欄位）。"""
    mutated = _mutate_redline(NOW, tmp_path, "（6 sha256）", "（5 sha256）")
    v = redline_violations(mutated)
    assert any("欄位數漂移" in s and "5" in s for s in v), f"未抓出 filing 計數轉抄漂移: {v}"


def test_guard_detects_missing_redline_line(tmp_path: pathlib.Path):
    """契約行整行被刪必須被抓住——消失的契約不是 OK（I-4）。"""
    dropped = _drop_redline(NOW, tmp_path)
    v = redline_violations(dropped)
    assert any("契約行" in s for s in v), f"未抓出紅線契約行消失: {v}"
