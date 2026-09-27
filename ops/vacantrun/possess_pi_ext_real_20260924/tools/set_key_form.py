#!/usr/bin/env python3
"""把使用者 models.json 裡 mylab 的 apiKey 設成指定形式（literal／env／cmd／wrong）與 baseUrl。
這支檔**不印金鑰**。"""
import json, pathlib, sys
R = pathlib.Path("/var/tmp/vacant_piext_20260924")
form = sys.argv[1]
base = sys.argv[2] if len(sys.argv) > 2 else "http://100.124.254.83:18899/v1"
secret = (R / "secret").read_text().strip()
key = {"literal": secret, "env": "$MYLAB_KEY", "cmd": f"!cat {R}/secret",
       "wrong": "sk-relay-" + "0" * 32}[form]
d = R / "home/.pi/agent"
d.mkdir(parents=True, exist_ok=True)
doc = {"providers": {"mylab": {
    "baseUrl": base, "api": "openai-completions", "apiKey": key,
    "compat": {"supportsDeveloperRole": False, "supportsReasoningEffort": False},
    "models": [{"id": "gemma-4-12b-it-qat", "name": "gemma-4-12b-it-qat",
                "contextWindow": 131072, "maxTokens": 16384}]}}}
(d / "models.json").write_text(json.dumps(doc, indent=2) + "\n")
(d / "settings.json").write_text(json.dumps(
    {"defaultProvider": "mylab", "defaultModel": "gemma-4-12b-it-qat"}, indent=2) + "\n")
print(f"models.json: mylab apiKey form={form} baseUrl={base}")
