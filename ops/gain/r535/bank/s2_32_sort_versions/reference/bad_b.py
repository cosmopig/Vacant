def sort_versions(vs):
    return sorted(vs, key=lambda v: [int(p) for p in v.split(".")],
                  reverse=True)
