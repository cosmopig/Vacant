#!/bin/bash
for M in p tui; do for S in Z1 Z2root Z2home Z3; do
  for B in v091 v090 none; do ./run.sh $B $S $M & done; wait
done; done
