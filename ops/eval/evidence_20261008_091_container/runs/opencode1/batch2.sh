#!/bin/bash
cd /tmp/claude-0/e2e091/oc1drv
for b in v091 v090; do
 ( ./run1.sh z1b-tui-$b --build $b --scn z1b --mode tui &
   ./run1.sh z3-tui-$b --build $b --scn z3 --mode tui &
   ./run1.sh z1-run-$b --build $b --scn z1 --mode run &
   wait )
done
