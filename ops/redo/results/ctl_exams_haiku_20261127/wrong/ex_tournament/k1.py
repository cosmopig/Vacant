WIN_POINTS = 3
DRAW_POINTS = 1

HEADER = f"{'Team':<31}| {'MP':>2} | {'W':>2} | {'D':>2} | {'L':>2} | {'P':>2}"


def tally(rows):
    if len(rows) < 2:
        return [HEADER]

    stats = {}

    def record(team):
        return stats.setdefault(team, {"w": 0, "d": 0, "l": 0})

    for row in rows:
        parts = row.split(";")
        if len(parts) != 3:
            raise ValueError(f"invalid line: {row!r}")
        home, away, outcome = parts
        a = record(home)
        b = record(away)
        if outcome == "win":
            a["w"] += 1
            b["l"] += 1
        elif outcome == "loss":
            a["l"] += 1
            b["w"] += 1
        elif outcome == "draw":
            a["d"] += 1
            b["d"] += 1
        else:
            raise ValueError(f"unknown outcome: {outcome!r}")

    table = []
    for team, s in stats.items():
        mp = s["w"] + s["d"] + s["l"]
        points = s["w"] * WIN_POINTS + s["d"] * DRAW_POINTS
        table.append((points, team, mp, s["w"], s["d"], s["l"]))

    table.sort(key=lambda r: (-r[0], r[1]))

    lines = [HEADER]
    for points, team, mp, w, d, l in table:
        lines.append(f"{team:<31}| {mp:>2} | {w:>2} | {d:>2} | {l:>2} | {points:>2}")
    return lines
