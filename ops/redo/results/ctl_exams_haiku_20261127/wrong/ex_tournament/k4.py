def tally(rows):
    table = {}

    def record(name):
        return table.setdefault(name, {"w": 0, "d": 0, "l": 0})

    for row in rows:
        if not row or not row.strip():
            continue
        parts = row.split(";")
        if len(parts) != 3:
            raise ValueError(f"malformed row: {row!r}")
        home, away, outcome = parts
        h = record(home)
        a = record(away)
        if outcome == "win":
            h["w"] += 1
            a["l"] += 1
        elif outcome == "draw":
            h["d"] += 1
            a["d"] += 1
        else:
            a["w"] += 1
            h["l"] += 1

    standings = []
    for name, s in table.items():
        mp = s["w"] + s["d"] + s["l"]
        points = 3 * s["w"] + s["d"]
        standings.append((name, mp, s["w"], s["d"], s["l"], points))

    standings.sort(key=lambda t: (-t[5], t[0]))

    lines = [f"{'Team':<31}| {'MP':>2} | {'W':>2} | {'D':>2} | {'L':>2} | {'P':>2}"]
    for name, mp, w, d, l, p in standings:
        lines.append(f"{name:<31}| {mp:>2} | {w:>2} | {d:>2} | {l:>2} | {p:>2}")
    return lines
