#!/bin/bash
# usage: run1.sh <name> <driver args...>
N=$1; shift
D=/tmp/claude-0/e2e091/evidence/opencode1/$N; rm -rf $D; mkdir -p $D
docker run --rm --network none --name oc1-$N -v /tmp/claude-0/e2e091/oc1drv:/d:ro -v /tmp/claude-0/e2e091/oc1drv:/m:ro -v $D:/o vacant091-e2e:latest bash /d/inside.sh "$@" > $D/container.log 2>&1
echo "$N rc=$?"; cat $D/container.log | tail -3
