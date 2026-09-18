def mean_by(rows, field):
    vals = [r.get(field, 0) for r in rows]
    if not vals:
        return 0.0
    return sum(vals) / len(vals)
