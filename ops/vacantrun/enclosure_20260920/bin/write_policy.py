#!/usr/bin/env python3
"""把「這一跑實際用的圍牆政策」落成一個檔，給圍牆**裡面**那支探針讀。

用法：write_policy.py <輸出路徑> <外面的 netns id 或空字串> <bwrap 參數…>

⚠ **不帶時間戳**：同一份政策要雜湊出同一個值（`policy_sha256` 才跨跑可比）。
⚠ 這個檔會跟門一起 `--ro-bind` 進 `/run/vacant/` ⇒ 圍牆裡面改不掉。
"""
import json
import pathlib
import sys

out = pathlib.Path(sys.argv[1])
outer = sys.argv[2] or None
doc = {"schema": "vacant-enclosure-policy/1",
       "outer_net_ns": outer,
       "door_sock": "/run/vacant/relay.sock",
       "bwrap_args": sys.argv[3:]}
out.write_text(json.dumps(doc, ensure_ascii=False, sort_keys=True,
                          indent=2) + "\n", encoding="utf-8")
