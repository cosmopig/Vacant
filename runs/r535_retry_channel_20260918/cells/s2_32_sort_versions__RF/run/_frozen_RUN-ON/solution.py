def sort_versions(vs):
    def version_key(v):
        return [int(part) for part in v.split('.')]
    
    return sorted(vs, key=version_key)
