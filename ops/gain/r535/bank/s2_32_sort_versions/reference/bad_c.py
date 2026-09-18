def version_sort(vs):
    return sorted(vs, key=lambda v: [int(p) for p in v.split(".")])
