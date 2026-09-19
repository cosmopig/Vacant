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

## 第三種角色（2026-09-20）：`--unix` ＝ **enclosure 的那扇門**

`--unix <路徑>` 之下，本支改聽一個**路徑型 unix socket**。那是為了 enclosure
（`ops/vacantrun/enclosure_20260920/`）：`bwrap --unshare-all` ＋ mount ns 之下
TCP／DNS／抽象 socket **全部穿不過去**，實測只有路徑型 unix socket 穿得過
——所以它是唯一做得出「一扇門」的形狀。

門這一側的三個性質，**改碼請一條都不要弄丟**：

1. **門會終結 HTTP。** 之前那版是 byte pipe（`door_host_bytepipe.py`），
   而 byte pipe 不看內容 ⇒ enclosure 裡照樣可以對它送任何請求，洞只是從
   「任意主機」縮到「那一台上游」。**縮小不是關掉。**
2. **`--path-policy` 預設跟著聽法走**：`--unix` ⇒ `model`（只放模型 API 的
   path，`GET /admin` 當場 403 且一個 byte 都不往上游送），`--port` ⇒ `any`
   （常駐端點的既有行為，一個 byte 都沒改）。
3. **`sentinel=""` 一樣成立**：門**不持有任何金鑰**，`Authorization` 原樣穿透。
   多一扇門不等於多一個保管金鑰的地方。

⚠ 這扇門把「唯一那條路」做成真的，**但仍然不是「不會被繞過」**：圍牆成立的
理由是**路不存在**（namespace），不是門很聰明。把 agent 放到 enclosure 外面
跑，它一樣什麼都連得到。
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


def run_daemon(*, port: int | None, state_dir: pathlib.Path,
               upstreams: dict[str, str],
               unix_path: str | None = None,
               path_policy: str | None = None) -> int:
    wire_dir = state_dir / "proxyd" / "wire"
    wire_dir.mkdir(parents=True, exist_ok=True)
    meta = state_dir / "proxyd"
    # ⚠ 預設值**跟著聽法走**（見下面「第三種角色」那一節）：
    #   unix ⇒ `model`（那是 enclosure 唯一的出口，fail-closed）；
    #   TCP  ⇒ `any`（既有常駐端點的行為，一個 byte 都不改）。
    policy = path_policy or ("model" if unix_path else "any")
    proxy = WireProxy(wire_dir=wire_dir, upstreams=upstreams,
                      keys={},               # ⚠ 不持有任何真鑰
                      sentinel="",           # ⚠ ⇒ 換鑰那一段整段不執行
                      mode="tee", host="127.0.0.1", port=port or 0,
                      unix_path=unix_path, path_policy=policy)
    proxy.start()
    (meta / "state.json").write_text(json.dumps({
        "pid": os.getpid(), "url": proxy.endpoint, "endpoint": proxy.endpoint,
        "listen": "unix" if unix_path else "tcp",
        "port": None if unix_path else port,
        "unix_path": unix_path,
        "path_policy": policy,
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
    print(f"[vacant proxyd] listening {proxy.endpoint}  "
          f"path_policy={policy}  upstreams={upstreams}", flush=True)
    try:
        while not stop["now"]:
            time.sleep(1.0)
            # 心跳：`install-status` 用它判斷這支是活的而不是殭屍
            (meta / "heartbeat").write_text(
                json.dumps({"t": time.time(),
                            "requests_seen": proxy.stats["requests_seen"],
                            "by_wire": proxy.stats["by_wire"],
                            "errors": proxy.stats["errors"],
                            "blocked": proxy.stats["blocked"],
                            "refused_path": proxy.stats["refused_path"]},
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
    ap.add_argument("--port", type=int, default=None,
                    help="聽 TCP 127.0.0.1:<port>（常駐端點；與 --unix 二選一）")
    ap.add_argument("--unix", default=None, metavar="PATH",
                    help="改聽一個**路徑型** unix socket（enclosure 的那扇門）。"
                         "⚠ 只有它穿得過 --unshare-net。")
    ap.add_argument("--path-policy", choices=("any", "model"), default=None,
                    help="放哪些 path 過去。預設：--unix ⇒ model、"
                         "--port ⇒ any（既有行為）")
    ap.add_argument("--state", required=True, help="possess state 目錄")
    ap.add_argument("--upstream", action="append", default=[],
                    help="wire=url，可重複（openai／anthropic）")
    a = ap.parse_args(argv)
    # ⚠ fail-closed 而不是「兩個都聽」：一個 proxy 一扇門、一份 journal。
    if (a.port is None) == (a.unix is None):
        ap.error("--port 與 --unix 恰好要給一個（一個 proxy 一扇門）")
    ups = {"openai": envmap.SINK_UPSTREAM, "anthropic": envmap.SINK_UPSTREAM}
    for item in a.upstream:
        w, _, u = item.partition("=")
        if w in ups and u:
            ups[w] = u
    return run_daemon(port=a.port, state_dir=pathlib.Path(a.state),
                      upstreams=ups, unix_path=a.unix,
                      path_policy=a.path_policy)


if __name__ == "__main__":
    raise SystemExit(main())
