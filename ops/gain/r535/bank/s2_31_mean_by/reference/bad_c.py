def average_by(rows, field):
    vals = [r[field] for r in rows if field in r]
    if not vals:
        return 0.0
    return sum(vals) / len(vals)
