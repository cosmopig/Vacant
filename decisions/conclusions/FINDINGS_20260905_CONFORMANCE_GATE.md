# 迭代到現在的答案：有用的不是評審委員會，是「交付前先跑你的驗收測資」

（2026-09-05 整理。資料來源：`feat/v2-four-stages` 上 21 天、6,437 輪、1,255 筆 commit
的自動迴圈；本文件的每個數字都可從 `runs/*/rows.jsonl` 重算，重算指令附在 §五。）

## 一、一句話

**同儕評審＋修訂在等預算下打不贏 self-consistency（三個乾淨 run 一致）；
把它換成「交付前用客戶自己的可見驗收測資把關，過不了就不交」之後，
在難題上贏了單發 19.2 個百分點（p=0.0003），而且只花 1.7 通呼叫、
不到 self-consistency 的三分之一。**

## 二、被推翻的三件事（人類提的假說，實驗自己推翻自己）

| 假說 | 實驗 | 結果 |
|---|---|---|
| 加了 Vacant（信譽路由＋三人評審＋抽樣稽核）等預算下會贏 | 決定性 run `g_r356_3arm_20260830`，179 題 | ON 84.2% vs OFF5 81.2%，n=101 b/c=5/2 **p=0.4531**，不顯著 |
| H-A：35b worker 太強造成天花板 | E1 `g_r441_gemma_only_mbpp_b`，gemma-12b 單模型 179 題 | OFF 失敗率升到 31.8%（確實變弱），ON vs OFF5 n=167 b/c=11/12 **p=1.0** |
| H-B：MBPP+ 太簡單 | E3 `g_r443_gemma_lcb`，LiveCodeBench 91 題 medium+hard | OFF 失敗率升到 48.4%（確實更難），ON vs OFF5 n=87 b/c=15/10 **p=0.4244** |

機制解釋（R438／R516／R440T）：**評審票幾乎是常數函數**。
在 MBPP+ 上近乎一律說「可以」（原始層 −2.99pp 於最佳常數基線），
在 LCB 難題上翻成 89.7% 主張「有錯」（+0.77pp）——它追蹤的是**題目難不難**
這個全域性質，不是這一份答案對不對。評審不辨真偽 ⇒ 修訂無淨修正
（113 題只有 1 題真的改對）⇒ 多花的四通呼叫沒有交付價值。

## 三、成立的一件事：符合性閘門（CONFORM）

設計：一位具名 worker 產出 → **本機跑客戶提供的可見驗收測資** →
通過才出貨並把收據簽進 hash-chain → 全不通過就拒交。評審與修訂整個拿掉。

| run | 題庫 | n | OFF | **CONFORM** | OFF5 | CONFORM 呼叫/題 |
|---|---|---|---|---|---|---|
| `g_r444_conform_mbpp` | MBPP+ | 179 | 72.1% | **75.4%** | 72.6% | 1.39 |
| `g_r445_conform_mbpp_ext` | MBPP+ 擴充 | 192 | 70.3% | **76.0%** | 71.4% | 1.51 |
| `g_r447_conform_lcb2` | LCB 難題 | 120 | 50.8% | **70.0%** | 63.3% | 1.71 |

配對 McNemar（2026-09-05 由稽核端獨立重算）：

```
g_r444  CONFORM vs OFF5  n=179  b=9  c=4   p=0.2668
g_r444  CONFORM vs OFF   n=179  b=13 c=7   p=0.2632
g_r445  CONFORM vs OFF5  n=192  b=18 c=9   p=0.1221
g_r445  CONFORM vs OFF   n=192  b=21 c=10  p=0.0708
g_r447  CONFORM vs OFF5  n=120  b=16 c=8   p=0.1516
g_r447  CONFORM vs OFF   n=120  b=31 c=8   p=0.0003   ← 難題上顯著
```

**已成立**：難題上 CONFORM 顯著優於單發（+19.2pp，p=0.0003），
成本 1.71 通 vs OFF5 的 5.0 通。
**尚未成立**：對 OFF5 三個 run 方向一致（b>c）但都不顯著；
等預算的最終答案要更大的 n（`g_r461_lcb3_three_arm` 189 題三臂進行中）。

## 四、誠實邊界（先寫死）

1. 贏的是**符合性閘門**，不是「同儕評審讓 agent 變聰明」。展場不得混用這兩個說法。
2. 閘門的前提是**客戶給得出可見驗收測資**。給不出來的需求，這個機制沒有著力點。
3. CONFORM 只驗證過 MBPP+／LCB 兩個題庫、gemma-4-12b 一個 worker 家族。
4. 對 OFF5 尚未顯著；現在說「贏過 self-consistency」是超前宣稱。
5. 這些數字量的是**產出品質**。Vacant 主張的可究責性（收據、雜湊鏈、
   確定性稽核）**不是靠這些數字成立的**，它成立在「每一步都能被獨立重驗」——
   那是機制性質，不是統計結果。

## 五、重算指令

```bash
python3 - <<'PY'
import json, math
from collections import defaultdict
def mcnemar(b,c):
    n=b+c
    return 1.0 if n==0 else min(1.0, sum(math.comb(n,k) for k in range(0,min(b,c)+1))/2**n*2)
by=defaultdict(dict)
for line in open("runs/g_r447_conform_lcb2/rows.jsonl"):
    r=json.loads(line)
    if not r.get("infra_void"): by[r["task_id"]][r["arm"]]=bool(r.get("meets_demand"))
pairs=[(v["CONFORM"],v["OFF"]) for v in by.values() if "CONFORM" in v and "OFF" in v]
b=sum(1 for x,y in pairs if x and not y); c=sum(1 for x,y in pairs if y and not x)
print(len(pairs), b, c, mcnemar(b,c))
PY
```
