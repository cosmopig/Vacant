#!/usr/bin/env bash
# 發射：凍結佇列（種子 20260924 洗牌）、寫發射紀錄（預註冊與 manifest 的 sha256、程式碼版本、pi 設定 sha256）、
# 起三個 worker。用法：bcb_launch.sh <預註冊檔的路徑> <7小時的秒數，預設 25200>
set -u
R=/var/tmp/vacant_piext_20260924; RUN=$R/bcb_run; T=$R/bcb_tools; B=$R/bcb
prereg=$1; dur=${2:-25200}
[ -e $RUN/launch_record.json ] && { echo "已經發射過（$RUN/launch_record.json），停。"; exit 2; }
mkdir -p $RUN/claims $RUN/1004 $RUN/1003 $RUN/gemini
sort /var/tmp/vacant_piext_20260924/bcb_tools/usable_dirs.txt > $RUN/tasks_sorted.txt   # 用 manifest 的 usable_dirs，不靠列目錄
python3 -c "
import random,sys
ids=[l.strip() for l in open('$RUN/tasks_sorted.txt') if l.strip()]
random.Random(20260924).shuffle(ids); open('$RUN/queue.txt','w').write('\n'.join(ids)+'\n')"
now=$(date +%s); echo $((now + dur)) > $RUN/deadline_epoch
python3 - "$prereg" <<PYL
import hashlib, json, sys, pathlib, time
R = pathlib.Path("$R"); RUN = R / "bcb_run"
sha = lambda p: hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
rec = {"launched_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
       "deadline_epoch": int((RUN / "deadline_epoch").read_text()),
       "prereg": sys.argv[1], "prereg_sha256": sha(sys.argv[1]),
       "bank_manifest_sha256": sha(R / "bcb/bank/bank_manifest.json") if (R / "bcb/bank/bank_manifest.json").exists() else None,
       "n_tasks": sum(1 for _ in open(RUN / "queue.txt")),
       "queue_sha256": sha(RUN / "queue.txt"), "seed": 20260924,
       "code": {b: (R / f"pilot_{b}/repo/GIT_HEAD").read_text().strip() for b in ("1004", "1003", "gemini")},
       "pi_settings_sha256": {f"{b}/{h}": {f: sha(R / f"pilot_{b}/{h}/.pi/agent/{f}") for f in ("models.json", "settings.json")}
                              for b in ("1004", "1003", "gemini") for h in ("home_off", "home_on")}}
(RUN / "launch_record.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1))
print(json.dumps({k: rec[k] for k in ("launched_utc", "n_tasks", "prereg_sha256", "bank_manifest_sha256")}, ensure_ascii=False))
PYL
# pilot（R534，描述性）的迴圈停掉：不再開新格；正在跑的格子讓它跑完（worker 會等）
for p in $(pgrep -f "pilot_tools/run_(sync|serial).sh"); do kill $p && echo "停掉 pilot 迴圈 $p"; done
for b in 1004 1003 gemini; do BACKEND=$b setsid nohup bash $T/bcb_worker.sh > /dev/null 2>&1 < /dev/null & done
sleep 2; pgrep -af bcb_worker | cut -c1-80
