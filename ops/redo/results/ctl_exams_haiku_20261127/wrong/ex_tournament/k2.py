from collections import defaultdict

WIN_POINTS = 3
DRAW_POINTS = 1
LOSS_POINTS = 0


def _blank_record():
    return {"MP": 0, "W": 0, "D": 0, "L": 0, "P": 0}


def _format_row(team, record):
    return (
        f"{team:<30} | {record['MP']:>2} | {record['W']:>2} | "
        f"{record['D']:>2} | {record['L']:>2} | {record['P']:>2}"
    )


def tally(rows):
    stats = defaultdict(_blank_record)

    for row in rows:
        if not row or not row.strip():
            continue
        parts = row.split(";")
        if len(parts) != 3:
            raise ValueError(f"invalid input line: {row!r}")
        home, away, outcome = parts

        home_rec = stats[home]
        away_rec = stats[away]
        home_rec["MP"] += 1
        away_rec["MP"] += 1

        if outcome == "win":
            home_rec["W"] += 1
            home_rec["P"] += WIN_POINTS
            away_rec["L"] += 1
            away_rec["P"] += LOSS_POINTS
        elif outcome == "loss":
            away_rec["W"] += 1
            away_rec["P"] += WIN_POINTS
            home_rec["L"] += 1
            home_rec["P"] += LOSS_POINTS
        elif outcome == "draw":
            home_rec["D"] += 1
            home_rec["P"] += DRAW_POINTS
            away_rec["D"] += 1
            away_rec["P"] += DRAW_POINTS
        else:
            raise ValueError(f"invalid outcome: {outcome!r}")

    ordered = sorted(
        stats.items(),
        key=lambda item: (item[1]["P"], item[0]),
        reverse=True,
    )

    header = (
        f"{'Team':<30} | {'MP':>2} | {'W':>2} | "
        f"{'D':>2} | {'L':>2} | {'P':>2}"
    )
    lines = [header]
    lines.extend(_format_row(team, record) for team, record in ordered)
    return lines
