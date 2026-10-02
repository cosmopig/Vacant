# P12 整合端到端（2026-10-02，舊 VM 100.124.254.83，暫存目錄 /var/tmp/vacant_p12_e2e，已留在 VM 待人類清）

整合後的 Vacant（`exhibit/twin-fortune-20261002`）＋雲端 `feat/fortune`（f400076＋d5ef30a，`vacant-world-cloud-wt-p10`）：VM 上起雲端 server.js（自訂 token、port 3392），
`twinlink loop`（engine=agent、enclose=on、require_tier=B、模型 gemma-4-12b-it-qat 經 100.119.113.56:5500），腳本 `ops/exhibit/twin/smoke_fortune_e2e.py`。全是 SYNTH 合成特質，沒有任何觀眾資料送外部服務。

- `smoke_fortune_report.json`：stage 時間軸、`fortune_result`、拍立得 http／meta（本機重算，確定性）、撤回殘留。
- `status_A/B.json`、`polaroid_A/B.png`、`qr_decode.json`（OpenCV 解出來＝官網 https://vacant.cosmopig.com）。
- `live.jsonl`／`live.sidecar.jsonl`＝三格混在一起的原封事件流；`pe_A／pe_B.*`＝拆開的 A、B 兩格（喂電視用）。
- `run1_hints_dropped/`：第一次跑。**量到一個整合缺口**：P11 的 `polaroid_hints`（地點／物件類別）twinagent 有輸出，但 `twinvault.TWIN_OFF_CHAIN_KEYS` 沒收，封存時被丟掉 ⇒ 拍立得永遠拿到 None（背景一律退到 drop）。
  已修（加進白名單、有回歸測試），第二次跑（本目錄頂層）才看到背景對得上地點（A＝longtable、B＝drop）。
- 電視截圖與時間軸：vacant_hm `exhibit/world3-fortune-20261002` 的 `evidence/fortune_p12_20261002/shots/`（`pe_A_01_fortune_way`、`pe_A_08_fortune_card`、`pe_B_01_fortune_way`、`pe_B_15_fortune_card`）。
