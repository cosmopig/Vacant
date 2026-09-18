#!/usr/bin/env python3
"""工作區樹雜湊——R530 的「這一格當時長什麼樣」承重件。

這支在架構裡承重什麼（`DECISION_20260913_R530_…_PREREG.md` §三-1、§五-4）：
既有的收據鏈（`vacant/logbook.py`）佐證的是**模型說了什麼**——每一輪的訊息與
裁決被簽進 hash-chain。R530 的處理是**一個目錄**，而目錄不在鏈上 ⇒ 沒有這支，
收據能證明「這段對話沒被改過」，證明不了「當時工作區長這樣」。
樹雜湊逐輪簽進鏈（`ws_attempt` 的 `ws_sha256`），兩者合起來才是一份完整收據。

演算法（刻意寫得可以用 shell 重算，不綁本 repo）：

    leaf  = {"path": <相對路徑，POSIX 分隔>, "sha256": <檔案內容 sha256>,
             "exec": <擁有者可執行位元>}
    root  = sha256(json.dumps(sorted(leaves, key=path), sort_keys=True,
                              separators=(",", ":"), ensure_ascii=False))

**只取內容，不取 mtime／uid／inode**。理由是硬需求不是偏好：
`cp -a` 會保留樣板的 mtime，但**每一格的建立時間不同**，任何把時間戳算進去的
雜湊都會讓「同一份樣板複製出來的 108 格」得到 108 個不同的值 ⇒ §五-5 的 E-1
（所有工作區起點雜湊相同）在結構上永遠紅，而那不是資料的問題是量具的問題。

**`exec` 位元進雜湊，這是對預註冊字面（「排序路徑＋內容 sha256」）的一處明示擴充。**
理由：`chmod +x run.sh` 改變工作區的行為卻不改變任何一個位元組的內容，
純內容雜湊看不見它。擴充寫在這裡而不是靜靜加進去——量具改了要說出來。

**`.git/` 整個排除**，同樣是硬需求：`git init && git commit` 產生的 object／
`COMMIT_EDITMSG`／`index` 帶著 commit 時間與作者，逐格必然不同。排除它之後，
「worker 到底動了什麼」仍然可以用 `git diff` 事後查（§三-1），
只是那條證據走的是 git 自己，不是這支雜湊。
其餘一律納入，包含 worker 自己新增的檔案與空目錄以外的所有東西。

**誠實邊界**：這支證明的是「這棵樹的內容在被雜湊的當下是這樣」。它**不**證明
誰寫的、也**不**證明中間沒有被改過又改回來——後者由收據鏈的時間次序承接，
而鏈本身只能說「事後沒被改過」，不能說「由某個已知的人簽的」
（`gain_run.save_receipts` 的同一條誠實邊界，R530 逐字沿用）。

零外部依賴（只用標準庫）：vacant-dev 上沒有 venv、沒有 pip
（§三-2 實測），這支必須在 `/usr/bin/python3` 裸跑。
"""
from __future__ import annotations

import hashlib
import json
import os
import pathlib

#: 不進樹雜湊的目錄名（逐字比對整段路徑元件，不做模糊比對）。
#: `.git` 的理由見模組 docstring；其餘兩個是 Python 自己產生的快取，
#: 內容隨直譯器版本與執行次序變動，與 worker 的工作無關。
EXCLUDED_DIRS = frozenset({".git", "__pycache__", ".pytest_cache"})

#: 單檔讀取的區塊大小。純效能參數，不影響結果。
_CHUNK = 1 << 20


def file_sha256(path: pathlib.Path) -> str:
    """一個檔案的內容 sha256（十六進位小寫）。"""
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(_CHUNK)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def tree_leaves(root: str | os.PathLike) -> list[dict]:
    """回傳排序過的葉子清單 `[{path, sha256, exec}, …]`。

    符號連結**不跟隨**：記成一個葉子，`sha256` 取的是連結目標字串的 sha256，
    並帶 `"symlink": true`。理由是 fail-visible——跟隨連結會讓
    `ln -s /etc/passwd x` 把工作區外的內容算進樹雜湊，
    忽略它則會讓一個真的改動在雜湊上消失。
    """
    base = pathlib.Path(root)
    if not base.is_dir():
        raise FileNotFoundError(f"工作區不存在或不是目錄：{base}")
    leaves: list[dict] = []
    for dirpath, dirnames, filenames in os.walk(base, followlinks=False):
        dirnames[:] = sorted(d for d in dirnames if d not in EXCLUDED_DIRS)
        for name in sorted(filenames):
            p = pathlib.Path(dirpath) / name
            rel = p.relative_to(base).as_posix()
            if p.is_symlink():
                target = os.readlink(p)
                leaves.append({
                    "path": rel,
                    "sha256": hashlib.sha256(target.encode("utf-8")).hexdigest(),
                    "exec": False,
                    "symlink": True,
                })
                continue
            if not p.is_file():
                # FIFO／socket／device：不讀內容（會 block），但**不可以靜靜跳過**。
                leaves.append({"path": rel, "sha256": None, "exec": False,
                               "special": True})
                continue
            st = p.stat()
            leaves.append({
                "path": rel,
                "sha256": file_sha256(p),
                "exec": bool(st.st_mode & 0o100),
            })
    leaves.sort(key=lambda d: d["path"])
    return leaves


def tree_hash(root: str | os.PathLike) -> str:
    """工作區的 Merkle 根（sha256 十六進位小寫）。"""
    return hashlib.sha256(canonical_leaves(tree_leaves(root))).hexdigest()


def canonical_leaves(leaves: list[dict]) -> bytes:
    """葉子清單的正規化位元組——雜湊的唯一輸入，重算的人照這一行寫就好。"""
    return json.dumps(leaves, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def tree_manifest(root: str | os.PathLike) -> dict:
    """給落盤用的一整份：根雜湊 ＋ 逐檔葉子 ＋ 檔數與位元組數。

    `files_n`／`bytes_n` 不進雜湊，它們是給人看的——樹雜湊變了的時候，
    第一個要看的是「檔案多了幾個」而不是去 diff 一個 64 字元的字串。
    """
    leaves = tree_leaves(root)
    base = pathlib.Path(root)
    total = 0
    for leaf in leaves:
        if leaf.get("symlink") or leaf.get("special"):
            continue
        total += (base / leaf["path"]).stat().st_size
    return {
        "ws_sha256": hashlib.sha256(canonical_leaves(leaves)).hexdigest(),
        "files_n": len(leaves),
        "bytes_n": total,
        "leaves": leaves,
    }


def diff_leaves(before: list[dict], after: list[dict]) -> dict:
    """兩份葉子清單的差集——「worker 到底動了什麼」的機器可讀版本。"""
    b = {d["path"]: d for d in before}
    a = {d["path"]: d for d in after}
    return {
        "added": sorted(set(a) - set(b)),
        "removed": sorted(set(b) - set(a)),
        "changed": sorted(p for p in set(a) & set(b)
                          if a[p]["sha256"] != b[p]["sha256"]
                          or a[p].get("exec") != b[p].get("exec")),
    }


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser(description="工作區樹雜湊（R530）")
    ap.add_argument("path")
    ap.add_argument("--manifest", action="store_true",
                    help="印出完整 manifest（含逐檔葉子）而不是只印根雜湊")
    args = ap.parse_args()
    if args.manifest:
        print(json.dumps(tree_manifest(args.path), ensure_ascii=False, indent=2))
    else:
        print(tree_hash(args.path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
