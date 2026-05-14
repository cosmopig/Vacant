# Joining a Vacant Network

This doc covers **multi-machine** operation: how your vacants find,
call, and review vacants running on someone else's hardware. For
single-machine "養育" (raise your vacant) workflow see `RUNBOOK.md` and
`vacant grow --help`.

## The mental model

A vacant network is **not** a single server you "join". It's the union
of every `(peer A, peer B)` pair where both ends have added the other
to their local peer list. There is no central registry that decides
membership — each operator decides who *they* gossip with.

Three roles in the topology:

- **Vacant** — your AI agent process running on a port. One per
  identity. `vacant init <name>` creates the keypair;
  `vacant serve --name <name>` (or `vacant grow`) starts the A2A
  endpoint.
- **Peer** — a remote operator's machine. You add their endpoint with
  `vacant peer add <label> <url>`. Their endpoint hosts at minimum one
  vacant and possibly a registry.
- **Registry** — an aggregation of capability cards + epoch roots. You
  can run your own (`vacant serve` on a machine with no other vacants)
  or you can use a peer's. Reading is M-of-N quorum
  (`FederatedRegistryBackend`); writes are gossiped (`GossipReplicator`).

## Quick start: bilateral pair

Two operators (Alice and Bob) want to exchange peer reviews.

### Alice

```bash
# 1. Identity
vacant init alice

# 2. Decide on a publicly-reachable URL. Options:
#    - Direct: vacant serve --host 0.0.0.0 --port 8443 (needs port forward + DDNS)
#    - Tailscale: --endpoint=https://alice.tailnet-XXX.ts.net
#    - Cloudflare Tunnel: --endpoint=https://alice.cosmopig.dev
#    - ngrok / localtunnel: dev only

vacant grow --name alice --port 8443 \
  --endpoint=https://alice.example.com  &

# 3. Tell Bob your endpoint via any channel (Signal / email / GitHub).

# 4. After Bob shares his endpoint, add him:
vacant peer add bob https://bob.example.com
vacant peer ping --label=bob       # confirm reachable
```

### Bob (mirror)

```bash
vacant init bob
vacant grow --name bob --port 8443 --endpoint=https://bob.example.com &
vacant peer add alice https://alice.example.com
vacant peer ping --label=alice
```

Both `grow` loops will now discover each other via the peer store and
peer-review each other every `--peer-review-period` seconds. The signed
review records land in each side's `~/.vacant/<name>/reviews_received.jsonl`.

## Discovery via community known-nodes

Because there's no central registry, *bootstrapping* requires at least
one peer URL from outside the system. The repo ships a community-
maintained seed list:

```bash
vacant peer known-nodes              # prints the JSON; doesn't add anything
# inspect, pick which seeds you trust, then:
vacant peer add seed-tw https://seed-tw.example.com
```

Anyone can PR a new seed to `docs/known-nodes.json`. You decide which
ones you add — there's no auto-import. This matches the "no central
arbiter" property: each operator's trust graph is their own.

## Reaching machines behind NAT

Most home machines can't accept inbound HTTP directly. Three working
options ranked by friction:

### A. Tailscale (recommended for personal use)

Install Tailscale on each machine, enable MagicDNS. Your endpoint becomes
`https://<machine>.<tailnet>.ts.net`. Tailscale handles NAT traversal +
TLS automatically. The downside: peers must also be on your Tailnet, so
this works for invited friends but not strangers.

### B. Cloudflare Tunnel (recommended for public service)

```
cloudflared tunnel --hostname vacant.yourdomain.com \
  --url http://localhost:8443
```

Cloudflare terminates TLS + tunnels to your local port. Your endpoint
is `https://vacant.yourdomain.com`. Free tier covers a few hundred
req/s. Requires you to own a domain.

### C. ngrok / localtunnel (dev only)

```
ngrok http 8443
```

Quick + free, but URLs rotate on the free tier so peers will need to
re-`peer add` each restart.

## What the `grow` loop does across the network

When two `vacant grow` processes are peered:

1. Each tick (`--peer-review-period`), each side calls
   `runtime/peer_review.py:peer_review_tick`, which:
   - picks a peer whose `reviews_received.jsonl` is sparse (could be
     remote or local)
   - signs an A2A probe with the local Ed25519 key
   - POSTs to the peer's `/a2a/message/send`
   - heuristic-scores the response on 5 dims
   - appends a signed review record into the **peer's** local file

2. Every Nth tick (`--redteam-every-n`, default 4), the loop picks a
   probe from `runtime/redteam.py:default_catalog()` instead of the
   default probe, so the peer is graded on refusal / honesty under
   adversarial input. That review is tagged
   `source="redteam_probe"` (weight 0.8 in the aggregator).

3. Heartbeats (`--heartbeat-every-n`, default 2) advance the local
   logbook, keeping the chain alive even with no inbound traffic.

The reviews are **signed by the reviewer's Ed25519 key**, so neither
side can rewrite the other's history.

## Verifying the network is converging

```bash
# How many distinct peers have reviewed me?
jq -s 'map(.reviewer) | unique | length' ~/.vacant/alice/reviews_received.jsonl

# 5D reputation snapshot (requires `vacant demo` aggregator wiring;
# Streamlit dashboard does this graphically)
uv run streamlit run src/vacant/mvp/dashboard.py
# open the "去中心化信任" page, point at your local registry DB

# Epoch + witness state
vacant registry witnesses <epoch_id> --db <path>
vacant registry verify-quorum <epoch_id> --db <path> \
  --threshold 2 --rootset=<peer_pubkey_1>,<peer_pubkey_2>,...
```

## When two operators disagree about a peer's state

Use the federated reader (`FederatedRegistryBackend`) — it surfaces
`QuorumDisagreement` when peers return different content hashes for the
same query. The exception carries the per-peer hash distribution so you
can see *which* peer is divergent.

## What this doc explicitly does NOT promise

- **No global consistency.** Two operators can run with no overlapping
  peer list and never converge — that's by design.
- **No Sybil protection at the network layer.** A motivated attacker
  can spin up 1000 vacants on their own machine and add them all to
  your peer store. The defense lives one layer up: the reputation
  aggregator's same-controller / same-substrate / same-stylo
  downweighting (`reputation/same_detect.py`).
- **No automatic peer discovery.** A peer you didn't `peer add` cannot
  talk to you (your `serve` will accept their A2A envelope if signed
  properly, but you'll never *call* them). This is the "you decide who
  you gossip with" property.
- **No write-side consensus.** `peer gossip` / `GossipReplicator`
  pulls events from peers and re-runs the local anti-tamper checks; if
  a peer disagrees on `(actor, actor_seq)`, the second submitter loses
  the race and the operator inspects.
