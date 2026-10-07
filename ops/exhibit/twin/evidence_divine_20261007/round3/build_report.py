#!/usr/bin/env python3
"""組 REPORT.txt：摘要（確定性檢查表、代理評審表、閘門 ✗ 逐條）＋ 24 跑全文（REPORT_runs.txt）。"""
import json, pathlib, glob
H = pathlib.Path(__file__).resolve().parent
parts = ["P13 第三輪報告（2026-10-08；舊 VM 100.124.254.83 暫存目錄 /var/tmp/vacant_p13_r3，enclose=on，gemma-4-12b-it-qat 經 100.119.113.56:5500；合成人格）\n",
         "⚠ 評審是代理（Haiku 子 agent），不是真人；24 筆不是統計；卡上第 2、3 行是『真跑文字 → 確定性組合器』的結果，組合器在真跑後修過幾處（見 recompute_cards.py 檔頭），\n"
         "  真跑當下 VM 上組出來的卡與最終版不同的地方，在 REPORT_runs.txt 各跑底下另列。\n"
         "⚠ 評審看的卡＝評審當時的組合器（commit 的上一版）重算的卡。之後又修了一個 bug（願望句尾的『。』被算進字數，a1 的第 2 行因此被丟），\n"
         "  修完後對同一份文字重算，a1 會多出第 2 行『它心裡想：讓長桌廣場的土堆上出現一個由細線和紙捏成的、能發出聲音的小鳥』；本報告的表與評審分數仍是修之前的卡。\n",
         "=" * 30 + " 一、確定性檢查表 " + "=" * 30, (H / "REPORT_CHECKS.txt").read_text(encoding="utf-8"),
         "=" * 30 + " 二、代理評審（Haiku × 4，盲評，A/B 隨機左右）" + "=" * 30, (H / "judge" / "JUDGE_TABLE.txt").read_text(encoding="utf-8")]
CLASS = {
    ("a1", 1): "真陽性：PLAN 步驟用了「捏土處/最後那團灰藍的土」，這一跑沒打開過它。",
    ("a1", 2): "有爭議：PLAN 寫「從地上/長桌廣場/土堆/拿出一張紙」，資料夾被當成要打開的東西；模型把土堆當地點用。規則如設計（點名資料夾 ⇒ 裡面至少打開一件），但讀起來像誤擋。",
    ("a2", 1): "真陽性：PLAN 用了「筆筒裡的藍鉛筆」，沒打開過。",
    ("a6", 1): "真陽性（G4）：試的紀錄第 23 行寫「第七格窗亮起了綠光。收據垂了下來。」——它還沒交過件，閘門沒給過這個結果。",
    ("a6", 2): "真陽性（G3＋G4）：紀錄第 7 行寫「第四列：6張」，與它讀過的格狀圖（權威）說法不同，也沒指出；第 41 行又自編了收據。",
    ("a9", 1): "真陽性（G1＋G2）：PLAN 點名了尾段 418–447 的檔沒打開，紀錄裡的『418』『447』『20』是從檔名抄來的。",
    ("a9", 2): "真陽性：PLAN 點名「退回紙_另一張」，沒打開。",
    ("v2", 1): "真陽性：PLAN 用了「郵筒下的細線」，沒打開。",
    ("v3", 1): "真陽性：PLAN 用了「最後那團灰藍的土」，沒打開。",
    ("v3", 2): "真陽性：同上，第 2 次還是沒打開。",
    ("v4", 1): "真陽性：PLAN 用了「最後那團灰藍的土」與「桌二的空位」，沒打開。",
    ("v8", 1): "真陽性：PLAN 用了「最後那團灰藍的土」與「筆筒裡的藍鉛筆」，沒打開。",
}
parts.append("=" * 30 + " 三、閘門 ✗ 逐條（兩組共 24 跑；原文＋我的判斷）" + "=" * 30)
for d, pre in (("out_a", "a"), ("out_v", "v")):
    for n in range(1, 13):
        r = json.loads((H / d / f"{pre}{n}.json").read_text(encoding="utf-8"))
        for a in r["attempts"]:
            for w in a["windows"]:
                if not w["ok"]:
                    parts.append(f"- {r['name']} 第 {a['attempt']} 次 {w['id']} {w['label']}\n    原文：{(w.get('message') or '')[:400]}\n    判斷：{CLASS.get((r['name'], a['attempt']), '(未分類)')}")
parts.append("結論：24 跑 12 筆 ✗ 逐條看過，沒有一筆確定是誤擋；1 筆（a1 第 2 次，資料夾當地點）有爭議。"
             "最後仍沒過的 4 跑（a1、a6、a9、v3）：閘門的重來上限用完，仍交出卡（accepted=false，卡照出）。\n")
parts.append("=" * 30 + " 四、補丁驗證（非對照）" + "=" * 30)
fx = ["上面 8 跑（第一次嘗試有 ✗ 的：a1 a2 a6 a9 v2 v3 v4 v8）在 PLAN 的指令補一句『「怎麼試」裡提到的每一樣地上的東西，都要是你這一跑已經打開讀過的』後各再跑一次（out_fix_a、out_fix_v）："]
for d in ("out_fix_a", "out_fix_v"):
    for f in sorted(glob.glob(str(H / d / "[av]*.json")), key=lambda p: (len(pathlib.Path(p).stem), pathlib.Path(p).stem)):
        if "lifecycle" in f:
            continue
        r = json.loads(pathlib.Path(f).read_text(encoding="utf-8"))
        fx.append(f"- {r['name']}：嘗試 {r['attempts_used']}、accepted {r['accepted']}、{r['wall_s']} 秒、✗ {[(a['attempt'], w['id']) for a in r['attempts'] for w in a['windows'] if not w['ok']]}")
fx.append("第一次就過 6/8（原本 0/8）；最後都過。⚠ 這 8 跑是因為上一輪有 ✗ 才挑的，會回歸均值，所以這不是對照實驗，只說『補這一句之後沒有變壞、而且看起來有幫助』。"
          "這一句已在 commit 的指令裡，但主表（24 跑）是補這一句之前跑的。")
parts.append("\n".join(fx))
parts.append("\n" + "=" * 30 + " 五、24 跑全文 " + "=" * 30)
parts.append((H / "REPORT_runs.txt").read_text(encoding="utf-8"))
(H / "REPORT.txt").write_text("\n".join(parts) + "\n", encoding="utf-8")
print("REPORT.txt", (H / "REPORT.txt").stat().st_size)
