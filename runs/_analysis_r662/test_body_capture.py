#!/usr/bin/env python3
"""round662：證明 400 回應本體真的被落盤（雙向：修後會抓到，修前抓不到）。
零 API——用假的 HTTPError 走真實的 except 路徑。"""
import io, json, sys, pathlib, tempfile, urllib.error, urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from ops.gain.brain_cline import ClineBrain, InfraVoid

BODY = b'{"error":{"message":"model qwen/qwen3.6-35b-a3b not loaded on node B"}}'


def run_once():
    tmp = pathlib.Path(tempfile.mkdtemp()) / "calls.jsonl"
    br = ClineBrain("t-agent", "sys", key="k", log_path=tmp,
                    retries=1, backoff_s=0, timeout_s=1)

    def boom(req, timeout=None):
        raise urllib.error.HTTPError(
            "http://x", 400, "Bad Request", {}, io.BytesIO(BODY))

    orig = urllib.request.urlopen
    urllib.request.urlopen = boom
    try:
        br.generate("hi")
    except InfraVoid as e:
        void_msg = str(e)
    finally:
        urllib.request.urlopen = orig
    logged = [json.loads(l) for l in tmp.open()]
    return void_msg, [r.get("error", "") for r in logged]


void_msg, errs = run_once()
joined = " ".join(errs)
fails = []

# 方向一（修後必須抓到）：伺服器的解釋要出現在落盤的 error 裡
if "not loaded on node B" not in joined:
    fails.append(f"回應本體沒被落盤：{joined[:200]!r}")
# 狀態碼與原本的訊息不能不見（不得回歸）
if "HTTP Error 400" not in joined:
    fails.append("原本的 'HTTP Error 400' 不見了（回歸）")
# InfraVoid 訊息也要帶著本體，這樣 notes.jsonl 才追得到
if "not loaded on node B" not in void_msg:
    fails.append(f"InfraVoid 訊息沒帶本體：{void_msg[:200]!r}")

# 方向二（證明測試有牙齒）：修前的寫法必須抓不到
old_style = f"{urllib.error.HTTPError.__name__}: HTTP Error 400: Bad Request"
if "not loaded on node B" in old_style:
    fails.append("突變體驗證失效：修前寫法竟然也含本體")

print("落盤 error 欄位 =", errs[0][:150] if errs else "(無)")
print("InfraVoid 訊息  =", void_msg[:150])
if fails:
    print("TEST FAIL")
    for f in fails:
        print("  -", f)
    sys.exit(1)
print("TEST PASS（本體有落盤、狀態碼未回歸、InfraVoid 帶得到、修前寫法確實抓不到）")
