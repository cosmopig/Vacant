"""ops.e1 — E1′ 實驗基建（「保護已經對的工作」：只提交範圍內單元 vs 原生 agent vs 驗收閘門＋回滾）。

這支在架構裡承重什麼
====================
E1′ 檢驗一個具體的工程假設：在多回合（multi-round）任務鏈中，當檔案已有已經正確的單元
（程式碼函式或報告宣稱行）且新一回合要求新增、改名或更新部分單元時，由宿主端（host-side）
執行「僅提交允許範圍內單元、範圍外一律保留基線」（S／S+B2／O）能否在最終回合顯著保護
既有正確工作，相對於無檢查的原生 agent（B0／B0x3）與只做驗收檢查加回滾的閘門（B2）。

所有任務鏈均衍生自公開資料集（EvalPlus HumanEval+ v0.1.10／MBPP+ v0.2.0、真實修訂
維基百科網頁快照），將其組裝為多回合演進鏈屬於**本實驗的延伸（our extension）**，不可與
原始公開基準的單回合分數混講。

誠實邊界（改碼請保留）
----------------------
- 本套件量測的是 **harness 側的範圍提交機制**，不是「裝了 Vacant 就會變好」的產品實測數字。
- EvalPlus 沒有「規格改變後的變體測試」，因此程式碼鏈**無法**構造「行為變更（behavior-change）」
  回合；該限制顯式記於每條程式碼鏈的 metadata 與文件，不偽造。
- 隔離仰賴 Linux bubblewrap（`bwrap`）的掛載與網路命名空間；worker 沙箱共用網路以連線本機
  模型端點與來源伺服器，因此隔離邊界涵蓋「宿主檔案系統不可見」，但不等同全機出口封鎖。
- 假 agent（selftest）只能驗證機制與管線沒有壞，**不是**模型效果證據。
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import pathlib
import re
import threading
from typing import Any

CODE_CHAIN_SCHEMA = "vacant.e1.code_chain/1"
DOC_CHAIN_SCHEMA = "vacant.e1.doc_chain/1"
PLAN_SCHEMA = "vacant.e1.plan/1"
RESULT_SCHEMA = "vacant.e1.round_result/1"

EVALPLUS_SHA256: dict[str, str] = {
    "HumanEvalPlus-v0.1.10.jsonl.gz": "272720b90ac375502c8ed23cd791c2a93dfb22a911641a494da74a426c09f101",
    "MbppPlus-v0.2.0.jsonl.gz": "af43697e8791c4c149bdfd6b489d8b5412507551ac20e28a439f650b8225db63",
}

ARMS_CODE: tuple[str, ...] = ("B0", "B0x3", "B2", "S", "S+B2", "O")
ARMS_DOC: tuple[str, ...] = ("B0", "B2", "S", "S+B2", "O")

#: KS-1 鐵律防呆：提示文字禁止責任／懲罰類措辭
KS1_BANNED_RE = re.compile(r"你有責任|會被懲罰|負責任|responsib|punish|penal|blame|fault of", re.I)

#: 預設路徑（唯讀參考資料與設定；實驗執行時永不寫入）
DEFAULT_EVALPLUS_DIR = pathlib.Path("~/dev/ops/ref/evalplus").expanduser()
DEFAULT_PI_CFG_DIR = pathlib.Path("~/dev/ops/agentcfg/d2v52").expanduser()


def utc_now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def assert_ks1_clean(text: str) -> None:
    m = KS1_BANNED_RE.search(text or "")
    if m:
        raise ValueError(f"KS-1 違規：提示含禁用詞 {m.group(0)!r}")


def atomic_write_text(path: pathlib.Path, content: str) -> str:
    """原子寫檔：寫入同目錄暫存檔、fsync 後以 os.replace 取代目標檔，回傳 sha256。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = content.encode("utf-8")
    tmp = path.with_name(f".{path.name}.tmp.{os.getpid()}.{threading.get_ident()}")
    with open(tmp, "wb") as fh:
        fh.write(raw)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)
    return sha256_bytes(raw)


def atomic_write_json(path: pathlib.Path, obj: Any) -> str:
    text = json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    return atomic_write_text(path, text)
