"""這支在架構裡承重什麼：**通道層的那個「隨時都在」的端點**。

`vacant install` 把五個 agent 的常駐設定檔指向 `http://127.0.0.1:<port>`。
那個位址**必須隨時有人在聽**，否則 agent 直接連不上——所以要有一支常駐的
反向代理，而不是「shim 每次起一個」（shim 只在有人經過 shim 時才存在，
那正是繞得過的那一層）。

本檔就是那支常駐 proxy。它把 `vacant_network.vrun.wireproxy.WireProxy`
包成一個長命的行程，由 OS 監督（macOS `launchd` `KeepAlive`／
Linux `systemd --user` `Restart=always`）。

## 跟 `vacant run` 裡那個 proxy 的差別（⚠ 三點，不可混講）

1. **不換鑰。** `vacant run` 會把金鑰從 agent 的環境裡拿掉、塞一個 sentinel，
   由 proxy 在轉送時換回真鑰。常駐這一支**原樣轉送 `Authorization`／
   `x-api-key`**（`sentinel=""` ⇒ `wireproxy` 的換鑰那一段整段不執行）。
   理由是紅線：常駐行程不該持有使用者的真鑰，而且我們也不准去讀
   `~/.codex/auth.json` 那一類檔案。代價是**「拿掉金鑰」那個弱保證在常駐
   這條路上不成立**——它本來也不是安全邊界（`envmap` 誠實邊界 3）。
2. **不跑驗收、不簽裁決收據。** 這支只做中介與落盤。閘門是 `gateshim` 那一層。
3. **落盤的是 journal 不是收據。** 每通請求的 body 逐位元落在
   `<state>/proxyd/wire/`，索引在 `index.jsonl`。
   **header 不落盤**（`wireproxy._handle_inner` 只寫 body），所以金鑰不會上碟。

## 這支存在本身就是一個新東西：**繞過閘門會留下痕跡**

人類指出的原始問題是「忘記打那一串 ⇒ 完全沒有 Vacant，**而且零痕跡**」。
裝了之後，即使有人打完整路徑跳過 shim（閘門沒跑），**通道仍然經過這支**，
那一通照樣進 journal。所以繞過閘門從「零痕跡」變成「有痕跡、但沒有裁決」。

⚠ **這不是「不會被繞過」。** 把設定檔改回去、或用一個不在名單上的 agent、
或直接 `curl`，都繞得過。能說的只有：**名單上的五個 agent，在設定沒被改回去
之前，模型呼叫會留下紀錄。**
"""
from __future__ import annotations

import json
import os
import pathlib
import signal
import sys
import time

from . import envmap
from .wireproxy import WireProxy


def run_daemon(*, port: int, state_dir: pathlib.Path,
               upstreams: dict[str, str]) -> int:
    wire_dir = state_dir / "proxyd" / "wire"
    wire_dir.mkdir(parents=True, exist_ok=True)
    meta = state_dir / "proxyd"
    proxy = WireProxy(wire_dir=wire_dir, upstreams=upstreams,
                      keys={},               # ⚠ 不持有任何真鑰
                      sentinel="",           # ⚠ ⇒ 換鑰那一段整段不執行
                      mode="tee", host="127.0.0.1", port=port)
    proxy.start()
    (meta / "state.json").write_text(json.dumps({
        "pid": os.getpid(), "url": proxy.url, "port": port,
        "started_at": time.time(),
        "upstreams": upstreams,
        "python": sys.executable,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    stop = {"now": False}

    def _sig(_s, _f):
        stop["now"] = True
    for s in (signal.SIGTERM, signal.SIGINT):
        try:
            signal.signal(s, _sig)
        except (OSError, ValueError):        # pragma: no cover
            pass
    print(f"[vacant proxyd] listening {proxy.url}  upstreams={upstreams}",
          flush=True)
    try:
        while not stop["now"]:
            time.sleep(1.0)
            # 心跳：`install-status` 用它判斷這支是活的而不是殭屍
            (meta / "heartbeat").write_text(
                json.dumps({"t": time.time(),
                            "requests_seen": proxy.stats["requests_seen"],
                            "by_wire": proxy.stats["by_wire"],
                            "errors": proxy.stats["errors"],
                            "blocked": proxy.stats["blocked"]},
                           ensure_ascii=False), encoding="utf-8")
    finally:
        proxy.stop()
        try:
            (meta / "state.json").unlink()
        except OSError:
            pass
    return 0


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="vacant proxyd",
                                 description="通道層的常駐反向代理")
    ap.add_argument("--port", type=int, required=True)
    ap.add_argument("--state", required=True, help="possess state 目錄")
    ap.add_argument("--upstream", action="append", default=[],
                    help="wire=url，可重複（openai／anthropic）")
    a = ap.parse_args(argv)
    ups = {"openai": envmap.SINK_UPSTREAM, "anthropic": envmap.SINK_UPSTREAM}
    for item in a.upstream:
        w, _, u = item.partition("=")
        if w in ups and u:
            ups[w] = u
    return run_daemon(port=a.port, state_dir=pathlib.Path(a.state),
                      upstreams=ups)


if __name__ == "__main__":
    raise SystemExit(main())
