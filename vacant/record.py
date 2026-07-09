"""record — 一次 run 的最小證據包：打包（pack）與核對（check）。承重 17 §P0-2。

這支在架構裡承重「記錄基建」：把一次實驗 run 落盤成**別人不必信任你、只憑磁碟就能
複核**的證據集合（規格見 docs/RECORD_SPEC.md）。任何進統計的 run 都要先過 `check`；
缺任一必要項＝該 run 記錄層 infra_void，不得進統計（引 09 §3.5 的 retry×4 /
infra_void / parse_void 紀律，即 CLAUDE.md 鐵律 3）。

兩個入口：
  - pack(run_dir, extra_meta)：就地整理成 RECORD_SPEC 佈局——生成 manifest.json
    （抓 git commit / pip freeze / platform / utc；併入 extra_meta）；對居民 logbook
    離線重驗簽章鏈、把人可讀輸出寫進 chain_verify.txt；對 trust_cards/*.json 逐張
    獨立驗簽、輸出寫 card_verify.txt；確保 anomalies.md 存在；最後生成 SHA256SUMS
    （排除自身）。回傳 manifest dict。
  - check(run_dir)：對照 RECORD_SPEC 檢查必要項、manifest 欄位、SHA256SUMS 逐檔重驗、
    chain_verify/card_verify 非空且不含 FAIL。缺項/問題全部點名，回 (ok, problems)。

誠實邊界（規格的一部分，改碼保留）：pack 只能保證「這個包是完整且自洽的」（必要項齊、
雜湊自洽、驗證輸出落盤），**不能保證「內容是真的」**——內容真實性由簽章鏈
（chain_verify.txt）與稽核（card_verify.txt）承擔，不是打包器的責任。SHA256SUMS
偵測（detects）落盤後的竄改，不預防（not prevents）。

runtime 依賴只有 stdlib＋repo 既有模組（logbook / trustcard / identity）。
"""

from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .identity import PublicIdentity
from .logbook import Logbook
from .trustcard import verify_trust_card

# --- RECORD_SPEC 常數（單一真相；docs/RECORD_SPEC.md §2/§3）------------------
MANIFEST_NAME = "manifest.json"
SUMS_NAME = "SHA256SUMS"
CHAIN_VERIFY_NAME = "chain_verify.txt"
CARD_VERIFY_NAME = "card_verify.txt"
ANOMALIES_NAME = "anomalies.md"
LEDGER_NAME = "ledger_events.jsonl"
WIRE_NAME = "wire.jsonl"
MODEL_IO_NAME = "model_io.jsonl"
TRUST_CARDS_DIR = "trust_cards"

# 恆須存在的必要項（缺＝記錄層 infra_void）
REQUIRED_FILES = (MANIFEST_NAME, LEDGER_NAME, CHAIN_VERIFY_NAME, ANOMALIES_NAME, SUMS_NAME)
# 可缺、但缺席須在 manifest.missing 附理由的項
OPTIONAL_WITH_REASON = (WIRE_NAME, MODEL_IO_NAME)
# manifest 必要欄位
REQUIRED_MANIFEST_FIELDS = (
    "repo_commit", "pip_freeze", "os", "python", "model_id", "endpoint",
    "no_think", "seeds", "machine", "utc_start", "utc_end", "trust_arm", "scripts",
)

ANOMALIES_EMPTY_NOTE = (
    "（未登記異常——若 run 有異常而此檔為空，屬記錄違規）\n"
)


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _git_commit(run_dir: Path) -> str | None:
    """抓 repo_commit；抓不到回 None（呼叫端記入 missing、值填 'unknown'）。"""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=str(run_dir),
            capture_output=True, text=True, timeout=15,
        )
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return None


def _pip_freeze() -> list[str] | None:
    """用 sys.executable -m pip freeze 抓當前環境依賴清單；失敗回 None。"""
    try:
        out = subprocess.run(
            [sys.executable, "-m", "pip", "freeze"],
            capture_output=True, text=True, timeout=120,
        )
        if out.returncode == 0:
            return [ln for ln in out.stdout.splitlines() if ln.strip()]
    except (OSError, subprocess.SubprocessError):
        pass
    return None


def _discover_logbooks(run_dir: Path, logbook_paths: list[Path] | None) -> list[Path]:
    """找居民 logbook：呼叫者指定優先，否則 glob residents/*/logbook.ndjson
    與 residents/*/trust/logbook.ndjson（body 實佈局在 trust/ 下）。"""
    if logbook_paths is not None:
        return [Path(p) for p in logbook_paths]
    found: list[Path] = []
    for pat in ("residents/*/logbook.ndjson", "residents/*/trust/logbook.ndjson"):
        found.extend(sorted(run_dir.glob(pat)))
    # 去重（保序）
    seen: set[Path] = set()
    uniq: list[Path] = []
    for p in found:
        rp = p.resolve()
        if rp not in seen:
            seen.add(rp)
            uniq.append(p)
    return uniq


def _pub_identity_for(logbook_path: Path) -> PublicIdentity | None:
    """從 logbook 同目錄的 identity.pub / vacant_id 建 PublicIdentity（離線驗鏈用）。"""
    d = logbook_path.parent
    pub_f, vid_f = d / "identity.pub", d / "vacant_id"
    if not (pub_f.exists() and vid_f.exists()):
        return None
    try:
        pub_hex = pub_f.read_text(encoding="utf-8").strip()
        vid = vid_f.read_text(encoding="utf-8").strip()
        return PublicIdentity.from_hex(vid, pub_hex)
    except (OSError, ValueError):
        return None


def _write_chain_verify(run_dir: Path, logbook_paths: list[Path] | None) -> None:
    """離線重驗每條居民鏈，把人可讀輸出寫進 chain_verify.txt。無鏈→SKIPPED＋理由。"""
    logbooks = _discover_logbooks(run_dir, logbook_paths)
    lines = [f"# chain_verify — 離線簽章鏈重驗（{_utc_now_iso()}）", ""]
    if not logbooks:
        lines.append(
            "SKIPPED: 此 run 目錄下找不到居民 logbook"
            "（residents/*/logbook.ndjson 或 residents/*/trust/logbook.ndjson）。"
        )
        lines.append("理由：本 run 無上鏈居民，或 logbook 未落盤於預期路徑。")
        (run_dir / CHAIN_VERIFY_NAME).write_text("\n".join(lines) + "\n", encoding="utf-8")
        return
    for lb_path in logbooks:
        rel = lb_path.relative_to(run_dir) if run_dir in lb_path.parents else lb_path
        who = _pub_identity_for(lb_path)
        if who is None:
            lines.append(
                f"SKIPPED {rel}: 同目錄缺 identity.pub / vacant_id，無公鑰可離線驗鏈。"
            )
            continue
        try:
            lb = Logbook.load(lb_path)
            ok = lb.verify_chain(who)
            lines.append(
                f"{'PASS' if ok else 'FAIL'} {rel}  entries={len(lb)}  "
                f"vacant_id=…{who.vacant_id[-12:]}"
                + ("" if ok else "  （鏈被竄改或不完整）")
            )
        except (OSError, ValueError) as e:
            lines.append(f"FAIL {rel}: 載入/驗鏈時例外 {type(e).__name__}: {e}")
    (run_dir / CHAIN_VERIFY_NAME).write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_card_verify(run_dir: Path) -> None:
    """對 trust_cards/*.json 逐張 verify_trust_card，輸出寫 card_verify.txt。
    無卡→不建檔（card_verify 是條件必要：有卡才需存在）。"""
    cards_dir = run_dir / TRUST_CARDS_DIR
    cards = sorted(cards_dir.glob("*.json")) if cards_dir.is_dir() else []
    if not cards:
        return
    lines = [f"# card_verify — 信任狀獨立驗簽（{_utc_now_iso()}）", ""]
    for cp in cards:
        rel = cp.relative_to(run_dir)
        try:
            card = json.loads(cp.read_text(encoding="utf-8"))
            ok = verify_trust_card(card)  # 用卡上自帶 signer_pub_hex 驗內部自洽
            task_id = card.get("task_id", "?")
            lines.append(
                f"{'PASS' if ok else 'FAIL'} {rel}  task_id={task_id}"
                + ("" if ok else "  （host_sig 驗不過：卡被竄改或簽者不符）")
            )
        except (OSError, ValueError) as e:
            lines.append(f"FAIL {rel}: 解析/驗卡例外 {type(e).__name__}: {e}")
    (run_dir / CARD_VERIFY_NAME).write_text("\n".join(lines) + "\n", encoding="utf-8")


def _ensure_anomalies(run_dir: Path) -> None:
    """anomalies.md 必存在；不存在則建立空骨架（明白斷言未登記異常）。"""
    p = run_dir / ANOMALIES_NAME
    if not p.exists():
        p.write_text("# anomalies\n\n" + ANOMALIES_EMPTY_NOTE, encoding="utf-8")


def _iter_pack_files(run_dir: Path):
    """遞迴列出 run_dir 下所有一般檔，排除 SHA256SUMS 自身。"""
    for p in sorted(run_dir.rglob("*")):
        if p.is_file() and p.name != SUMS_NAME:
            yield p


def _write_sha256sums(run_dir: Path) -> None:
    """對全部檔（排除自身）逐檔 sha256，格式同 sha256sum：`<hex>  <relpath>`。"""
    lines = []
    for p in _iter_pack_files(run_dir):
        rel = p.relative_to(run_dir).as_posix()
        lines.append(f"{_sha256_file(p)}  {rel}")
    (run_dir / SUMS_NAME).write_text("\n".join(lines) + ("\n" if lines else ""),
                                     encoding="utf-8")


def _parse_sha256sums(text: str) -> list[tuple[str, str]]:
    """解析 SHA256SUMS：回 [(hex, relpath)]。"""
    out = []
    for ln in text.splitlines():
        ln = ln.rstrip("\n")
        if not ln.strip():
            continue
        # 格式：<64hex><2 space><path>
        parts = ln.split("  ", 1)
        if len(parts) != 2:
            parts = ln.split(None, 1)
        if len(parts) == 2:
            out.append((parts[0].strip(), parts[1].strip()))
    return out


# --- 公開入口 ----------------------------------------------------------------
def pack(run_dir: str | Path, extra_meta: dict | None = None, *,
         logbook_paths: list[Path] | None = None) -> dict[str, Any]:
    """就地把 run_dir 整理成 RECORD_SPEC 佈局，回傳 manifest dict。

    誠實邊界：pack 只保證「包完整且自洽」，不保證「內容為真」——真實性由簽章鏈
    （chain_verify.txt）與稽核（card_verify.txt）承擔。
    """
    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    extra = dict(extra_meta or {})

    # 1) 驗證輸出先落盤（它們也要被 SHA256SUMS 涵蓋）
    _write_chain_verify(run_dir, logbook_paths)
    _write_card_verify(run_dir)
    _ensure_anomalies(run_dir)

    # 2) 組 manifest：自動偵測 + extra_meta 併入
    commit = _git_commit(run_dir)
    freeze = _pip_freeze()
    missing: dict[str, str] = dict(extra.get("missing", {}))

    manifest: dict[str, Any] = {
        "repo_commit": commit if commit is not None else "unknown",
        "pip_freeze": freeze if freeze is not None else [],
        "os": platform.platform(),
        "python": platform.python_version(),
        "model_id": None,
        "endpoint": None,
        "no_think": None,
        "seeds": None,
        "machine": f"{platform.node()} {platform.machine()}".strip(),
        "utc_start": None,
        "utc_end": _utc_now_iso(),
        "trust_arm": None,
        "scripts": {},
    }
    # extra_meta 覆寫（run harness 提供 pack 無法自知的欄位）
    for k, v in extra.items():
        if k == "missing":
            continue
        if k == "scripts" and isinstance(v, list):
            # 允許以路徑清單提供 scripts → 由 pack 計 sha256
            manifest["scripts"] = {
                str(sp): (_sha256_file(Path(sp)) if Path(sp).exists() else "MISSING")
                for sp in v
            }
        else:
            manifest[k] = v

    # 自動偵測失敗者記入 missing
    if commit is None:
        missing.setdefault("repo_commit", "git rev-parse HEAD 失敗（非 git repo 或無 git）")
    if freeze is None:
        missing.setdefault("pip_freeze", "pip freeze 失敗（無 pip 或逾時）")
    if manifest["utc_start"] is None:
        manifest["utc_start"] = manifest["utc_end"]
        missing.setdefault("utc_start", "extra_meta 未提供 run 起始時間，退用 pack 時刻")
    # extra_meta 未提供的關鍵 run 欄位，明白登記進 missing（不留空白讓讀者腦補）
    for k in ("model_id", "endpoint", "no_think", "seeds", "trust_arm"):
        if manifest.get(k) is None:
            missing.setdefault(k, "extra_meta 未提供")
    if not manifest["scripts"]:
        missing.setdefault("scripts", "extra_meta 未提供產生本 run 的腳本清單")

    # 可缺項缺席須附理由
    for opt in OPTIONAL_WITH_REASON:
        if not (run_dir / opt).exists():
            missing.setdefault(opt, "本 run 未產出此檔（可缺項）")

    manifest["missing"] = missing
    (run_dir / MANIFEST_NAME).write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    # 3) SHA256SUMS 最後（涵蓋以上全部，排除自身）
    _write_sha256sums(run_dir)
    return manifest


def check(run_dir: str | Path) -> tuple[bool, list[str]]:
    """對照 RECORD_SPEC 核對 run_dir。回 (ok, problems)；問題逐條點名。"""
    run_dir = Path(run_dir)
    problems: list[str] = []

    if not run_dir.is_dir():
        return False, [f"run 目錄不存在：{run_dir}"]

    # 1) 必要項存在
    for name in REQUIRED_FILES:
        if not (run_dir / name).exists():
            problems.append(f"缺必要項：{name}（記錄層 infra_void）")

    # 2) manifest 載入 + 必要欄位
    manifest: dict[str, Any] = {}
    mpath = run_dir / MANIFEST_NAME
    if mpath.exists():
        try:
            manifest = json.loads(mpath.read_text(encoding="utf-8"))
        except ValueError as e:
            problems.append(f"{MANIFEST_NAME} 不是合法 JSON：{e}")
        if isinstance(manifest, dict):
            for f in REQUIRED_MANIFEST_FIELDS:
                if f not in manifest:
                    problems.append(f"manifest 缺必要欄位：{f}")

    missing = manifest.get("missing", {}) if isinstance(manifest, dict) else {}
    if not isinstance(missing, dict):
        missing = {}

    # 3) 可缺項：缺席須在 manifest.missing 附理由
    for opt in OPTIONAL_WITH_REASON:
        if not (run_dir / opt).exists() and not missing.get(opt):
            problems.append(f"可缺項 {opt} 缺席但 manifest.missing 未附理由（缺席須有理由）")

    # 4) trust_cards 有卡則 card_verify.txt 必存在
    cards_dir = run_dir / TRUST_CARDS_DIR
    has_cards = cards_dir.is_dir() and any(cards_dir.glob("*.json"))
    cv_path = run_dir / CARD_VERIFY_NAME
    if has_cards and not cv_path.exists():
        problems.append(f"有 {TRUST_CARDS_DIR}/*.json 卻缺 {CARD_VERIFY_NAME}（有卡即必要）")

    # 5) SHA256SUMS 逐檔重驗
    spath = run_dir / SUMS_NAME
    if spath.exists():
        listed = _parse_sha256sums(spath.read_text(encoding="utf-8"))
        listed_paths = set()
        for want_hex, rel in listed:
            listed_paths.add(rel)
            fp = run_dir / rel
            if not fp.exists():
                problems.append(f"SHA256SUMS 列了 {rel} 但檔案不存在")
                continue
            got = _sha256_file(fp)
            if got != want_hex:
                problems.append(f"SHA256SUMS 不符：{rel}（落盤後被竄改或內容變動）")
        # 現存檔（排除自身）是否都在清單內
        for p in _iter_pack_files(run_dir):
            rel = p.relative_to(run_dir).as_posix()
            if rel not in listed_paths:
                problems.append(f"檔案 {rel} 未列入 SHA256SUMS（清單不完整）")

    # 6) chain_verify.txt 非空、不含 FAIL
    cvp = run_dir / CHAIN_VERIFY_NAME
    if cvp.exists():
        txt = cvp.read_text(encoding="utf-8")
        if not txt.strip():
            problems.append(f"{CHAIN_VERIFY_NAME} 為空（宣稱可驗證須附驗證輸出）")
        elif "FAIL" in txt:
            problems.append(f"{CHAIN_VERIFY_NAME} 含 FAIL（有居民鏈驗不過）")

    # 7) card_verify.txt（若存在）非空、不含 FAIL
    if cv_path.exists():
        txt = cv_path.read_text(encoding="utf-8")
        if not txt.strip():
            problems.append(f"{CARD_VERIFY_NAME} 為空（有卡卻無驗證輸出）")
        elif "FAIL" in txt:
            problems.append(f"{CARD_VERIFY_NAME} 含 FAIL（有信任狀驗不過）")

    return (not problems), problems
