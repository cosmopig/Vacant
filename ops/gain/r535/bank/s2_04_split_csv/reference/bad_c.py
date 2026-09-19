def parse_csv(line):
    if not line:
        return []
    return [p.strip() for p in line.split(",")]
