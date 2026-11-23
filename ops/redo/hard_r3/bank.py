"""定義原創題庫與可見／隱藏測資，承接 PROTOCOL.md 的 Tasks 與 Outcome。"""
from collections import Counter, defaultdict
from fractions import Fraction
import heapq
from itertools import combinations
import random

import extra_bank


def mesh(data):
    events = data["events"]
    edges = Counter()
    out = []
    for op, a, *rest in events:
        if op in ("add", "remove"):
            e = tuple(sorted((a, rest[0])))
            edges[e] = max(0, edges[e] + (1 if op == "add" else -1))
            continue
        adj = defaultdict(list)
        for (u, v), count in edges.items():
            if count:
                adj[u].append(v)
                adj[v].append(u)
        seen = {a}
        todo = [a]
        while todo:
            for v in adj[todo.pop()]:
                if v not in seen:
                    seen.add(v)
                    todo.append(v)
        out.append(len(seen) if op == "size" else rest[0] in seen)
    return out


def cache(data):
    entries = {}  # key -> (size, expiry, pinned, last_successful_access_index)
    result = []
    for i, (t, op, key, *args) in enumerate(data["events"]):
        entries = {k: e for k, e in entries.items() if e[1] > t}
        if op == "get":
            if key not in entries:
                result.append(None)
            else:
                size, expiry, pinned, _ = entries[key]
                entries[key] = size, expiry, pinned, i
                result.append(size)
        elif op == "pin":
            if key in entries:
                size, expiry, _, last = entries[key]
                entries[key] = size, expiry, args[0], last
            result.append(key in entries)
        else:
            size, ttl, pinned = args
            trial = {k: e for k, e in entries.items() if k != key}
            victims = sorted((e[3], k) for k, e in trial.items() if not e[2])
            for _, k in victims:
                if size + sum(e[0] for e in trial.values()) <= data["capacity"]:
                    break
                del trial[k]
            ok = size + sum(e[0] for e in trial.values()) <= data["capacity"]
            if ok:
                entries = {**trial, key: (size, t + ttl, pinned, i)}
            result.append(ok)
    return result


def intervals(data):
    jobs = sorted(data["jobs"], key=lambda j: (j[1], j[2], j[0]))
    best = (0, ())
    for n in range(1, min(data["max_jobs"], len(jobs)) + 1):
        for subset in combinations(jobs, n):
            if any(a[2] + data["gap"] > b[1] for a, b in zip(subset, subset[1:])):
                continue
            candidate = (-sum(j[3] for j in subset), tuple(j[0] for j in subset))
            best = min(best, candidate)
    return [-best[0], list(best[1])]


def route(data):
    start, end = data["source"], data["target"]
    adjacent = defaultdict(list)
    for edge_id, u, v, charge, time in data["edges"]:
        adjacent[u].append((edge_id, v, charge, time))
    heap = [(0, 0, (), start, False)]
    seen = set()
    while heap:
        time, charge, path, u, used = heapq.heappop(heap)
        state = (u, charge, used)
        if state in seen:
            continue
        seen.add(state)
        if u == end:
            return [time, charge, list(path)]
        for edge_id, v, c, t in adjacent[u]:
            for use in (False, True) if not used else (False,):
                cost = charge + (c // 2 if use else c)
                if cost <= data["budget"]:
                    heapq.heappush(heap, (time + t, cost, path + (edge_id,), v, used or use))
    return None


def spans(data):
    spans = {s[0]: s[1:] for s in data}
    records = []
    errors = set()
    for sid, (parent, begin, end, service) in spans.items():
        if end <= begin:
            errors.add(sid)
            continue
        if parent is not None:
            p = spans.get(parent)
            if p is None or p[1] > begin or p[2] < end or (p[1], p[2], parent) == (begin, end, sid):
                errors.add(sid)
        records.append((sid, parent, begin, end, service))
    for sid in spans:
        seen = []
        while sid in spans and sid not in seen:
            seen.append(sid)
            sid = spans[sid][0]
        if sid in seen:
            errors.update(seen[seen.index(sid):])
    if errors:
        return {"invalid": sorted(errors)}
    out = defaultdict(int)
    for sid, _, begin, end, service in records:
        out[service] += sum(not any(p == sid and b <= i < e for _, p, b, e, _ in records)
                            for i in range(begin, end))
    return dict(out)


def patch(data):
    hunks = data["edits"]
    conflicts = set()
    for (a, l1, r1, _), (b, l2, r2, _) in combinations(hunks, 2):
        overlap = (max(l1, l2) < min(r1, r2)
                   or l1 == r1 and l2 < l1 < r2
                   or l2 == r2 and l1 < l2 < r1)
        if overlap and a != b:
            conflicts.update((a, b))
    pos = 0
    parts = []
    for _, left, right, text in sorted((e for e in hunks if e[0] not in conflicts),
                                       key=lambda h: (h[1], h[1] != h[2], h[0])):
        parts.extend((data["base"][pos:left], text))
        pos = right
    parts.append(data["base"][pos:])
    return {"text": "".join(parts), "rejected": sorted(conflicts)}


def rank(data):
    live = {}
    out = []
    for op, *args in data:
        if op == "set":
            live[args[0]] = args[1]
        elif op == "del":
            live.pop(args[0], None)
        else:
            lo, hi, k = args
            xs = sorted(v for v in live.values() if lo <= v <= hi)
            midpoint = len(xs) // 2
            median = (None if not xs else Fraction(xs[midpoint] if len(xs) % 2
                                                  else xs[midpoint - 1] + xs[midpoint],
                                                  1 if len(xs) % 2 else 2))
            out.append([len(xs), sum(xs), xs[k - 1] if 0 < k <= len(xs) else None,
                        str(median) if median is not None else None])
    return out


def reconcile(data):
    enabled = set(data["start"])
    steps = {k: 0 for k in enabled}
    round_number = 1
    while True:
        added = {output for output, threshold, inputs in data["rules"]
                 if len(enabled.intersection(inputs)) >= threshold} - enabled
        if not added:
            return steps
        steps.update(dict.fromkeys(added, round_number))
        enabled |= added
        round_number += 1


SPECS = {
    "mesh": """A field team records an undirected multigraph on vertices 0..n-1.
Input {"n": n, "events": [...]} in order. ["add",u,v] adds one undirected edge
copy. ["remove",u,v] removes one copy if present, otherwise does nothing.
Self-loops are legal. Emit an answer only for ["connected",u,v] (boolean,
including u==v) or ["size",u] (count of vertices currently in u's component).
Return the answers in event order. n <= 20000, events <= 80000. The grader
includes a long dense connected chain with interleaved deletes and queries;
per-query graph traversal can exceed the 4 s case limit.""",
    "cache": """Implement a weighted LRU cache with pinning and TTL. Input
{"capacity": C, "events": [...]} in nondecreasing integer time, input order
breaks same-time ties. Each [time, op, key, ...] first expires everything
with expires_at <= time, including pinned entries. A "get" returns stored size
or null, and promotes a hit. A "pin" has a boolean argument, updates a live
entry's pinned flag without promoting it, and returns whether it exists.
A "put" has args [positive_size, positive_ttl, pinned_bool]. Replace the old
key (even if pinned), promote it, and expire it at time+ttl. To make room,
evict other unpinned entries from oldest successful get/put to newest. Return
true on success. If the put cannot fit even after all possible evictions,
return false and make NO changes apart from expiration, including no
promotion. Return one result per event.""",
    "intervals": """Input {"gap": g, "max_jobs": k, "jobs": [[id,start,end,value],...]}.
Select up to k jobs. Each has a unique ASCII string id and start < end.
In chronological order every previous end + g must be <= next start.
Maximize the sum of values (possibly negative), then minimize the sequence
of ids in chronological order using standard lexicographic comparison, where
a proper prefix is smaller. Return [value, [ids...]], including empty if
optimal. g >= 0, up to 8000 jobs and k<=24; exhaustive subset enumeration
will exceed the case limit.""",
    "route": """Plan a trip on a directed graph. Input {"source":s,"target":t,
"budget":B,"edges":[[id,from,to,charge,minutes],...]}. ids are unique ASCII
strings; vertices are nonnegative ints; charges nonnegative ints; minutes
strictly positive ints. The same edge may be traveled multiple times.
At most once on the trip you may apply a coupon to one traversal, changing
its charge to floor(charge/2) without affecting minutes. Total charge must
be <= B. Choose the path minimizing (total minutes, total actual charge,
sequence of IDs in traversal order) lexicographically. Return [minutes,
actual charge, [edge_ids...]], or null if impossible. The zero-length trip
at the source is allowed. Up to 150 vertices, 2500 edges, budget <= 400.""",
    "spans": """Compute exclusive service time from trace spans. Input is a list
of [id,parent_id_or_null,start,end,service], unique ASCII identifiers,
integer times, spans half-open. Span order carries no meaning. Invalid
IDs are exactly: spans with end<=start; spans whose non-null parent is
missing or whose [start,end) is not contained within its parent's interval
(equal intervals allowed); every member of a parent-pointer cycle, including
a self-loop. Do not propagate invalidity down the tree for this check.
Return {"invalid":[sorted unique IDs]} if any are invalid. Otherwise return
a mapping from each service to total exclusive time, including zero-valued
services: each span's duration minus the union length of its DIRECT
children's intervals. Overlapping sibling durations are not double-subtracted.
Parents need not start earlier. Up to 15000 spans, times up to 10^12;
do not iterate each temporal unit.""",
    "patch": """Merge transactions of proposed edits to a text. Input
{"base":text,"edits":[[transaction_id,start,end,replacement],...]}.
Offsets are Python Unicode code point offsets in the ORIGINAL text,
0 <= start <= end <= len(base). A transaction's own intervals do not
conflict, and it makes at most one insertion at each offset. Two edits
from distinct transactions conflict if two nonempty half-open spans
intersect, or an insertion lies STRICTLY inside the other's nonempty span.
At boundaries, insertions and replacements coexist. Two insertions never
conflict. If any edit conflicts, reject BOTH whole transactions; determine all
conflicts on original edits before filtering. Apply remaining edits in
original-position order, insertions before a replacement at the same offset,
and multiple insertions at the same offset sorted by transaction id.
Return {"text": resulting_string,"rejected":[sorted transaction IDs]}.""",
    "rank": """Maintain live reservations as a mapping from unique string
ID to integer value. Input events ["set",id,v] (overwrites), ["del",id]
(no-op if missing), ["ask",low,high,k]. Each ask uses all currently live
values in the inclusive range low..high, duplicates counted. A reversed
range is empty. Answer [count,sum,kth_or_null,median_or_null]; kth is
1-indexed ascending, null if k out of range. Return the median as a
reduced rational string, e.g. "-3/2" or "4", not a float. Return the list
of answers in order. Up to 60000 events, values can be large signed ints;
grading includes a heavy update/range workload.""",
    "reconcile": """A build system enables features in synchronous rounds.
Input {"start":[...],"rules":[[output,threshold,[input features]],...]}.
Started features have round 0. In round r>=1 a feature becomes enabled if
at least one rule for it has at least 'threshold' DISTINCT inputs enabled
at the beginning of the round. Threshold >=0, repeated inputs count once.
Rules may be repeated, thresholds can exceed input count, and cycles do
not self-start. Each feature stays enabled and its earliest round is final.
Return a mapping of enabled feature names to their earliest round, omitting
unreachable features. Up to 35000 rules and 100000 input occurrences;
the case limit covers a long chain.""",
}

SMALL = {
    "mesh": {"n": 4, "events": [["add", 0, 1], ["add", 1, 0], ["remove", 0, 1],
                                ["connected", 0, 1], ["size", 0], ["remove", 1, 0],
                                ["connected", 0, 1]]},
    "cache": {"capacity": 4, "events": [[0, "put", "a", 2, 4, False], [1, "put", "b", 2, 5, True],
                                       [2, "put", "c", 3, 4, False], [2, "get", "a"],
                                       [4, "get", "a"], [4, "put", "c", 2, 2, False]]},
    "intervals": {"gap": 1, "max_jobs": 2, "jobs": [["b", 0, 2, 5], ["x", 3, 5, 4],
                                                    ["a", 0, 2, 5], ["q", 2, 4, 5]]},
    "route": {"source": 0, "target": 2, "budget": 5,
              "edges": [["a", 0, 1, 5, 2], ["b", 1, 2, 2, 3], ["c", 0, 2, 9, 7]]},
    "spans": [["p", None, 0, 10, "a"], ["b", "p", 2, 6, "b"], ["c", "p", 4, 7, "b"]],
    "patch": {"base": "axßd", "edits": [["t1", 1, 3, "Q"], ["t2", 1, 1, "ö"],
                                        ["t3", 3, 3, "!"], ["t4", 1, 1, "X"]]},
    "rank": [["set", "x", -3], ["set", "y", 0], ["ask", -4, 4, 2], ["del", "x"],
             ["ask", -5, 5, 2], ["ask", 9, 2, 0]],
    "reconcile": {"start": ["a"], "rules": [["b", 1, ["a"]], ["c", 2, ["b", "b"]],
                                          ["d", 2, ["b", "a"]], ["e", 1, ["e"]]]},
}

ORACLES = dict(zip(SPECS, (mesh, cache, intervals, route, spans, patch, rank, reconcile), strict=True))
SPECS.update(extra_bank.SPECS)


def random_input(task, r, visible=False):
    ri = r.randint
    if task == "mesh":
        return {"n": 7, "events": [[op, ri(0, 6)] + ([] if op == "size" else [ri(0, 6)])
                                  for op in (r.choice(["add", "add", "remove", "connected", "size"])
                                             for _ in range(20 if visible else 160))]}
    if task == "cache":
        time = 0
        events = []
        for _ in range(12 if visible else 100):
            time += ri(0, 1)
            op, key = r.choice(["put", "put", "pin", "get"]), str(ri(0, 8))
            args = {"put": [ri(1, 9), ri(1, 10), bool(ri(0, 1))], "pin": [bool(ri(0, 1))], "get": []}
            events.append([time, op, key, *args[op]])
        return {"capacity": ri(0, 20), "events": events}
    if task == "intervals":
        return {"gap": ri(0, 3), "max_jobs": ri(0, 5),
                "jobs": [[f"{i:02d}", s, s + ri(1, 6), ri(-3, 6)]
                         for i, s in enumerate(ri(-5, 15) for _ in range(6 if visible else 13))]}
    if task == "route":
        return {"source": ri(0, 5), "target": ri(0, 5), "budget": ri(0, 15),
                "edges": [[f"{i:02d}", ri(0, 5), ri(0, 5), ri(0, 8), ri(1, 6)]
                          for i in range(12 if visible else 30)]}
    if task == "spans":
        records = [["root", None, 0, 24, "a"]]
        for i in range(6 if visible else 12):
            pid, _, lo, hi, _ = r.choice(records)
            lo = ri(lo, hi - 1)
            hi = ri(lo + 1, hi)
            records.append([str(i), pid, lo, hi, r.choice("abc")])
        r.shuffle(records)
        if ri(0, 1):
            node = r.choice(records)
            node[1] = r.choice(records)[0]
        return records
    if task == "patch":
        return {"base": "甲aé😀xyz尾巴", "edits": [[str(i), a, ri(a, min(a + 3, 9)), str(i)]
                          for i, a in enumerate(ri(0, 9) for _ in range(5))]}
    if task == "rank":
        out = []
        for _ in range(12 if visible else 150):
            op = r.choice(["set", "set", "del", "ask"])
            ident = str(ri(0, 20))
            out.append({"set": [op, ident, ri(-9, 9)], "del": [op, ident],
                        "ask": [op, ri(-10, 10), ri(-10, 10), ri(-1, 25)]}[op])
        return out
    return {"start": ["0", "9"], "rules": [[str(ri(0, 12)), ri(0, 5),
            [str(ri(0, 12)) for _ in range(ri(0, 9))]] for _ in range(6 if visible else 22)]}


def stress(task):
    if task == "mesh":
        n = 14000
        events = [["add", i, i+1] for i in range(n-1)]
        out = []
        for i in range(1, n - 1):
            events += [["remove", i - 1, i], ["size", n-1], ["connected", 0, n-1], ["add", i, i-1]]
            out += [n-i, False]
        return {"n": n, "events": events}, out
    if task == "intervals":
        n = 7800
        jobs = [[str(i).zfill(4), i*2, i*2+1, 1] for i in range(n)]
        return {"gap": 1, "max_jobs": 24, "jobs": jobs[::-1]}, [24, [j[0] for j in jobs[:24]]]
    if task == "spans":
        big = 10**12
        return [["r", None, 0, big, "outer"], ["a", "r", 2, big-1, "inner"],
                ["b", "r", big-2, big, "inner"]], {"outer": 2, "inner": big-1}
    if task == "rank":
        n = 28000
        seq = [["set", str(i), i] for i in range(n)]
        seq += [["ask", 0, i, 1] for i in reversed(range(n))]
        return seq, [[i+1, i*(i+1)//2, 0, str(Fraction(i, 2))] for i in reversed(range(n))]
    if task == "reconcile":
        n = 26000
        return {"start": ["0"], "rules": [[str(i), 1, [str(i-1)]] for i in range(1, n)]}, {
            str(i): i for i in range(n)}
    return None


EXTRA = {
    "cache": [{"capacity": 5, "events": [[0,"put","a",2,4,False],[0,"put","b",3,10,True],
                  [1,"put","a",4,3,False],[1,"get","a"],[2,"pin","b",False],[2,"put","c",4,8,False],
                  [2,"get","a"],[2,"get","b"],[10,"get","c"]]}],
    "spans": [[["a","b",0,4,"x"],["b","a",0,4,"x"],["c","a",1,2,"y"],
                ["d","missing",0,8,"z"],["e",None,2,2,"z"]]],
    "patch": [{"base":"甲bcdefghij","edits":[["a",0,3,"A"],["a",8,9,"X"],["b",2,5,"B"],
               ["b",7,7,"!"],["c",7,10,"C"],["d",5,7,"D"],["e",5,5,"+"],["f",7,7,"-"]]}],
}


def suite(task, hidden):
    if task in ORACLES:
        oracle, small, extra, gen_case, large_case = ORACLES[task], SMALL, EXTRA, random_input, stress
    else:
        oracle = extra_bank.ORACLES[task]
        small, extra = extra_bank.SMALL, extra_bank.EXTRA
        gen_case, large_case = extra_bank.random_input, extra_bank.stress
    if not hidden:
        r = random.Random(f"r3-hard-visible-v1:{task}")
        examples = [small[task], *(gen_case(task, r, visible=True) for _ in range(3))]
        return [(case, oracle(case)) for case in examples]
    r = random.Random(f"r3-hard-v1:{task}")
    cases = extra.get(task, []) + [gen_case(task, r, visible=False) for _ in range(24)]
    out = [(case, oracle(case)) for case in cases]
    large = large_case(task)
    if large:
        out.append(large)
    return out
