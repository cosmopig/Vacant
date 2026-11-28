MATCH_RESULTS = {"win", "loss", "draw"}


def tally(rows):
    teams = {}

    def record(name):
        if name not in teams:
            teams[name] = {"mp": 0, "w": 0, "d": 0, "l": 0, "p": 0}
        return teams[name]

    for row in rows:
        row = row.strip()
        if not row:
            continue
        parts = row.split(";")
        if len(parts) != 3:
            raise ValueError(f"invalid input line: {row!r}")
        home, away, outcome = parts
        if outcome not in MATCH_RESULTS:
            raise ValueError(f"invalid outcome: {outcome!r}")

        a = record(home)
        b = record(away)
        a["mp"] += 1
        b["mp"] += 1

        if outcome == "win":
            a["w"] += 1
            a["p"] += 3
            b["l"] += 1
        elif outcome == "loss":
            b["w"] += 1
            b["p"] += 3
            a["l"] += 1
        else:
            a["d"] += 1
            b["d"] += 1
            a["p"] += 1
            b["p"] += 1

    ordered = sorted(teams.items(), key=lambda kv: -kv[1]["p"])

    lines = ["Team                           | MP |  W |  D |  L |  P"]
    for name, s in ordered:
        lines.append(
            f"{name:<31}| {s['mp']:>2} | {s['w']:>2} | {s['d']:>2} | {s['l']:>2} | {s['p']:>2}"
        )
    return lines
