def mean_by(rows, field):
    values = [row[field] for row in rows if field in row and isinstance(row[field], (int, float))]
    if not values:
        return 0.0
    return sum(values) / len(values)
