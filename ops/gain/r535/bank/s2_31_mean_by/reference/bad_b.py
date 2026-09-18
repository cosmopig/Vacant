def mean_by(rows, field):
    vals = [r[field] for r in rows]
    if not vals:
        return 0.0
    return sum(vals) / len(vals)
