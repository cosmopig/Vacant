#!/bin/bash
# root part: user + dirs, then drop to user
useradd -m -s /bin/bash user 2>/dev/null
mkdir -p /opt/oc1bin && ln -sf /opt/npm/opencode1/bin/opencode /opt/oc1bin/opencode
mkdir -p /work && chown user /work; chmod 777 / 2>/dev/null; chmod 777 /o
exec runuser -u user -- env HOME=/home/user python3 /d/drive.py "$@"
