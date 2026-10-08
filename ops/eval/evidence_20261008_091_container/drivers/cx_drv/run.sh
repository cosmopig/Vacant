#!/bin/bash
B=$1; S=$2; M=$3
D=/tmp/claude-0/e2e091/evidence/codex/${B}_${S}_${M}
rm -rf $D; mkdir -p $D
docker run --rm --network none --name cx-$B-$S-$M -v /home/user/Vacant/ops/intake:/m:ro -v /tmp/claude-0/e2e091/cx_drv:/drv:ro -v $D:/o vacant091-e2e python3 /drv/drive.py $B $S $M > $D/driver.log 2>&1
echo "$B $S $M rc=$?"; tail -2 $D/driver.log
