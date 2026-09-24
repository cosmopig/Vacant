#!/usr/bin/env bash
R=/var/tmp/vacant_piext_20260924
for t in lcb_3522 lcb_3584 lcb_3649 lcb_3715 lcb_3789; do
  bash $R/tools/task_cell.sh $t 1 >> $R/logs/tasks.progress 2>&1
done
echo ALLDONE >> $R/logs/tasks.progress
