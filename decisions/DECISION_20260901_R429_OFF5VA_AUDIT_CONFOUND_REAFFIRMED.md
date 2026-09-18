# round429：off5v 的「mechanism_contributes」需要 off5va 的稽核曝光警語，round428 漏寫了

## 背景

round428（2026-09-01 00:32-00:40 UTC）重跑冷落 26 輪的 `analyze_off5v.py`，
發現 discordant `(b,c)=(0,6)`、McNemar p=0.0312，判定 `mechanism_contributes`，
寫進 GAIN_STATE：「這是第 3 個獨立檢查點，`mechanism_contributes` 判定從未
動搖過」。這句話**字面正確**（off5v 的原始數字確實穩定），但省略了一個
round388 就已經建立、round392 又驗證過一次的關鍵警語——導致讀者（下一輪
或人類）可能誤以為「同儕評審／修訂機制本身」的判斷力被證實優於
self-consistency，而這不是量到的東西。

## 本輪怎麼發現的（先於重新翻出 off5va，是獨立重新推導）

在看 round428 交棒之前，先手動查了 off5v discordant 的 6 個「只有 OFF5V
漏出」的題目（`mbppplus_Mbpp/305,427,593,736,739,790`），逐題攤開 ON 那一列
的完整欄位：

```
305/593/739/427: passed_review=True, visible_ok=True, audited=True, audit_ok=False -> accepted=False
736/790:         passed_review=True, visible_ok=False (revision 也失敗)          -> accepted=False（跟稽核無關）
```

4/6 是被 `audited=True, audit_ok=False` 擋下——`gain_run.py:566` 的 `audit_ok`
是拿**跟計分用的同一個 `t["hidden_check"]["code"]`** 對已選定的 `code` 跑
`meets_demand()`；`accepted = visible_ok and (audit_ok is not False)`。也就是
稽核抽到的 20% 子樣本，只要底層答案本來就是錯的，`accepted` 在程式碼層級
就**必然**是 False——這不是「審查判斷力比較好」，是稽核那一刻直接偷看了
跟計分用的同一份 oracle。

再往上一層量整個 ON 臂（n=101）驗證這不是巧合：

```
ON wrong (meets_demand=False) 列：24
  audited=True 的 5 列：全部 accepted=False（程式碼保證，non-negotiable）
  audited=False 的 19 列：9 漏出、10 被 visible_ok 擋下
反事實（拿掉稽核閘、只靠 visible_ok）漏出率：13/101 = 12.87%
實際（含稽核閘）漏出率：              9/101 = 8.91%
稽核閘單獨解釋了約 4pp 的漏出率下降
```

## 這不是新發現——round388 已經建過完整的控制組工具

查完才發現 `ops/gain/analyze_off5va.py` docstring 開頭就是這段推理的完整版本
（round388），而且已經把它做成一個離線、零額外呼叫的公平對照：把**同一條
確定性稽核規則**套到 OFF5 自己選出的程式碼上（OFF5 的 `meets_demand` 早就
量過，直接拿來當「稽核結果」，不需要重跑），生成 OFF5VA，再跟 ON 重新配對。

本輪重跑：

```
$ python3 ops/gain/analyze_off5va.py --run runs/g_r356_3arm_20260830
=== OFF5+同稽核(A) vs ON（配對 n=91，其中 25 題被同一顆 hash 抽中稽核） ===
ON      漏出 8/91 = 8.79%
OFF5VA  漏出 10/91 = 10.99%
discordant: 只有 ON 漏出 b=0，只有 OFF5VA 漏出 c=2
McNemar 精確雙尾 p = 0.5000
gap (OFF5VA - ON) = 2.20pp
```

跟 GAIN_STATE 歷史紀錄裡 round388 起的軌跡完全一致（discordant 恆為
`(0,2)`，同一組題目 736/790——正是本輪獨立查出的、**不**靠稽核閘、而是靠
`visible_ok` 擋下的那 2 個，見上面）：

```
off5va (b,c)  (0,2) (0,2) (0,2) (0,2) (0,2)   <- 本輪第 5+ 個檢查點，依舊不動
off5va p      0.50  0.50  0.50  0.50  0.50
off5va gap    3.28pp 3.17pp 3.13pp 2.99pp 2.20pp
```

## 結論

**兩件事同時為真、不衝突**：

1. **off5v（原始版）**：ON 顯著優於 OFF5V（p=0.0312，discordant (0,6)，
   round342/388/392/401/427/428/429 七個檢查點穩定）。
2. **off5va（稽核曝光公平版）**：ON 與 OFF5VA 沒有顯著差異（p=0.50，
   discordant (0,2) 恆定，round388 起至少 5 個檢查點穩定）。

差額（off5v 顯著、off5va 不顯著）的機制解釋是**稽核曝光不對等**：`audit_rate=0.2`
的確定性稽核是 SPEC_GAIN 明文列出的 ON 三個子機制之一（路由＋K=3 審查＋
**抽樣稽核**，`SPEC_GAIN.md:48`），本身不是 bug、也不是作弊——但它結構性地
保證「被抽到稽核、且底層答案是錯的」這格永遠不漏出，跟審查／修訂的判斷力
無關。**這個結構性保障是 ON 唯一結構性擁有、OFF5(V) 定義上不可能有的東西**
（self-consistency 沒有「偷看隱藏測資」這一步）。off5va 把這道閘公平地也
給 OFF5，差距立刻從顯著掉到不顯著——證明 off5v 的顯著性主要來自稽核曝光，
不是同儕評審機制本身的判斷力。

**對 round428 的修正**：round428 說「`mechanism_contributes` 判定從未動搖過」
是對 off5v 本身而言正確的，但沒有帶上 off5va 的警語，讀起來像是「Vacant 的
審查／修訂機制被驗證有效」——這句話目前的證據只支持到「Vacant 的稽核子
機制有效（且稽核本來就是直接查 oracle，效果保證）」，**不支持**「同儕審查
本身比 self-consistency 聰明」。**不修改 round428 的原始文字**（保留歷史），
本文件是修正性的補充。

**對 R411（主判準）沒有影響**：R411 從一開始就沒有依賴 off5v/off5va，這條
線一直是補充的機制層級調查。

## 下一輪該做什麼

- 若有心力：off5va 剩下的 736/790 兩題，round388 已定性為「獨立生成雜訊」
  （不是稽核閘、也不是特定機制的系統性盲區），可以再逐題翻一次驗證這個
  定性是否隨 n 增長還成立（732/790 之外有沒有第三題加入 discordant）。
- **未來只要重跑 off5v，一定要同時重跑 off5va 附帶警語**——否則同樣的
  誤導會再發生一次（這是第二次：round428 是第一次漏寫警語）。
- 本文件不建議新增判準或修改 `gain_run.py`——稽核機制本身的設計沒有問題，
  問題只在敘事：報 off5v 顯著性時要同時報 off5va 的警語，否則歸因會錯。
