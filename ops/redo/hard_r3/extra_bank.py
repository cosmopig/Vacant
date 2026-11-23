"""定義序列重跑的四道新題與獨立評分器，承接 SERIAL_PROTOCOL.md 的 Tasks。"""
from itertools import product


def settlement(data):
    edges = data["edges"]
    best = None
    for flows in product(*(range(lo, hi + 1) for _, _, lo, hi, _ in edges)):
        balance = [0] * len(data["supply"])
        cost = 0
        for (u, v, _, _, rate), amount in zip(edges, flows, strict=True):
            balance[u] += amount
            balance[v] -= amount
            cost += amount * rate
        if balance == data["supply"] and (best is None or cost < best):
            best = cost
    return best


def grammar(data):
    rules = data["rules"]

    def cost(word):
        table = {}
        for width in range(1, len(word) + 1):
            for i in range(len(word) - width + 1):
                j = i + width
                here = {}

                def offer(symbol, value):
                    if value is not None and (symbol not in here or value < here[symbol]):
                        here[symbol] = value
                        return True
                    return False

                for lhs, kind, rhs, price in rules:
                    if kind == "letter" and width == 1 and word[i] == rhs:
                        offer(lhs, price)
                    elif kind == "pair":
                        a, b = rhs
                        for k in range(i + 1, j):
                            left, right = table[i, k], table[k, j]
                            if a in left and b in right:
                                offer(lhs, left[a] + right[b] + price)
                while True:
                    changed = False
                    for lhs, kind, rhs, price in rules:
                        if kind == "unit" and rhs in here:
                            changed |= offer(lhs, here[rhs] + price)
                    if not changed:
                        break
                table[i, j] = here
        return table.get((0, len(word)), {}).get(data["start"])

    return [cost(word) for word in data["words"]]


def dispatcher(data):
    tasks = {key: [arrival, work, priority, 0] for key, arrival, work, priority in data["jobs"]}
    time = 0
    done = {}
    while tasks:
        ready = {key: task for key, task in tasks.items() if task[0] <= time}
        if not ready:
            time = min(task[0] for task in tasks.values())
            continue
        selected = min(ready, key=lambda k: (-(ready[k][2] + ready[k][3] // data["aging"]),
                                               ready[k][0], k))
        time += 1
        for key, task in ready.items():
            if key == selected:
                task[1] -= 1
                if task[1] == 0:
                    done[key] = time
                    del tasks[key]
            else:
                task[3] += 1
    return done


def terrain(data):
    grid, cap = data["grid"], data["cap"]
    height, width = len(grid), len(grid[0])
    points = {(i, j): v for i, row in enumerate(grid) for j, v in enumerate(row) if v is not None}
    outlets = {(i, j): v for i, j, v in data["outlets"]}
    depth = {point: max(0, cap - elevation) for point, elevation in points.items()}
    for level in sorted(v for v in set(points.values()) | set(outlets.values()) if v <= cap):
        allowed = {point for point, elevation in points.items() if elevation <= level}
        seeds = {point for point in allowed if outlets.get(point, cap + 1) <= level}
        found = set(seeds)
        while seeds:
            i, j = seeds.pop()
            p = i, j
            depth[p] = min(depth[p], level - points[p])
            for neighbor in ((i - 1, j), (i + 1, j), (i, j - 1), (i, j + 1)):
                if neighbor in allowed and neighbor not in found:
                    found.add(neighbor)
                    seeds.add(neighbor)
    return [[depth.get((i, j)) for j in range(width)] for i in range(height)]


SPECS = {
    "settlement": """A transfer system chooses an INTEGER flow on every directed edge.
Input {"supply":[signed integers for nodes 0..n-1],
"edges":[[from,to,lower,upper,cost_per_unit],...]}. Parallel edges and
self-loops are allowed. Bounds are nonnegative, lower<=upper. For each
node, sum outgoing flow minus sum incoming flow must equal its supply.
Return the minimum sum of flow * cost over ALL edges, or null if infeasible.
Costs can be negative. Flow around cycles is legal even when every supply
is zero. n<=100, m<=500, upper<=10000. The grader includes a case whose
edge-bound combinations are too numerous to enumerate.""",
    "grammar": """A weighted context-free grammar uses nonnegative integer rule
costs and no empty productions. Input {"start":symbol,
"rules":[[lhs,kind,rhs,cost],...],"words":[strings...]}. A "letter" rule
has one character as rhs; "unit" has one nonterminal symbol string;
"pair" has [left_symbol,right_symbol] in order. Duplicate rules and
zero-cost unit cycles are allowed. The cost of a finite derivation
tree is the sum of its rule costs, counting repeats. Return one
minimum cost per word in order, null when impossible (including "").
At most 32 nonterminals, 150 rules, 10 words, and word length <= 70.""",
    "dispatcher": """Simulate a preemptible single-worker scheduler in integer
ticks. Input {"aging":positive integer,"jobs":[[id,arrival,duration,priority],
...]}. IDs are unique ASCII strings, arrivals nonnegative, durations
positive, priorities signed. At the start of tick t all arriving jobs
join. Among arrived unfinished jobs choose highest priority plus
floor(total previous waiting ticks / aging), then earliest arrival,
then lexicographically smallest ID. Execute it for one tick and age
all other ready jobs by one waiting tick; the running job retains
its prior waiting ticks. A finish in tick t is reported at t+1.
Return a mapping from ID to completion time. Up to 600 jobs,
arrival and duration <= 10^9; the run may have a long single-job tail.""",
    "terrain": """Compute residual water depth on a rectangular grid. Input
{"grid":[[nonnegative elevations or null]],"cap":nonnegative maximum
level,"outlets":[[row,column,spill_level],...]}. Null cells are walls.
Only four-neighbor steps between non-wall cells are legal. Grid edges
are not outlets. Outlet cells are unique and non-wall, spill_level>=0.
For each non-wall cell, a path from it to an outlet (possibly zero
steps) has a threshold equal to the maximum of all elevations on
the path and the outlet's spill level. The cell's final level is
min(cap, the lowest such threshold), or cap if no path; its depth is
max(0, final level minus its elevation). Preserve walls as null.
Up to 140x140, elevations and levels up to 10^9.""",
}

ORACLES = {"settlement": settlement, "grammar": grammar, "dispatcher": dispatcher, "terrain": terrain}
SMALL = {
    "settlement": {"supply": [1, -1], "edges": [[0, 1, 1, 3, 2], [1, 0, 0, 2, -5]]},
    "grammar": {"start": "S", "words": ["ab", "a", "", "ba"],
                "rules": [["S", "pair", ["A", "B"], 1], ["A", "letter", "a", 2],
                          ["B", "letter", "b", 3], ["S", "unit", "A", 4], ["A", "unit", "A", 0]]},
    "dispatcher": {"aging": 2, "jobs": [["x", 0, 3, 0], ["y", 0, 2, 1], ["z", 1, 1, 1]]},
    "terrain": {"grid": [[0, 4, 0], [1, None, 2], [0, 1, 0]], "cap": 5, "outlets": [[0, 2, 2]]},
}
MANUAL = {
    "settlement": -4,
    "grammar": [6, 6, None, None],
    "dispatcher": {"y": 2, "z": 4, "x": 6},
    "terrain": [[2, 0, 2], [1, None, 0], [2, 1, 2]],
}
EXTRA = {
    "settlement": [{"supply": [0], "edges": [[0, 0, 1, 3, -2], [0, 0, 0, 1, 3]]}],
    "grammar": [{"start": "S", "words": ["a", "aa", "aaa"],
                 "rules": [["S", "unit", "A", 0], ["A", "unit", "S", 0],
                           ["A", "letter", "a", 2], ["A", "pair", ["A", "A"], 1]]}],
    "dispatcher": [{"aging": 1, "jobs": [["b", 2, 3, -1], ["a", 2, 3, -1], ["c", 3, 1, 1]]}],
    "terrain": [{"grid": [[0, None, 1], [1, None, 0]], "cap": 7, "outlets": [[0, 2, 3]]}],
}


def random_input(task, r, visible):
    if task == "settlement":
        n, m = (3, 5) if visible else (4, 7)
        supply, edges = [0] * n, []
        for _ in range(m):
            u, v, lo = r.randrange(n), r.randrange(n), r.randrange(3)
            hi = lo + r.randrange(3)
            edges.append([u, v, lo, hi, r.randint(-4, 4)])
            flow = r.randint(lo, hi)
            supply[u] += flow
            supply[v] -= flow
        if r.randrange(3) == 0:
            supply[0] += 1
            supply[-1] -= 1
        return {"supply": supply, "edges": edges}
    if task == "grammar":
        syms = "ABC"
        rules = [[symbol, "letter", letter, r.randrange(5)] for symbol, letter in zip(syms, "aba", strict=True)]
        for _ in range(8):
            kind = r.choice(["unit", "pair"])
            rhs = r.choice(syms) if kind == "unit" else r.choices(syms, k=2)
            rules.append([r.choice(syms), kind, rhs, r.randrange(6)])
        words = ["".join(r.choices("ab", k=r.randrange(7))) for _ in range(2 if visible else 5)]
        return {"start": "A", "words": words, "rules": rules}
    if task == "dispatcher":
        jobs = [[str(i), r.randrange(8), r.randint(1, 5), r.randint(-3, 3)]
                for i in range(5 if visible else 7)]
        r.shuffle(jobs)
        return {"aging": r.randint(1, 5), "jobs": jobs}
    h, w = (3, 4) if visible else (4, 5)
    grid = [[r.choice([None, 0, 1, 2, 3, 5]) for _ in range(w)] for _ in range(h)]
    cells = [(i, j) for i in range(h) for j in range(w) if grid[i][j] is not None]
    outlets = [[i, j, r.randrange(8)] for i, j in r.sample(cells, k=min(len(cells), r.randrange(5)))]
    return {"grid": grid, "cap": r.randrange(8), "outlets": outlets}


def stress(task):
    if task == "settlement":
        return {"supply": [0, 0], "edges": [[0, 1, 0, 10000, 1]] * 80
                + [[1, 0, 0, 10000, -3]] * 80}, -1600000
    if task == "grammar":
        return {"start": "S", "words": ["a" * 70, "a" * 69 + "b", "a" * 35],
                "rules": [["S", "unit", "A", 0], ["A", "unit", "S", 0],
                          ["A", "letter", "a", 2], ["A", "pair", ["S", "S"], 1]]}, [209, None, 104]
    if task == "dispatcher":
        return {"aging": 29, "jobs": [["long", 0, 10**9, 0], ["short", 10**9 - 1, 1, 1]]}, {
            "short": 10**9, "long": 10**9 + 1,
        }
    if task == "terrain":
        n = 120
        return {"grid": [[0] * n for _ in range(n)], "cap": 10**9,
                "outlets": [[n - 1, n - 1, 19]]}, [[19] * n for _ in range(n)]
    return None
