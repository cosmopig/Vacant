#!/usr/bin/env bash
# 一格 ＝ 一題 × 真 pi 0.87.0 × 真模型（1004 經要金鑰的中繼）× **常駐 extension 那條路**。
#
# 與 possess_pi_real_20260922/tools/cell.sh 的刻意差異：
#   · 那批打 `$HOME/.vacant/possess/bin/pi`（PATH shim → gateshim → PI_CODING_AGENT_DIR 暫存目錄）；
#     本批打 pi 的**完整路徑**，不經 shim ⇒ pi 讀的是 `$HOME/.pi/agent/`，載入的是
#     `vacant install` 寫的**常駐** extension，模型呼叫走常駐 proxyd。
#   · 因此**沒有閘門、沒有收據**（shim 那條才有）。本批量的是通道，不是裁決。
# 其餘沿用：prompt、工作區四個檔、純度 fail-closed 擋門、模型 gemma-4-12b-it-qat。
set -u
source /var/tmp/vacant_piext_20260924/env.sh; export HOME=$R/home_p2_new_local PYTHONPATH=$R/repo_new
export MYLAB_KEY="$(cat $R/secret)"
TPL=$R/repo/ops/gain/r534/templates
PROMPT='Read goal.md and contract.md in this directory and do what they say. Use your tools to write the file.'
tid="$1"; rep="${2:-1}"; name="${tid}_r${rep}"
L=$R/cells/p2_new_local_task_$name; ws=$R/ws_p2/$name
mkdir -p "$L"; rm -rf "$ws"; mkdir -p "$ws"
cp "$TPL/$tid/goal.md" "$TPL/$tid/contract.md" "$TPL/$tid/run_tests.sh" "$ws/"
cp -r "$TPL/$tid/tests_visible" "$ws/"
want="./contract.md ./goal.md ./run_tests.sh ./tests_visible/test_visible.py"
got="$(cd "$ws" && find . -type f | sort | tr '\n' ' ' | sed 's/ $//')"
if [ "$got" != "$want" ]; then echo "工作區不乾淨，停。got: $got" >&2; exit 3; fi
jf=$HOME/.vacant/possess/proxyd/wire/index.jsonl
rb=$(wc -l < $R/logs/relay_alias.jsonl); jb=$(wc -l < $jf)
ls $HOME/.vacant/possess/hooks/ > $L/hooks_before.txt
{ echo "task=$tid rep=$rep"; echo "route=常駐 extension（pi 完整路徑，不經 shim）"
  echo "pi=$($PI --version)"; echo "prompt=$PROMPT"; echo "workspace_files=$got"
  echo "argv=cd <ws> && $PI -p '<PROMPT>'"; } > $L/argv.txt
t0=$(date +%s.%N)
( cd "$ws" && timeout 1500 $PI -p "$PROMPT" < /dev/null > $L/stdout 2> $L/stderr )
rc=$?; t1=$(date +%s.%N)
echo $rc > $L/rc; python3 -c "print(round($t1-$t0,1))" > $L/wall_s
tail -n +$((rb+1)) $R/logs/relay_alias.jsonl > $L/relay_slice.jsonl
tail -n +$((jb+1)) $jf > $L/proxyd_slice.jsonl
ls $HOME/.vacant/possess/hooks/ | sort | comm -13 <(sort $L/hooks_before.txt) - > $L/hook_files_new.txt
for h in $(cat $L/hook_files_new.txt); do cp $HOME/.vacant/possess/hooks/$h $L/; done
( cd "$ws" && find . -type f | sort ) > $L/workspace_after.txt
[ -f "$ws/solution.py" ] && cp "$ws/solution.py" $L/delivered_solution.py
( cd "$ws" && timeout 180 bash run_tests.sh > $L/visible.out 2>&1; echo $? > $L/visible.rc )
echo "=== $name rc=$rc wall=$(cat $L/wall_s)s visible_rc=$(cat $L/visible.rc)"
