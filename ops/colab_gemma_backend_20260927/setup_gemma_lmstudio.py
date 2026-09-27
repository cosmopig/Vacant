#!/usr/bin/env python3
"""在 Colab（或任何 Linux＋NVIDIA）上把 1003／1004 的 gemma 後端複製出來。每一步寫進 /content/setup.log。

對齊的四樣（2026-09-27 查到的事實）：
  1. GGUF：google/gemma-4-12B-it-qat-q4_0-gguf 的 **revision f6e7774e6148**（06-05 首發版），
     主模型 sha256 faff1a63…、mmproj e70b0e5c…——HF main 7/17 已換成修正版，直接抓 main 不是同一個檔。
  2. 引擎：LM Studio llama.cpp cuda12 **@2.46.0**（＝1004；1003 是 2.34.0）。
  3. 載入參數：context 262144、parallel 4、GPU max、identifier gemma-4-12b-it-qat（兩台 `lms ps` 一致）。
  4. 思考：這個組合預設會思考；分支用 reasoning_effort:"none" 關（呼叫端的事，這裡不改）。
⚠ 輸出不會與 1004 逐位元相同（不同 GPU 的數值差異）；對得上的是權重、引擎版本與參數。
"""
import hashlib, json, os, pathlib, subprocess, sys, time

LOG = open("/content/setup.log", "a", buffering=1)
def log(*a):
    print(time.strftime("%H:%M:%S"), *a, file=LOG, flush=True)
def sh(c, t=1800):
    r = subprocess.run(c, shell=True, capture_output=True, text=True, timeout=t)
    out = (r.stdout + r.stderr).strip()
    log(f"$ {c[:140]}  → rc={r.returncode}\n{out[-1500:]}")
    return r.returncode, out

L = "/root/.lmstudio/bin/lms"
REV = "f6e7774e6148da3b7f201e42ba37cf084c1db35f"
ENGINE = "llama.cpp-linux-x86_64-nvidia-cuda12-avx2@2.46.0"
WANT = {"gemma-4-12b-it-qat-q4_0.gguf": "faff1a63667fac17ac5e777f47114688fcefea96e220e211aaa8d62c2c4561f1",
        "mmproj-gemma-4-12b-it-qat-q4_0.gguf": "e70b0e5cd80323d5d588b4ed06780356b7b1ba03995a4b8164c6ae9db0ff5989"}
DST = pathlib.Path("/root/.lmstudio/models/google/gemma-4-12B-it-qat-q4_0-gguf")

log("==== 開始", json.dumps({"rev": REV, "engine": ENGINE}))
sh("nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader; free -g | head -2; nproc")
if not os.path.exists(L):
    sh("curl -fsSL https://lmstudio.ai/install.sh | bash 2>&1 | tail -5")
sh(f"{L} runtime get -y --allow-incompatible '{ENGINE}' 2>&1 | tail -2")
sh(f"{L} runtime select '{ENGINE}' 2>&1 | tail -2; {L} runtime ls 2>&1 | head -8")

from huggingface_hub import hf_hub_download
DST.mkdir(parents=True, exist_ok=True)
ok = True
for fn, sha in WANT.items():
    p = hf_hub_download("google/gemma-4-12B-it-qat-q4_0-gguf", fn, revision=REV, local_dir=str(DST))
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 24), b""):
            h.update(b)
    got = h.hexdigest(); ok &= got == sha
    log(f"檔案 {fn} {os.path.getsize(p)} {got} {'MATCH' if got == sha else 'MISMATCH（要 ' + sha + '）'}")
if not ok:
    log("==== 停：sha256 對不上，不載入"); sys.exit(2)

rc, out = sh(f"{L} load gemma-4-12b-it-qat --context-length 262144 --parallel 4 --gpu max --identifier gemma-4-12b-it-qat -y 2>&1 | tail -4")
sh(f"{L} ps --json 2>&1 | head -c 600")
subprocess.Popen(f"nohup {L} server start --port 1234 > /content/lms_server.log 2>&1 &", shell=True)
time.sleep(8)
sh("curl -s localhost:1234/v1/models | head -c 200; nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader")
log("==== SETUP_DONE" if rc == 0 else "==== SETUP_LOAD_FAILED")
