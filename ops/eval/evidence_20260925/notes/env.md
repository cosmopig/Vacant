# env probe — working notes (2026-09-25)

See RECIPE.md in this same dir for the final writeup. This file is just the
scratch log of what was run, in order.

1. Read MODELS.md and orq/ listing (context only, no model calls made here —
   per task rule, research/probe agents do not call the OpenRouter key).
2. `docker run --rm --network host -e HTTPS_PROXY=... -v .../ca-bundle.crt:/etc/ssl/certs/ca-certificates.crt:ro curlimages/curl -sS https://pypi.org/simple/` -> 200.
3. Batch of curl checks (npm, github api, raw github, hf, openrouter) inside
   one container -> npm/raw_github/hf/openrouter 200, api.github.com FAILED
   (SSL self-signed-in-chain, exit 60) despite the mount.
4. Retried 3x -> consistently fails for api.github.com only.
5. Host-side curl --cacert to same URL -> 200, so the CA bundle itself is fine;
   problem is container-side trust config.
6. Checked `curl -V` in the image -> musl/OpenSSL build.
7. `curl -v` showed `CAfile: /cacert.pem` (image's own baked-in bundle,
   ignores the mount at /etc/ssl/certs/ca-certificates.crt and ignores
   SSL_CERT_FILE env var).
8. `--cacert /etc/ssl/certs/ca-certificates.crt` explicit -> works (200).
   `SSL_CERT_FILE=...` -> still fails. `CURL_CA_BUNDLE=...` -> works (200).
   -> curl-specific env var quirk, documented in RECIPE.md.
9. Checked proxy status (`$HTTPS_PROXY/__agentproxy/status`) -> noProxy list
   explains why pypi/npmjs bypass the proxy entirely (direct, no MITM issue
   possible); api.github.com is not in that list and IS MITM'd by the proxy
   (consistent with gitConfigInjection/gitSshRewrite flags in the status),
   while raw.githubusercontent.com/huggingface.co/openrouter.ai go through the
   proxy as plain passthrough (no re-terminated cert, so the image's default
   trust already works for them).
10. docker build test: python:3.11-slim + `pip install requests` via
    --build-arg HTTPS_PROXY/HTTP_PROXY + COPY'd ca bundle + PIP_CERT -> built
    in ~10s, PyPI resolved fine (direct, noProxy).
11. node:22 pull + npm install -g for the 4 agent packages, using
    `npm config set cafile/proxy/https-proxy` (registry.npmjs.org is noProxy
    so likely didn't strictly need the CA bundle, but set defensively) -> all
    4 (pi, opencode-ai, @openai/codex, @anthropic-ai/claude-code) installed
    exit 0.
12. df -h before/after, docker images sizes, docker info CPU/mem, cgroup
    limit files (none found) -> recorded in RECIPE.md.
13. Cleanup: `docker rmi vacant-env-probe:pip-test curlimages/curl:8.10.1
    node:22` -> docker images empty, df back to baseline.

No model API calls made. No credential files read. Peak disk usage during
probes ~1.9GB (under 3GB budget), fully cleaned up afterward.
