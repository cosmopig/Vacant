#!/usr/bin/env bash
# 發射一批（VM，root）：收好上一批的狀態 → 寫發射紀錄（所有釘住東西的 sha256）→ 起打包、可行性、驅動（setsid，脫離 kernel）。
# 用法：launch_batch.sh <前綴> <plan.json> <位置數> <時間上限 UTC> <預註冊檔名>
set -euo pipefail
P=$1; PLAN=$2; SLOTS=$3; DL=$4; PREREG=$5
E=/srv/eval; TS=$(date -u +%Y%m%dT%H%M%SZ)
# 1) 上一批的狀態搬走（格子已經打包過；這裡只是讓進度檔、完成旗標從零開始）
if [ -f $E/progress.jsonl ] || [ -f $E/DRIVER_DONE ]; then
  mkdir -p $E/prev/$TS && for f in progress.jsonl DRIVER_DONE STOP feasibility.json; do [ -e $E/$f ] && mv $E/$f $E/prev/$TS/; done
  [ -e $E/archive/PACKER_DONE ] && mv $E/archive/PACKER_DONE $E/prev/$TS/
fi
cp "$PLAN" $E/plan.json
# 2) 發射紀錄
python3 - "$P" "$SLOTS" "$DL" "$PREREG" > $E/launch_record_$P.json <<'EOF'
import hashlib, json, pathlib, subprocess, sys, time
p, slots, dl, prereg = sys.argv[1:]
h = lambda f: hashlib.sha256(pathlib.Path(f).read_bytes()).hexdigest()
def tree(d):
    m = hashlib.sha256()
    for f in sorted(pathlib.Path(d).rglob("*")):
        if f.is_file():
            m.update(str(f.relative_to(d)).encode() + b"\0" + hashlib.sha256(f.read_bytes()).digest())
    return m.hexdigest()
plan = json.loads(pathlib.Path("/srv/eval/plan.json").read_text())
banks = sorted({t["bank"] for t in plan["tasks"]})
sh = lambda c: subprocess.run(c, shell=True, capture_output=True, text=True).stdout.strip()
print(json.dumps({"prefix": p, "launched": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "slots": int(slots), "deadline": dl,
  "prereg": prereg, "plan_sha256": h("/srv/eval/plan.json"), "n_tasks": len(plan["tasks"]), "arms": plan["arms"], "seed": plan["seed"],
  "tools_sha256": {f.name: h(f) for f in sorted(pathlib.Path("/opt/eval/bin").rglob("*")) if f.is_file()},
  "wheel": {f.name: h(f) for f in pathlib.Path("/opt/eval/wheel").glob("*.whl")},
  "staged_tree_sha256": {b: tree(f"/srv/eval/staged/{b}") for b in banks},
  "model_safetensors_sha256": sh("sha256sum /content/gemma-4-12B-it-qat-w4a16-ct/model.safetensors | cut -d' ' -f1"),
  "vllm": sh("/content/venv-vllm/bin/python -c 'import vllm; print(vllm.__version__)'"),
  "pi": sh("PATH=/opt/eval/node/bin:$PATH /opt/eval/pi/bin/pi --version | tail -1"), "node": sh("/opt/eval/node/bin/node -v"),
  "gpu": sh("nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader"),
  "vllm_cmdline": sh("pgrep -af 'vllm serve' | grep -v pgrep | head -1 | cut -d' ' -f2-")}, indent=1))
EOF
cat $E/launch_record_$P.json | head -5
# 3) 起打包、可行性、驅動（setsid：kernel 重開也不會帶走它們）
cd $E
pgrep -f "opt/eval/bin/packer.py" >/dev/null || setsid nohup python3 /opt/eval/bin/packer.py --interval 600 >> $E/packer.log 2>&1 < /dev/null &
setsid nohup python3 /opt/eval/bin/feasibility.py --prefix "$P" >> $E/feasibility_$P.log 2>&1 < /dev/null &
setsid nohup python3 /opt/eval/bin/driver.py --plan $E/plan.json --slots "$SLOTS" --prefix "$P" --deadline "$DL" >> $E/driver_$P.log 2>&1 < /dev/null &
sleep 3; pgrep -af "opt/eval/bin/(packer|feasibility|driver)" | cut -c1-120
echo LAUNCHED $P
