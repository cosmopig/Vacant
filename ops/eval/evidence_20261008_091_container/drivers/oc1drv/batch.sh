#!/bin/bash
cd /tmp/claude-0/e2e091/oc1drv
for b in v091 v090 none; do
 ( ./run1.sh z1-tui-$b --build $b --scn z1 --mode tui &
   ./run1.sh z2-root-tui-$b --build $b --scn z2 --mode tui --cwd / &
   ./run1.sh z2-home-tui-$b --build $b --scn z2 --mode tui --cwd /home/user &
   wait ) 
done
