#!/usr/bin/env bash
# smoke_vm.sh — 「分身迴圈跑在 VM」那一條線的實跑冒煙（Mac 這一側：佈、敲、收、拆）。
#
# 人類裁決（2026-09-24）：分身迴圈跑在 vacant-dev（1003 上的 VM），不在 1003 Windows 上。
# VM 那一側做什麼寫在 `smoke_vm.py` 的 docstring；這一支負責 VM 自己做不到的兩件事：
#   1. **從 1003 敲 VM**（電視的瀏覽器在 1003 上，它要讀得到 VM 的 18420／18899／18901）；
#   2. **拆乾淨**：VM 上的暫存與 kit 全刪、確認沒有 vacant-smoke-* unit 留著。
#
# ⚠ vacant-dev 只有 38 G，而且每份 repo clone 786 M（memory：vacant-dev 磁碟陷阱）
#   ⇒ 這裡只送一個 ~2 MB 的 kit（vacant_network ＋ ops/exhibit/twin ＋ 圍牆那幾支），
#   而且**只有一份**：每一位分身都用這一份唯讀簽出，不會各自 clone。
# ⚠ `ssh 1003` 別名會解析到假位址——一律用 IP（e2e_1003.sh 同一條）。
#
#   bash ops/exhibit/twin/smoke_vm.sh
set -u
WT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
VM="${VM:-user1@100.124.254.83}"
W1003="${W1003:-w401@100.119.113.56}"
#: VM 在 VMnet8 上的位址（1003 從這裡敲它）。**DHCP 發的**——布展時要固定（見 START.md）。
VMIP="${VMIP:-192.168.76.135}"
BASE="${BASE:-/var/tmp/vacant_twin_vm_smoke}"
OUT="${OUT:-$WT/ops/exhibit/twin/evidence_vm_20260924}"
KIT="${TMPDIR:-/tmp}/vacant_twin_vm_kit.$$.tgz"
SSH=(ssh -o BatchMode=yes -o ConnectTimeout=25 -o ControlMaster=no -o ControlPath=none)

mkdir -p "$OUT"
echo "證據目錄：$OUT"

( cd "$WT" && COPYFILE_DISABLE=1 tar czf "$KIT" --no-xattrs \
    --exclude='__pycache__' --exclude='*.pyc' \
    --exclude='ops/exhibit/twin/evidence_*' --exclude='ops/exhibit/twin/narrative_wire_*' \
    --exclude='ops/exhibit/twin/wait_v2_*' --exclude='ops/exhibit/twin/store' \
    vacant_network ops/exhibit/twin ops/vacantrun/enclosure_20260920/bin \
    ops/vacantrun/wrap_agent.sh examples/twin_viewer.html 2>/dev/null )
ls -la "$KIT"
"${SSH[@]}" "$VM" "rm -rf $BASE && mkdir -p $BASE/repo" || exit 2
scp -q -o BatchMode=yes -o ControlPath=none "$KIT" "$VM:$BASE/kit.tgz" || exit 2
"${SSH[@]}" "$VM" "tar xzf $BASE/kit.tgz -C $BASE/repo 2>/dev/null; rm -f $BASE/kit.tgz; du -sh $BASE/repo"
rm -f "$KIT"

# VM 那一側在背景跑（它會停在「等 1003」的關卡上）
"${SSH[@]}" "$VM" "cd $BASE/repo && python3 ops/exhibit/twin/smoke_vm.py --base $BASE" \
    > "$OUT/remote_stdout.log" 2>&1 &
RPID=$!

echo "等 VM 那一側走到 1003 關卡……"
for _ in $(seq 1 240); do
  "${SSH[@]}" "$VM" "test -f $BASE/READY_FOR_1003" 2>/dev/null && break
  kill -0 $RPID 2>/dev/null || break
  sleep 5
done

# ── 從 1003 敲 VM（電視的瀏覽器就在這一台）──────────────────────────────
"${SSH[@]}" "$W1003" "export PYTHONIOENCODING=utf-8
for u in http://$VMIP:18899/state http://$VMIP:18901/visitors.json \
         http://$VMIP:18420/world3/index.html http://$VMIP:18899/live/events.jsonl \
         http://$VMIP:18899/phone.html; do
  printf '%s ' \"\$u\"
  curl -sS --max-time 10 -o /dev/null -w '%{http_code} %{size_download}\n' \"\$u\" 2>&1
done
echo '--- visitors.json intake ---'
curl -sS --max-time 10 http://$VMIP:18901/visitors.json | python -c \"import json,sys;d=json.load(sys.stdin);print(json.dumps({'intake':d.get('intake'),'people':len(d.get('people') or []),'engines':[((p.get('run') or {}).get('engine') or p.get('engine')) for p in d.get('people') or []]},ensure_ascii=False))\"
echo '--- /state.live ---'
curl -sS --max-time 10 http://$VMIP:18899/state | python -c \"import json,sys;d=json.load(sys.stdin);print(json.dumps({k:d.get(k) for k in ('mode','live')},ensure_ascii=False)[:1500])\"
" > "$OUT/from_1003.txt" 2>&1
cat "$OUT/from_1003.txt"
"${SSH[@]}" "$VM" "touch $BASE/DONE_1003"

wait $RPID
echo "VM 那一側結束（rc=$?）"
scp -q -r -o BatchMode=yes -o ControlPath=none "$VM:$BASE/evidence/." "$OUT/" || echo "⚠ 證據拷不回來"

# ── 拆：VM 上的暫存全刪、確認沒有 unit 留著 ─────────────────────────────
"${SSH[@]}" "$VM" "sudo -n systemctl stop vacant-smoke-exhibit vacant-smoke-loop 2>/dev/null
rm -rf $BASE /var/tmp/vtw_probe /var/tmp/vtw_kit.tgz
echo UNITS_LEFT=\$(systemctl list-units --all --no-legend 'vacant-smoke-*' | wc -l)
echo BASE_EXISTS=\$(test -e $BASE && echo yes || echo no)
df -h / | tail -1" | tee "$OUT/teardown.txt"
