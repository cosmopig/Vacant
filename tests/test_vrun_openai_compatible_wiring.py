#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""W1：OpenAI 相容供應商的金鑰與上游，兩張表必須成對。

量到的缺口（`decisions/conclusions/FINDINGS_20260929_NATIVE_PLATFORM_WAVE1.md` §二 W1）
--------------------------------------------------------------------------------
`REDIRECT_VARS` 早就把九個供應商的 base-url 變數指向 proxy，`UPSTREAM_VARS` 與
`KEY_VARS` 卻只列了 `OPENAI_*`。`build_child_env` 又只對兩個變數給 sentinel。
於是讀 `OPENROUTER_API_KEY` 的 agent：

    agent_rc=1, agent_wall_s=1.196, requests_seen=0

——**在本機就失敗，一次 wire 都沒發**。本檔把修好的四件事逐條釘住。
"""
from __future__ import annotations

import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from vacant_network.vrun import envmap  # noqa: E402

FAILED: list[str] = []
PASSED: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    (PASSED if cond else FAILED).append(name + (" :: " + detail if detail else ""))


# 1 ------------------------------------------------- the two tables stay paired
def t1_tables_paired() -> None:
    redirect = {n for n, _ in envmap.REDIRECT_VARS}
    for url_var, key_var in envmap.OPENAI_COMPATIBLE:
        aliased = url_var in {"OPENAI_API_BASE", "OPENAI_BASE"}
        check("1 base url is redirected: " + url_var, url_var in redirect or aliased)
        check("1 key is stripped: " + key_var, key_var in envmap.SECRET_VARS)
        check("1 key is in KEY_VARS: " + key_var,
              key_var in envmap.KEY_VARS["openai"])
        check("1 base url is in UPSTREAM_VARS: " + url_var,
              url_var in envmap.UPSTREAM_VARS[0][1])
    check("1 no unredirected provider rows", envmap.UNREDIRECTED_PROVIDERS == (),
          str(envmap.UNREDIRECTED_PROVIDERS))


# 2 ------------------------------- every stripped key gets a sentinel, not a hole
def t2_every_key_gets_a_sentinel() -> None:
    child, meta = envmap.build_child_env(
        "http://127.0.0.1:9", "SENT",
        env={k: "real-" + k for k in envmap.SECRET_VARS})
    for url_var, key_var in envmap.OPENAI_COMPATIBLE:
        check("2 sentinel present: " + key_var, child.get(key_var) == "SENT",
              repr(child.get(key_var)))
        check("2 base url redirected: " + url_var,
              child.get(url_var) == "http://127.0.0.1:9/v1", repr(child.get(url_var)))
    check("2 anthropic key still sentineled", child.get("ANTHROPIC_API_KEY") == "SENT")
    check("2 the real keys are nowhere in the child env",
          not any(v.startswith("real-") for v in child.values()))
    check("2 sentinel_vars is recorded on the receipt",
          "OPENROUTER_API_KEY" in meta["sentinel_vars"])
    # the point of the fix, stated as a fact rather than a hope
    check("2 an SDK that requires OPENROUTER_API_KEY now has one",
          child.get("OPENROUTER_API_KEY") not in (None, ""))


# 3 ------------------------------------- the injected key is the right provider's
def t3_key_follows_the_named_destination() -> None:
    both = {"OPENAI_API_KEY": "sk-openai", "OPENROUTER_API_KEY": "sk-or"}
    check("3 explicit OPENROUTER_BASE_URL picks the openrouter key",
          envmap.discover_keys({**both,
                                "OPENROUTER_BASE_URL": "https://openrouter.ai/api/v1"}
                               )["openai"] == "sk-or")
    check("3 explicit OPENAI_BASE_URL picks the openai key",
          envmap.discover_keys({**both,
                                "OPENAI_BASE_URL": "http://127.0.0.1:1234/v1"}
                               )["openai"] == "sk-openai")
    check("3 nothing named keeps the legacy order (OPENAI first)",
          envmap.discover_keys(both)["openai"] == "sk-openai")
    check("3 only the openrouter key set uses it",
          envmap.discover_keys({"OPENROUTER_API_KEY": "sk-or"})["openai"] == "sk-or")
    check("3 no keys at all is the empty string, not a crash",
          envmap.discover_keys({})["openai"] == "")


# 4 --------------------------------- an explicitly named destination is honoured
def t4_named_destination_is_not_sunk() -> None:
    """⚠ 這一條是**行為改變**，寫在這裡是為了它不會變回來而不被發現。

    從前：使用者明講 `OPENROUTER_BASE_URL=https://openrouter.ai/api/v1`，
    該變數被 redirect 到 proxy，而 `describe_upstreams` 看不到它 ⇒ openai wire
    記成 `defaulted`、沒有 `--allow-public-upstream` 就指到本機 sink ⇒ 502。
    改後：明講的目的地被當成**明講**（`source=env:…`、`defaulted=False`）。
    沒有明講任何目的地時的 fail-closed 行為**不變**。
    """
    named = {"OPENROUTER_API_KEY": "sk-or",
             "OPENROUTER_BASE_URL": "https://openrouter.ai/api/v1"}
    d = envmap.describe_upstreams(named, allow_public=False)
    check("4 a named destination is source=env", d["openai"]["source"] == "env:OPENROUTER_BASE_URL",
          d["openai"]["source"])
    check("4 a named destination is not defaulted", d["openai"]["defaulted"] is False)
    check("4 a named destination is not sunk", d["openai"]["fallback"] is None)
    check("4 the named url is the one recorded", d["openai"]["url"] == named["OPENROUTER_BASE_URL"])

    bare = envmap.describe_upstreams({"OPENROUTER_API_KEY": "sk-or"}, allow_public=False)
    check("4 with nothing named it is still fail-closed",
          bare["openai"]["url"] == envmap.SINK_UPSTREAM, bare["openai"]["url"])
    check("4 with nothing named it is still marked defaulted",
          bare["openai"]["defaulted"] is True)
    check("4 allow_public with nothing named still goes to the public default",
          envmap.describe_upstreams({"OPENROUTER_API_KEY": "x"},
                                    allow_public=True)["openai"]["url"]
          == envmap.DEFAULT_UPSTREAM["openai"])


# 5 ------------------------------------------------------- routing is unchanged
def t5_routing_unchanged() -> None:
    """本檔只加金鑰與上游的對應，**不碰** `route()` 的分界。"""
    from vacant_network.vrun import wireproxy
    check("5 anthropic path still routes to anthropic",
          wireproxy.route("/v1/messages") == "anthropic")
    check("5 completions path still routes to anthropic",
          wireproxy.route("/v1/complete") == "anthropic")
    check("5 openrouter's chat path routes to openai",
          wireproxy.route("/v1/chat/completions") == "openai")
    check("5 the openai auth header is unchanged",
          envmap.AUTH_HEADERS["openai"] == ("authorization", "Bearer {key}"))


for fn in (t1_tables_paired, t2_every_key_gets_a_sentinel,
           t3_key_follows_the_named_destination, t4_named_destination_is_not_sunk,
           t5_routing_unchanged):
    try:
        fn()
    except Exception as e:
        FAILED.append(f"{fn.__name__} raised {type(e).__name__}: {e}")


def test_openai_compatible_wiring():
    assert not FAILED, "failures:\n  " + "\n  ".join(FAILED)


if __name__ == "__main__":
    print("=" * 74)
    print("W1 — OpenAI-compatible key/upstream pairing (zero model calls)")
    print("=" * 74)
    for p in PASSED:
        print("  [OK ]", p)
    for f in FAILED:
        print("  [FAIL]", f)
    print(f"\n{len(PASSED)} passed, {len(FAILED)} failed")
    sys.exit(1 if FAILED else 0)
