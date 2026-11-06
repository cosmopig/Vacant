"""`run_agent` 預算硬上限（工單 P20261106_0231-2）。

`max_tool_calls`／`max_tokens` 由執行器實際攔截（殺行程），不是提示詞。
未傳上限＝行為與以前逐位元組相同、用量欄位為 None（沒量就是 None，不填 0）。
token 上限只能在一次 API 回應結束後才知道用量 ⇒ 最多超出一次回應的量，
不是「事前保證不超過」。
"""
import json
import sys

from vacant_network.adapters.run import Launch, run_agent

# 每 0.1 秒印一行 JSON 並 flush，最後 sleep(30)——被殺前會一直活著。
_TOOL_CALL_LINES = (
    "import json, time\n"
    "for _ in range(20):\n"
    "    print(json.dumps({'type': 'tool_execution_start', 'toolName': 'bash'}), flush=True)\n"
    "    time.sleep(0.1)\n"
    "time.sleep(30)\n"
)
_TOKEN_LINES = (
    "import json, time\n"
    "for _ in range(20):\n"
    "    print(json.dumps({'type': 'message_end', 'message': {"
    "'role': 'assistant', 'usage': {'input': 1000, 'output': 10}}}), flush=True)\n"
    "    time.sleep(0.1)\n"
    "time.sleep(30)\n"
)


def _launch(script: str) -> Launch:
    return Launch(argv=[sys.executable, "-c", script])


def test_max_tool_calls_kills_agent(tmp_path):
    res = run_agent(_launch(_TOOL_CALL_LINES), workspace=tmp_path, log_dir=tmp_path,
                    timeout_s=20, max_tool_calls=3)
    assert res["budget_exceeded"] == "tool_calls"
    assert res["timed_out"] is False
    assert res["observed_tool_calls"] >= 4      # 「大於」3 才殺，所以量到至少 4
    assert res["wall_ms"] < 8000                # 遠早於 30s sleep 與 20s timeout


def test_max_tokens_kills_agent(tmp_path):
    res = run_agent(_launch(_TOKEN_LINES), workspace=tmp_path, log_dir=tmp_path,
                    timeout_s=20, max_tokens=2500)
    assert res["budget_exceeded"] == "tokens"
    assert res["observed_tokens"] >= 2500       # 每行 1010；「大於等於」才殺
    assert res["timed_out"] is False
    assert res["wall_ms"] < 8000


def test_no_cap_unchanged(tmp_path):
    script = (
        "import json\n"
        "print(json.dumps({'type': 'tool_execution_start', 'toolName': 'bash'}), flush=True)\n"
        "print(json.dumps({'type': 'message_end', 'message': "
        "{'role': 'assistant', 'usage': {'input': 5, 'output': 7}}}), flush=True)\n"
    )
    res = run_agent(_launch(script), workspace=tmp_path, log_dir=tmp_path, timeout_s=20)
    assert res["rc"] == 0
    assert res["budget_exceeded"] is None
    assert res["observed_tool_calls"] is None   # 沒啟用輪詢＝沒量＝None，不填 0
    assert res["observed_tokens"] is None
