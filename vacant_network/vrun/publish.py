"""publish — **唯一有對外寫入能力的那一塊**（2026-09-20 裁決 §四 P0 第二塊）。

這支在架構裡承重什麼：它是「出口」。而它的規則只有一條——

    沒有有效的 release attestation ＝ 不能 publish。

🔴 **它不讀退出碼。** 不讀 agent 的，也不讀 `vacant run` 的。
理由是 abpi 那批教的：`abpi_cell.sh:112` 就是一個「不看 rc 直接 `cp`」的呼叫者，
而它不是惡意的，只是**沒想到要看**。把安全性建立在「每個 harness 都記得寫
`if [ "$rc" = 0 ]`」上面，等於沒有安全性。所以這裡改成：

    不是要求呼叫者記得檢查，而是讓它**沒有東西可以發**。

它驗的是：簽章 · 交付物雜湊 · 判決 · 有效期 · 呼叫端要求的 coverage。

## ⚠ 誠實邊界（改碼請保留）

1. **這一層只綁「走這條路的呼叫者」。** 拿得到原始檔案的人照樣 `cp`／`git push`。
   本檔**沒有**、也做不到「讓別的路消失」——那要靠**呼叫者對目的地沒有寫入能力**
   （不同 UID／不同行程／不同憑證／OS 權限），是部署的事不是程式的事。
   ⇒ **不准寫「交付物被擋在出口」**，可以寫的是
   「**這條出口**在沒有 PASS 憑證時不會放行，而且它不看退出碼」。
2. **`--force` 不存在，而且刻意不做。** 一個可以繞過的閘門，在需要它的那一天
   一定會被繞過。要發沒過的東西，就自己 `cp`——**那條路留著是誠實**，
   因為它本來就存在，假裝擋住它才是說謊。
3. `dest` 已存在時**預設拒絕**（`overwrite=False`）。覆寫是不可逆的外部效應，
   而本檔的全部意義就是讓不可逆的事需要憑證。
"""
from __future__ import annotations

import pathlib
import shutil
import tempfile

from . import release as _release

#: 退出碼。與 `gateshim` 那一套分開——**這是另一個元件的判決**。
EXIT_PUBLISHED = 0
EXIT_NO_TOKEN = 30      # 根本沒給憑證
EXIT_REJECTED = 31      # 給了但驗不過
EXIT_DEST_EXISTS = 32   # 目的地已存在而沒明講要覆寫


def publish(src, dest, token: dict | None, *, pub_hex: str,
            vacant_id: str = "", require_coverage: dict | None = None,
            overwrite: bool = False, now: float | None = None,
            dry_run: bool = False) -> dict:
    """驗憑證，過了才把 `src` 送到 `dest`。

    回 `{"published": bool, "exit_code": int, "reasons": [...], "verify": {...}}`。

    ⚠ **注意這個函式簽名裡沒有任何 rc／returncode／exit 參數。** 那是刻意的：
      它無從得知 agent 或 launcher 的退出碼，所以也無從「忘記檢查」。
    """
    src = pathlib.Path(src)
    dest = pathlib.Path(dest)
    reasons: list[str] = []

    if token is None:
        return {"published": False, "exit_code": EXIT_NO_TOKEN,
                "reasons": ["沒有 release attestation ⇒ 沒有 publish capability"],
                "verify": None}

    if not src.is_file():
        return {"published": False, "exit_code": EXIT_REJECTED,
                "reasons": [f"來源不存在或不是檔案：{src}"], "verify": None}

    v = _release.verify(token, pub_hex=pub_hex, vacant_id=vacant_id,
                        artifact_path=src, now=now,
                        require_coverage=require_coverage)
    if not v["ok"]:
        return {"published": False, "exit_code": EXIT_REJECTED,
                "reasons": v["reasons"], "verify": v}

    if dest.exists() and not overwrite:
        return {"published": False, "exit_code": EXIT_DEST_EXISTS,
                "reasons": [f"目的地已存在且沒有 overwrite=True：{dest}"],
                "verify": v}

    if dry_run:
        return {"published": False, "exit_code": EXIT_PUBLISHED,
                "reasons": ["dry_run：驗過了但沒有寫出去"], "verify": v}

    # 原子寫入：同目錄暫存檔 ＋ replace。半個檔案出現在客戶目錄裡，
    # 比完全沒出現更糟——它看起來像交付。
    dest.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(dest.parent), prefix=".vacant-pub-")
    tmp_p = pathlib.Path(tmp)
    try:
        import os as _os
        _os.close(fd)
        shutil.copyfile(src, tmp_p)
        tmp_p.replace(dest)
    except BaseException:
        tmp_p.unlink(missing_ok=True)
        raise
    return {"published": True, "exit_code": EXIT_PUBLISHED,
            "reasons": [], "verify": v, "dest": str(dest)}
