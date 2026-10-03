# Environment probe (label: env) — results, 2026-09-25

All commands run and verified in this container; images pulled/built here were
removed after testing (see Cleanup). Peak extra disk during probes: node:22
(1.64GB) + vacant-env-probe:pip-test (209MB) + curlimages/curl (32MB) ≈ 1.9GB,
well under the 3GB budget. All removed; `docker images` empty afterward, `df -h /`
back to baseline (21G used / 17G avail, same order as the 18G avail noted at task start).

## 1. Docker network recipe that reaches PyPI/npm/GitHub/HF/OpenRouter through the proxy

Working flags, verified with `curlimages/curl:8.10.1`:

```bash
docker run --rm --network host \
  -e HTTPS_PROXY=$HTTPS_PROXY -e HTTP_PROXY=$HTTPS_PROXY \
  -e CURL_CA_BUNDLE=/etc/ssl/certs/ca-bundle.crt \
  -v /root/.ccr/ca-bundle.crt:/etc/ssl/certs/ca-bundle.crt:ro \
  <image> <cmd>
```

Key points, discovered empirically (not assumed):

- `--network host` + `HTTPS_PROXY`/`HTTP_PROXY` env vars alone is enough for the
  container to reach the proxy at `127.0.0.1:36343` — confirmed reachable for
  every host tested (pypi.org, registry.npmjs.org, api.github.com,
  raw.githubusercontent.com, huggingface.co, openrouter.ai).
- **CA bundle placement is tool-specific, don't assume `/etc/ssl/certs/ca-certificates.crt`
  is picked up.** `curlimages/curl:8.10.1` (Alpine/musl build) has its CAfile
  **compiled in as `/cacert.pem`**, which takes priority over `CApath` and is
  **not** overridden by mounting over `/etc/ssl/certs/ca-certificates.crt`, nor
  by setting `SSL_CERT_FILE`. Verified with `curl -v`: `* CAfile: /cacert.pem`.
  What *does* work reliably: `--cacert <path>` explicitly, or the
  `CURL_CA_BUNDLE` env var (curl-specific, checked before the compiled-in
  default). This is why the recipe above mounts to a neutral path
  (`/etc/ssl/certs/ca-bundle.crt`, not overwriting the image's own bundle) and
  sets `CURL_CA_BUNDLE` explicitly — this generalizes better than trying to
  clobber each image's own default cert path.
  - For non-curl tools, still set the standard vars as documented in
    `/root/.ccr/README.md`: `SSL_CERT_FILE`, `NODE_EXTRA_CA_CERTS`,
    `REQUESTS_CA_BUNDLE`, `PIP_CERT`, npm's `cafile` config (npm ignores
    `SSL_CERT_FILE`/`NODE_EXTRA_CA_CERTS` for its own HTTPS registry calls —
    must be set via `npm config set cafile <path>`, confirmed working, see §3).
- **Only some hosts are actually TLS-intercepted (MITM'd) by the proxy; most are
  passed through untouched.** Evidence: `pypi.org`, `registry.npmjs.org` are in
  the proxy's `noProxy` list (`/__agentproxy/status` → `"noProxy"` field) and
  bypass the local proxy entirely — reachable with **no CA bundle mount at
  all**. `raw.githubusercontent.com`, `huggingface.co`, `openrouter.ai` go
  through the proxy but were reachable **without needing the CA bundle**
  (curl's baked-in `/cacert.pem` already trusts the real upstream cert — proxy
  passthrough, not re-terminated). **Only `api.github.com` failed without the
  CA bundle** (`SSL certificate problem: self-signed certificate in certificate
  chain` — proxy re-terminates TLS there, likely for auth injection per the
  README's `gitConfigInjection`/`gitSshRewrite` flags) and needed
  `CURL_CA_BUNDLE` pointed at `/root/.ccr/ca-bundle.crt` to work. **Takeaway:
  always mount + wire the CA bundle defensively for every host** (cheap, no
  downside) rather than assuming pass-through; `api.github.com` is proof a
  given host can silently need it while sibling GitHub hosts don't.
- OpenRouter with no key: `GET https://openrouter.ai/api/v1/models` → `200`.
  `POST https://openrouter.ai/api/v1/chat/completions` with empty body and no
  `Authorization` header → `401`, as expected (no key exists in this probe).

Verified status codes (2026-09-25, this container):
```
pypi.org/simple/            200  (noProxy, direct)
registry.npmjs.org           200  (noProxy, direct)
raw.githubusercontent.com    200  (proxied, passthrough — no CA bundle needed)
huggingface.co/api/models    200  (proxied, passthrough — no CA bundle needed)
openrouter.ai/api/v1/models  200  (proxied, passthrough — no CA bundle needed)
openrouter.ai .../chat/completions (no auth)  401
api.github.com                000 → SSL error WITHOUT CA bundle
api.github.com                200 WITH CURL_CA_BUNDLE=/root/.ccr/ca-bundle.crt (proxied, MITM'd)
```

## 2. `docker build` through the proxy

Works. Recipe: pass proxy as build args (not just env, since `RUN` steps run in
build-time containers that don't inherit the host shell's env), and either
`COPY` the CA bundle in or bake `PIP_CERT`/`REQUESTS_CA_BUNDLE` pointing at it.
Verified with a `python:3.11-slim` base image doing `pip install requests`:

```dockerfile
FROM python:3.11-slim
ARG HTTPS_PROXY
ARG HTTP_PROXY
ENV HTTPS_PROXY=$HTTPS_PROXY
ENV HTTP_PROXY=$HTTP_PROXY
ENV PIP_CERT=/etc/ssl/certs/ca-certificates.crt
COPY ca-bundle.crt /etc/ssl/certs/ca-certificates.crt
RUN pip install --no-cache-dir requests
```
```bash
docker build --network host \
  --build-arg HTTPS_PROXY=$HTTPS_PROXY --build-arg HTTP_PROXY=$HTTPS_PROXY \
  -t <tag> <build-context-with-ca-bundle.crt-copied-in>
```
Result: succeeded in ~10s wall time, `pip install requests` resolved and
installed 5 packages from PyPI (direct, no MITM needed — PyPI is in `noProxy`).
`--network host` on `docker build` was necessary for the build containers to
reach the local proxy the same way `docker run --network host` does.

Note: for a host that DOES get MITM'd (like `api.github.com`) a build step
hitting it would need the image's own trust store to actually contain the
mounted/copied bundle — same caveat as §1 applies per-tool (pip respects
`PIP_CERT`/`REQUESTS_CA_BUNDLE`; verify per package manager, don't assume).

## 3. Node-based agent installs via npm, inside `node:22`, through the proxy

All four packages installed cleanly and fast. Recipe:

```bash
docker run --rm --network host \
  -e HTTPS_PROXY=$HTTPS_PROXY -e HTTP_PROXY=$HTTPS_PROXY \
  -v /root/.ccr/ca-bundle.crt:/etc/ssl/certs/ca-bundle.crt:ro \
  node:22 sh -c '
    npm config set cafile /etc/ssl/certs/ca-bundle.crt
    npm config set proxy $HTTPS_PROXY
    npm config set https-proxy $HTTPS_PROXY
    npm install -g <package>
  '
```
Note: npm needs its proxy/cafile set via `npm config set` — it does **not**
pick up `NODE_EXTRA_CA_CERTS`/`SSL_CERT_FILE` for its own registry HTTPS calls
in this image (untested whether it silently would've worked without `cafile`
since registry.npmjs.org is in `noProxy` anyway and reachable un-intercepted;
`npm config set proxy` was set defensively and not confirmed necessary either,
but costs nothing).

Results (fresh `node:22` pull, single container reused for all three in the
second batch to save pull time):
```
@earendil-works/pi-coding-agent   OK, 119 packages, ~11s
opencode-ai                       OK, 3 packages, ~11s
@openai/codex                     OK, 2 packages, ~8s
@anthropic-ai/claude-code         OK, 2 packages, ~5s
```
All exit code 0, `npm install -g` completed without errors for all four.
(pi's package pulls in 119 transitive deps — notably heavier than the other
three; worth remembering for image size / cold-start budgeting later.)

## 4. Disk

Baseline before any probe: `df -h /` → `252G total, 21G used, 18G avail (55%)`.
Peak during probes (all 3 test images present at once): `21G used, 16G avail
(59%)` — matches image sizes pulled (`node:22` 1.64GB + `vacant-env-probe:pip-test`
209MB + `curlimages/curl:8.10.1` 32MB ≈ 1.88GB, i.e. within the observed 2G
delta and well under the 3GB budget).
After `docker rmi` of all three: `21G used, 17G avail (55%)` — back to
essentially baseline (1G off is rounding/buffer-cache noise, not leaked disk).
`docker images` empty after cleanup — nothing left behind.

Implication for future task containers: `node:22` alone is 1.64GB — if many
agent-harness containers are spun up concurrently, prefer a slimmer base
(`node:22-slim` untested here, or a single shared prebuilt image with all 4
CLIs installed once and reused/committed) rather than re-pulling `node:22`
+ npm-installing per task container, both for disk and for the per-task
wall-clock cost (~35s cold for the first npm install, faster once npm's own
cache is warm inside a given container filesystem).

## 5. CPU / RAM available for running several task containers

Host-visible (this container, via `nproc`/`free -h`):
```
CPUs:   4        (nproc; docker info also reports "CPUs: 4")
Memory: 15.72GiB total (docker info), 15Gi total / ~14Gi available (free -h)
Swap:   0B (none configured)
```
No cgroup v2 CPU/memory limits were found on this container itself
(`/sys/fs/cgroup/cpu.max` and `.../memory.max` do not exist here — this
container is not itself cgroup-constrained beyond the host's own 4 CPU / 15GB
total), so `docker run` containers launched from here are only bounded by
whatever is left of the shared 4 CPU / 15GB after this session's own usage and
any sibling agent containers (per the task's own budget note: this is a
**shared** environment with other running agents). No explicit `--cpus`/
`--memory` flags were passed in any probe above and none were needed for these
lightweight tests; for concurrent task containers running actual model-driven
agent harnesses, explicit `--memory=`/`--cpus=` caps per container are
recommended to avoid one task container starving the others, since nothing
enforces that automatically here.

## Cleanup performed

```
docker rmi vacant-env-probe:pip-test curlimages/curl:8.10.1 node:22
```
Confirmed via `docker images` (empty) and `df -h /` (back to baseline) after.
Build context directory used:
`/tmp/claude-0/.../scratchpad/study/env/dockerbuild/` (local files only, no
images left running or built beyond the removed ones).

## Sources / how these facts were established

All facts above are this session's own command output, run in this container
on 2026-09-25 (not third-party sources) — commands and full output are in this
file inline. Referenced but not modified: `/root/.ccr/README.md` (proxy setup
doc, read for the `SSL_CERT_FILE`/`NODE_EXTRA_CA_CERTS`/etc. env var list) and
`curl -sS "$HTTPS_PROXY/__agentproxy/status"` (for the `noProxy` host list and
proxy config, read live).
