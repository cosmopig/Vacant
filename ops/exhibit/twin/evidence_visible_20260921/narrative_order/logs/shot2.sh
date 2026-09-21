#!/bin/bash
# shot2.sh <outdir> <name> <query> [dwell] [port] [baseurl]
set -u
HM=/Users/cosmopig/Documents/GitHub/vacant_hm
out="$1"; name="$2"; q="$3"; dwell="${4:-14000}"; port="${5:-9501}"
base="${6:-http://127.0.0.1:8472/stage/index.html}"
mkdir -p "$out"
cd "$HM" || exit 2
node tools/twinshot.mjs "$out/$name.png" "$base$q" "$dwell" "$port"
