# P8 線 V：最終版閘門的真跑（2026-10-02，舊 VM，真 pi＋gemma-4-12b-it-qat 經 100.119.113.56:5500）

- `f01`–`f12`：6 組合成特質×2，sub_id 挑不同關聯組；程式＝P7 最後版＋P8 修正（被時限切掉的嘗試 checks 標 `ok:null`、整跑 420 秒預算）。
- `b8`：B8 造出的一次——**模型端點指到關閉的埠 `127.0.0.1:9`**，且略過 twinlink 的端點探測（`gate_samples run --dead-endpoint`，只在測試行程 monkeypatch，production 不動）。
  結果見裁決檔 P8 一節：pi 起得來、打了 4 通到中介（全部 `model_call.error=true`），沒寫出信 ⇒ `requests_seen=4`（不是 0）、`degrade_kind=agent_no_plan`。
- `b8_probe_blocked.json`：不略過探測時的結果＝`upstream_unreachable`（production 路徑：探不到就不起 pi，沒有 lifecycle）。
- 每一跑：`<name>.json`、`<name>.lifecycle.jsonl`、`<name>.lifecycle.sidecar.jsonl`（原封不動）。合成特質，每跑跑完撤回。
