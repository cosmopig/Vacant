"""`envmap.CONFIG_ROUTE` 與 `wrap_agent.sh` 必須是**同一份名單**。

這支在架構裡承重什麼
────────────────────
`envmap` 的 docstring 說得很清楚：名單是**唯一**一份，漏一格的後果是
「那條路沒被中介，而且**不會有任何錯誤訊息**」。`CONFIG_ROUTE` 是設定檔框架
那一半的名單，而 `ops/vacantrun/wrap_agent.sh` 是它**唯一的可執行形式**。

兩邊分開住就會漂，而漂掉的徵兆**不是任何一支報錯**——是某一天有人寫
`wrap_agent.sh hermes` 拿到 `不認得的 agent`，或更糟：`CONFIG_ROUTE` 裡
還留著一格「已支援」而 wrapper 早就沒有那一段了。所以這支把「兩邊要對得上」
變成 CI 會紅的東西。

⚠ **這支證明的是名單一致，不是「接得通」。**
唯一能證明接通的是 `requests_seen > 0`（`docs/AGENT_COMPAT.md` §0），
而那要真的跑一個 agent、要機時，不在單元測試裡。
**不准把這支綠燈讀成某個 agent 可以用。**

2026-09-19 加這支的直接理由：Hermes 從 L-none 升到 L-real
（`docs/AGENT_COMPAT.md` §12），`CONFIG_ROUTE` 多一格、wrapper 多一段。
「加 agent 可以動行為，但要有測試」——這就是那個測試。
"""
from __future__ import annotations

import pathlib
import re

from vacant.vrun import envmap

WRAP = pathlib.Path(__file__).resolve().parents[1] / "ops" / "vacantrun" / "wrap_agent.sh"


def _wrapper_cases() -> set[str]:
    """把 `wrap_agent.sh` 的 `case` 分支名抓出來（`*)` 那一格不算）。"""
    text = WRAP.read_text(encoding="utf-8")
    body = text.split("case \"$AGENT\" in", 1)[1]
    return {m.group(1) for m in re.finditer(r"^([a-z][a-z0-9_-]*)\)\s*$", body, re.M)}


def test_wrapper_has_a_branch_for_every_config_route_entry():
    """`CONFIG_ROUTE` 有的，wrapper 一定要接得出來。"""
    missing = sorted(set(envmap.CONFIG_ROUTE) - _wrapper_cases())
    assert not missing, (
        f"`CONFIG_ROUTE` 列了 {missing} 但 `wrap_agent.sh` 沒有對應的 case ⇒ "
        "名單分家了。名單漏一格不會有錯誤訊息，所以這裡擋。")


def test_config_route_entries_are_complete():
    """每一格都要說得出「設定搬到哪、寫哪個欄位、哪條 wire、哪天量的」。"""
    for agent, spec in envmap.CONFIG_ROUTE.items():
        assert spec.get("relocate"), f"{agent}: 沒有 relocate ⇒ 只能改使用者自己那份設定"
        assert spec.get("field"), f"{agent}: 沒說 base url 落在哪個欄位"
        assert spec.get("wire") in {"openai", "anthropic"}, f"{agent}: wire 不是兩條路由之一"
        assert "measured" in spec, f"{agent}: 連「有沒有量過」都沒寫"


def test_hermes_is_measured_and_needs_provider_not_just_base_url():
    """Hermes 那一格的口徑（2026-09-19 實測，`docs/AGENT_COMPAT.md` §12）。

    ⚠ 這條釘的是**文件與程式對得上**，不是「它現在還通」。上游改版會漂，
    漂了的徵兆是 `requests_seen == 0`，不是這條紅。
    """
    spec = envmap.CONFIG_ROUTE["hermes"]
    assert spec["relocate"] == "HERMES_HOME"
    assert spec["file"] == "config.yaml"
    assert spec["measured"], "Hermes 已經是 L-real，`measured` 不可以再是空字串"
    # 反推曾經漏掉 provider 那一半，而那一半正好是決定會不會被中介到的那一半。
    assert "provider" in spec["field"], (
        "`field` 只寫 base_url 會讓下一個人重蹈覆轍：沒有 `provider: custom` 時 "
        "Hermes 在送出任何請求之前就停在 `No LLM provider configured`，"
        "`requests_seen == 0`（§12.2 對照 A）。")


def test_custom_base_url_is_redirected_with_the_v1_suffix():
    """`CUSTOM_BASE_URL` 是 Hermes 那條路真正在用的環境變數（§12.4 對照 B）。

    尾巴必須是 `/v1`：Hermes 拿到的值會直接當 OpenAI 相容的 base，
    少了 `/v1` 就會打到 `<proxy>/chat/completions`。
    """
    assert ("CUSTOM_BASE_URL", "/v1") in envmap.REDIRECT_VARS


def test_child_env_carries_custom_base_url_to_the_agent():
    """launcher 交給 agent 的環境裡真的有它，而且指向 proxy。"""
    child, meta = envmap.build_child_env(
        "http://127.0.0.1:65500", "vacant-run-test", env={"PATH": "/usr/bin"})
    assert child["CUSTOM_BASE_URL"] == "http://127.0.0.1:65500/v1"
    assert "CUSTOM_BASE_URL" in meta["redirected"]
