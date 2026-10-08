FROM node:22-bookworm
COPY ctx/ca.crt /ca.crt
ENV NODE_EXTRA_CA_CERTS=/ca.crt NPM_CONFIG_CAFILE=/ca.crt PIP_CERT=/ca.crt SSL_CERT_FILE=/ca.crt REQUESTS_CA_BUNDLE=/ca.crt
ARG HTTPS_PROXY
ARG HTTP_PROXY
RUN apt-get update && apt-get install -y --no-install-recommends python3 python3-venv python3-pip git tmux procps ca-certificates \
 && rm -rf /var/lib/apt/lists/*
# Vacant: two venvs
COPY ctx/vacant_network-0.9.1-py3-none-any.whl /tmp/whl/
RUN python3 -m venv /opt/v091 && /opt/v091/bin/pip install -q /tmp/whl/vacant_network-0.9.1-py3-none-any.whl \
 && python3 -m venv /opt/v090 && /opt/v090/bin/pip install -q vacant-network==0.9.0
# Agent CLIs, each in its own npm prefix
RUN npm install -g --prefix /opt/npm/opencode2 @opencode/cli@2.0.24 \
 && npm install -g --prefix /opt/npm/opencode1 opencode-ai@1.18.35 \
 && npm install -g --prefix /opt/npm/pi @earendil-works/pi-coding-agent@0.87.1 \
 && npm install -g --prefix /opt/npm/claude @anthropic-ai/claude-code@2.1.293 \
 && npm install -g --prefix /opt/npm/codex @openai/codex@0.161.0 \
 && npm cache clean --force
# Convenience symlinks with unambiguous names
RUN mkdir -p /opt/agents/bin \
 && ln -s /opt/npm/opencode2/bin/opencode /opt/agents/bin/opencode2 \
 && ln -s /opt/npm/opencode1/bin/opencode /opt/agents/bin/opencode1 \
 && ln -s /opt/npm/pi/bin/pi /opt/agents/bin/pi \
 && ln -s /opt/npm/claude/bin/claude /opt/agents/bin/claude \
 && ln -s /opt/npm/codex/bin/codex /opt/agents/bin/codex
COPY ctx/harness /opt/harness
ENV PATH=/opt/agents/bin:$PATH
