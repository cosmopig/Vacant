#!/usr/bin/env bash
exec python3 /opt/eval/bin/driver_i1001.py --phase auto --slots 4 --prefix t4 --deadline 2026-10-02T23:00:00Z --logfile /srv/eval/driver_t4.log --agent-timeout 60 --proxy http://127.0.0.1:18950
