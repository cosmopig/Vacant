#!/usr/bin/env bash
# 發射（VM，root）：先確認 selfcheck 過了 → 搬走上一批的狀態 → 寫發射紀錄 → 起 packer（鏡像到 Drive）／可行性／收尾／driver（setsid 脫離 kernel）。
# 用法：launch_i1001.sh <前綴> <位置數> <時限 UTC，例 2026-10-02T06:00:00Z> [Drive 鏡像目錄，預設 /content/drive/MyDrive/vacant_i1001] [driver 的額外參數…]
# driver 預設 `--phase auto`：篩選（任務題庫各 10 題、只跑 A）→ 天花板規則 → 主跑（A＋C、R／K 巢狀）。
set -euo pipefail
P=$1; SLOTS=$2; DL=$3; MIRROR=${4:-/content/drive/MyDrive/vacant_i1001}; shift $(( $# < 4 ? $# : 4 )) || true
E=/srv/eval; TS=$(date -u +%Y%m%dT%H%M%SZ)
python3 - <<PY || { echo "selfcheck 沒過（或沒跑）：先 python3 /opt/eval/bin/vm_selfcheck.py --scenarios a,k,r,timeout,void,driver,c" >&2; exit 2; }
import json, sys
d = json.load(open("$E/_selfcheck/selfcheck.json"))
sys.exit(0 if d.get("ok") else 1)
PY
[ -d "$(dirname "$MIRROR")" ] || echo "WARN: $(dirname "$MIRROR") 不存在——Drive 沒掛（colab drivemount）？packer 的鏡像會失敗，只剩 VM 上與本機同步兩份"
mkdir -p "$MIRROR" 2>/dev/null || true
SHIM=$(python3 -c "import json; d=json.load(open('$E/_selfcheck/selfcheck.json')); print('$E/_selfcheck/shim' if d.get('bridge_shim') else '')")
# 上一批的狀態搬走（格子已經打包過；這裡只讓進度檔、完成旗標從零開始）
if [ -f $E/progress.jsonl ] || [ -f $E/DRIVER_DONE ] || [ -f $E/STOP ]; then
  mkdir -p $E/prev/$TS && for f in progress.jsonl DRIVER_DONE STOP ALL_DONE feasibility_i1001.json; do [ -e $E/$f ] && mv $E/$f $E/prev/$TS/ || true; done
  for f in PACKER_DONE MIRROR_OK MIRROR_BAD; do [ -e $E/archive/$f ] && mv $E/archive/$f $E/prev/$TS/ || true; done
fi
python3 /opt/eval/bin/launch_record.py "$P" "$SLOTS" "$DL" "$MIRROR" | head -3
cd $E
# packer_i1001.py＝packer.py 的外殼（driver 一寫 DRIVER_DONE 就收尾，不多睡最多 10 分鐘）；`if` 包起來，免得 `||` 清單的子殼抓著輸出管線不放
if ! pgrep -f "opt/eval/bin/packer_i1001.py" >/dev/null; then
  setsid nohup python3 /opt/eval/bin/packer_i1001.py --interval 600 --mirror "$MIRROR" >> $E/packer.log 2>&1 < /dev/null &
fi
setsid nohup python3 /opt/eval/bin/feasibility_i1001.py --prefix "$P" >> $E/feasibility_$P.log 2>&1 < /dev/null &
setsid nohup python3 /opt/eval/bin/finalize_vm.py --mirror "$MIRROR" >> $E/finalize_$P.log 2>&1 < /dev/null &
SHIMARG=(); [ -n "$SHIM" ] && SHIMARG=(--shim-dir "$SHIM")
setsid nohup python3 /opt/eval/bin/driver_i1001.py --phase auto --slots "$SLOTS" --prefix "$P" --deadline "$DL" \
  --logfile $E/driver_$P.log "${SHIMARG[@]}" "$@" >> $E/driver_$P.log 2>&1 < /dev/null &
sleep 3; pgrep -af "opt/eval/bin/(packer_i1001|feasibility_i1001|finalize_vm|driver_i1001)" | cut -c1-140
echo LAUNCHED $P
