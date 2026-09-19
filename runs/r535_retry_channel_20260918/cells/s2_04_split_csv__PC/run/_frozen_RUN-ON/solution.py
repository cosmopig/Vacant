def split_csv(line):
    if not line.strip():
        return []
    fields = line.split(',')
    return [field.strip() for field in fields]
