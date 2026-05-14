# Deploying a vacant to the public internet

By default `vacant serve` binds `127.0.0.1` — only processes on the
same machine can reach it. This doc covers the deliberate, opt-in
paths to expose a vacant *outside* your machine.

> Read `JOIN_NETWORK.md` first if you only need two specific machines
> to talk. Public exposure is a strictly larger threat surface.

## Three deployment patterns

| Pattern | Auth at edge | Cert mgmt | Best for |
|---|---|---|---|
| **Direct `vacant serve --public --tls-cert ... --tls-key ...`** | Your operator firewall | You issue / renew | Tailscale-internal hostnames where Tailscale auto-issues |
| **Caddy reverse proxy (recommended)** | Caddy | Auto via Let's Encrypt | Public domain you own |
| **Cloudflare Tunnel** | Cloudflare edge | Auto via Cloudflare | Free tier, no port forward, hides your IP |

All three keep the **vacant identity** (Ed25519 keypair) inside the
vacant process — the TLS cert is for transport secrecy only; it does
NOT replace the per-vacant signature on A2A envelopes.

---

## Pattern A — Direct `--tls`

```bash
vacant init alice
vacant serve --name alice --public \
  --port 8443 \
  --tls-cert /etc/vacant/alice.pem \
  --tls-key  /etc/vacant/alice.key \
  --endpoint https://alice.example.com
```

`--public` flips bind to `0.0.0.0`. `--tls-cert/--tls-key` activates
uvicorn HTTPS. The `--endpoint` URL is what callers see and what gets
signed into the capability card — make sure it matches the cert's CN /
SAN.

Renewal is your job. For ACME-renewed certs use Caddy (pattern B).

## Pattern B — Caddy reverse proxy (recommended)

Run vacant on plain HTTP behind Caddy. Caddy handles Let's Encrypt
auto-renewal and HTTP→HTTPS redirect.

### Caddyfile

```caddy
alice.example.com {
    reverse_proxy 127.0.0.1:8443
}
```

That's it — Caddy provisions a cert on first request.

### Vacant systemd unit (`/etc/systemd/system/vacant-alice.service`)

```ini
[Unit]
Description=vacant (alice)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=vacant
Environment="VACANT_HOME=/var/lib/vacant"
Environment="ANTHROPIC_API_KEY_FILE=/etc/vacant/anthropic.key"
ExecStart=/usr/local/bin/uv run vacant grow \
    --name alice \
    --host 127.0.0.1 --port 8443 \
    --endpoint https://alice.example.com
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable + start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now vacant-alice
```

> The vacant binds **127.0.0.1**, not 0.0.0.0 — Caddy is the only
> thing that can reach it, even from another process on the same box.

## Pattern C — Cloudflare Tunnel

No port forward, no public IP, no inbound firewall hole. Cloudflare
terminates TLS at the edge and tunnels to your machine.

```bash
# One-time setup
cloudflared tunnel login                              # opens browser
cloudflared tunnel create vacant-alice                # creates tunnel
cloudflared tunnel route dns vacant-alice alice.cosmopig.dev

# Run (long-lived; usually under systemd)
cloudflared tunnel --config /etc/cloudflared/config.yml run vacant-alice
```

`config.yml`:

```yaml
tunnel: vacant-alice
credentials-file: /etc/cloudflared/vacant-alice.json
ingress:
  - hostname: alice.cosmopig.dev
    service: http://localhost:8443
  - service: http_status:404
```

Then run vacant **without** `--public` — Cloudflare connects from
inside your machine:

```bash
vacant grow --name alice --port 8443 \
  --endpoint https://alice.cosmopig.dev
```

## Security hardening (any pattern)

These are **load-bearing** for public deployment, not optional:

1. **`VACANT_HOME` on encrypted disk + restrictive perms.** The
   signing key seed lives in the OS keyring by default; if you opted
   into `init --insecure-demo` (e.g. for a kiosk demo), the seed is on
   disk — make sure the parent dir is `chmod 700`.

2. **No `ANTHROPIC_API_KEY` etc. in process env if your vacant uses
   `client-inherited`.** That substrate uses the calling MCP client's
   model, so the vacant process doesn't need any API key.

3. **Rate limiting.** FastAPI doesn't ship with rate limits.
   Pattern B + Caddy: add the `caddy-rate-limit` plugin
   ([repo](https://github.com/mholt/caddy-ratelimit)). Pattern C:
   Cloudflare's free WAF rules cover most of this.

4. **Logs at INFO, not DEBUG, in production.** DEBUG can leak
   prompt content + envelope payloads.

5. **Public visibility ≠ owner.** Once your vacant is reachable, the
   protocol-level checks
   (`replay_protect`, `state_machine.can_be_called`, `visibility.NONE`)
   are what stop strangers from impersonating or replaying. The
   reverse proxy is *transport* only.

## Operator checklist before going public

- [ ] `vacant peer ping --label=self` from another machine returns 200
- [ ] Capability card endpoint matches the public URL
      (`curl https://your-url/card | jq .endpoint`)
- [ ] You've added at least one trusted peer for federation
      (`vacant peer add <label> <url>`)
- [ ] You've decided what visibility tier you want
      (`vacant publish` for PUBLIC, leave LOCAL for friends-only)
- [ ] You're monitoring `~/.vacant/<name>/reviews_received.jsonl` so
      bad reviews don't tank your reputation silently
- [ ] You've set up TLS renewal (Caddy + Cloudflare handle this; for
      `--tls-cert` direct you're on your own)

## When to NOT go public

- Your vacant is mid-development and you're iterating on the
  `behavior_bundle`. Keep it LOCAL until you're happy.
- Your vacant has no rate limit and you can't afford an LLM bill that
  could go to $infinity.
- Your vacant calls out to `client-inherited` substrate (i.e. uses
  whoever-calls-it's LLM). That's a serious abuse vector for strangers
  on the public internet; only expose to trusted peer set.
