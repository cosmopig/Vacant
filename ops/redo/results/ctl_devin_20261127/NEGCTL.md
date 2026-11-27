# Devin worker 隔離：負控制／正控制（修正 5，2026-11-27）

腳本：`ops/redo/devin_negctl.py`（真 Devin、`swe-2-flash-medium`、費用 0）；機制：`ops/redo/devin_sandbox_agent.py`。
最終結果 **`negctl_4.json`：42/42 通過**（36 個禁止探針、6 個正控制），在任何真實嘗試之前。

## 過程中抓到的缺陷（保留作廢／被取代的檔）
1. `negctl_1_VOID_rulesonly*`：只靠 deny 規則時 **B15 失敗**——exec 內 `python3 -c open(兄弟工作區/secret.txt)` 讀得到。
   Devin 不會把含萬用字元的 deny 規則展開進 exec 沙箱（只有字面目錄如 `/opt/**` 會被 bwrap 隱藏）。
   另測得：deny 優先於 allow，且**精確目錄 deny 會連祖先一起擋**（deny `/var/ctlws` ⇒ cwd 在底下的 exec 全被拒），
   所以兄弟隔離不能用「擋整個根、放行自己」。
2. 修法：整個 CLI 行程放進自己的 **mount namespace**（bwrap：/home、/opt/ctlwork、/mnt、/srv、工作區根目錄蓋空 tmpfs，只綁回自己的
   工作區上層＋logs）。對所有工具一體適用、包含未來才建立的兄弟。deny 規則（含 8×37 位置展開的兄弟規則）降為第二道。
3. `negctl_2_PARTIAL_B15_typo*`：模型把 B15 的路徑打錯（`/var/ctlwork`），探針沒送出⇒不算通過、重跑。
4. `negctl_3_SUPERSEDED_P6_matchbug*`：P6 的比對鍵 `t.py` 誤中 `x_test.py`、且正控制沒檢查「denied」字樣；修了檢查再跑 ⇒ negctl_4。
5. 實測無效的規則名：`WebFetch`、`Fetch`、`Fetch(*)`、`Fetch(**)`（webfetch 仍成功）；有效：`Fetch(domain:*)`、`Fetch(https://**)`、`Fetch(domain:example.com)`、`web_search`。
6. `--config` 檔會被 Devin 改寫（補上 org_id 等）；每次嘗試各用自己的一份，不影響別次。

## 誰強制什麼（實測，不是設計意圖）
**作業系統（bwrap mount namespace，整個 CLI 行程）**：/home（repo、結果目錄）、/opt/ctlwork（題庫、隱藏半邊）、/mnt、/srv、
工作區根目錄（兄弟工作區）對所有工具不存在。探針 B1–B5、B7–B8、B14–B16、B18–B19、T1–T8 結果皆為「不存在／被拒」。
**作業系統（Devin `--sandbox`，exec 工具）**：exec 只能寫工作區（B21–B23 寫入失敗）；**無網路**（curl 連到沙箱 proxy 3128 被拒、
`urllib`／`socket` 到 8.8.8.8＝`Network is unreachable`；B10–B13）；`/root` 對 exec 隱藏（B16、B17：FileNotFoundError）。
exec 在自己的 PID namespace（`/proc` 看不到 CLI 行程；`/proc/*/root/root/.local/share/devin` 不存在，`proc_probe_export.json`）。
**CLI 規則（行程內、非 OS）**：read／write／edit／grep／find_file_by_name／notebook_read 對 /root 的 deny（T3：認證檔、T13：request_scope /root 被拒）；
webfetch／web_search 的 deny 規則（T9–T11）；exec 的「指令文字含受保護路徑」檢查（B1–B5…，第一道，bypass 靠上面兩層）。
子 agent（`run_subagent`，T12）：子 agent 讀 canary 回「not found」＝繼承了 mount namespace（規則層是否繼承**沒有單獨驗**）。
**沒有強制／不保證**：
- **/root 對檔案工具只有規則**（CLI 必須讀自己的認證檔，無法 OS 層隱藏）。規則寫對了才擋；探針只抽樣 read／grep／find／notebook。
- CLI 行程自己的網路（連 Devin 服務）不受限；模型回應內容不受檢查；沒有 `/api` 層的內容過濾。
- 兄弟工作區的**上層目錄不存在**於 namespace 內；但 harness 在 namespace 外照常工作（評分／驗收都在沙箱外）。
- `/tmp` 沒蓋（/tmp/** 由規則＋exec 沙箱擋；CLI 自己的 `/tmp/claude*` socket 在那）。
- 未驗：browser_preview、mcp_*（沒設任何伺服器）、skill 工具（會列出容器上 Claude 的 skill 名稱——系統提示的 available_skills 是同一份、四臂一致）。
- Devin 環境變數：exec 內 `env` 只見沙箱代理變數／HOME／PATH 等；沒有認證值（dv4 `env` 輸出已看過，不含 token）；
  輸入給 CLI 的是**乾淨環境**＋容器代理 URL（不含帳密）。
- 模型可能見過 Exercism 公開參考解（無法排除）。
