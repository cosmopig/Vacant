def pluck(rows, field):
    return [r.get(field) for r in rows]
