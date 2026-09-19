"""裝好的 wheel 真的能用嗎——build job 的最小 quickstart（零網路、零模型呼叫）。

這支在架構裡承重什麼：`python -m build` 成功只證明「打得包起來」，不證明
「裝起來能跑」。最常見的兩種壞法都不會讓 build 失敗：

  1. **套件資料沒進去**——`pyproject.toml` 的 `package-data` 漏了，
     觀測台的 `vacant/web/*.html` 就不在 wheel 裡；只有在別的機器上
     真的去讀那個檔的時候才會炸。
  2. **依賴宣告漏了**——本機測試用得到的東西剛好裝在開發環境裡，
     wheel 的 `dependencies` 卻沒寫；全新環境一 import 就 ImportError。
  3. **第一屏跑不動**——`vacant demo gate` 的判斷層 2026-09-18 才從 `ops/`
     搬進 `vacant/vrun/`（`ops/` 不進 wheel）。少一支模組、子行程的
     `PYTHONPATH` 指錯，上面兩條照樣全過，而下載的人拿到的是一個
     跑不起來的第一屏。

所以這支**必須在 repo 目錄以外**執行（CI 會 `cd "$RUNNER_TEMP"`），
否則 `import vacant` 會讀到原始碼那一份，上面三條都測不到。

跑的是簽章鏈的最小一圈（創世 → 接一筆 → 全鏈驗章），因為那是本專案
唯一的 runtime 依賴（`cryptography`）真的被用到的地方；再加上整幕
`vacant demo gate`（零網路、零模型、約 2 秒），判準**沿用 demo 自己的
可執行防呆**，不在這裡寫第二份。
"""
from __future__ import annotations

import pathlib
import sys


def main() -> int:
    here = pathlib.Path.cwd().resolve()
    if (here / "vacant" / "__init__.py").exists():
        print(f"× 這支要在 repo 以外跑（現在在 {here}）——"
              "不然 import 到的是原始碼不是裝進去的 wheel")
        return 2

    import vacant
    from vacant import Identity, Logbook, PublicIdentity

    mod = pathlib.Path(vacant.__file__).resolve()
    print(f"import vacant  ← {mod}")
    if "site-packages" not in mod.parts:
        print("× import 到的不是 site-packages 裡那一份")
        return 2

    # 1) 簽章鏈的最小一圈：創世 → 第二筆 → 全鏈驗章。
    ident = Identity.generate()
    who = PublicIdentity(vacant_id=ident.vacant_id, pub=ident.pub)
    book = Logbook()
    book.append("smoke", {"n": 1}, ident, ts_ms=1)
    book.append("smoke", {"n": 2}, ident, ts_ms=2)
    assert len(book) == 2, len(book)
    assert book.verify_chain(who) is True, "全新環境裡驗不了自己剛簽的鏈"
    assert book.stream_id() == book.entries[0].hash(), "stream_id 不是創世 hash"
    print(f"logbook  2 筆、head={book.head()[:16]}…、verify_chain=True")

    # 2) 套件資料：觀測台的靜態檔要跟著 wheel 一起裝進去。
    web = mod.parent / "web"
    html = sorted(p.name for p in web.glob("*.html")) if web.is_dir() else []
    if not html:
        print(f"× wheel 裡沒有 vacant/web/*.html（package-data 漏了）：{web}")
        return 2
    print(f"package-data  vacant/web/ 有 {len(html)} 個 html：{', '.join(html)}")

    # 3) console script 的進入點 import 得動（`vacant` 指令本身另外驗）。
    from vacant.cli import main as cli_main
    assert callable(cli_main)
    print("entry point  vacant.cli:main 可呼叫")

    # 4) **第一屏**：`vacant demo gate` 真的把交付擋下來。
    #
    #    為什麼這一條要在 CI 裡：`pip install` 之後跑得動第一屏，是 2026-09-18
    #    搬家（判斷層進 `vacant/vrun/`）的全部目的。而它壞掉的方式很安靜——
    #    少一個模組、少一份 package-data、子行程的 PYTHONPATH 指錯——
    #    上面三格全都會過。人類手測過一次不等於下一次改動之後還會過。
    #
    #    ⚠ **不在這裡寫第二份判準**：`vacant/vrun/demo.py::_assert_not_a_performance`
    #    已經逐條檢查這一幕的每個前提（裸 agent rc=0、閘門 rc=EXIT_REFUSED、
    #    stop_reason、收據鏈最後一筆是 ws_verdict、驗章器的負控制先過…），
    #    任何一條不成立就 `SystemExit`。所以這裡只看**退出碼**與它自己吐的
    #    JSON，`EXIT_REFUSED` 也是從 launcher 讀，不寫死 20。
    import json
    import subprocess
    import tempfile

    from vacant.vrun.launcher import EXIT_REFUSED

    with tempfile.TemporaryDirectory(prefix="vacant-demo-gate-") as td:
        p = subprocess.run(
            [sys.executable, "-m", "vacant.cli", "demo", "gate",
             "--root", td, "--json"],
            capture_output=True, text=True, timeout=300)
        if p.returncode != 0:
            print("× vacant demo gate 沒跑完（demo 自己的防呆會在前提不成立時喊停）")
            print(p.stdout[-3000:])
            print(p.stderr[-3000:])
            return 2
        try:
            out = json.loads(p.stdout)
        except json.JSONDecodeError:
            print("× vacant demo gate --json 沒吐出 JSON：")
            print(p.stdout[-3000:])
            return 2
        if out.get("gated_rc") != EXIT_REFUSED or out.get("receipts_verdict") != "OK":
            print(f"× 第一屏的結果不對：{json.dumps(out, ensure_ascii=False)[:600]}")
            return 2
    print(f"demo gate  閘門 rc={out['gated_rc']}（{out['stop_reason']}）、"
          f"可見驗收 {out['visible_passed']}/{out['visible_total']}、"
          f"收據 {out['receipt_entries']} 筆 verdict={out['receipts_verdict']}")
    print("SMOKE OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
