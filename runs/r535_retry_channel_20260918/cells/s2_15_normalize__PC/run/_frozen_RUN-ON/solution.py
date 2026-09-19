def normalize(p):
    if not p:
        return ""
    
    # Replace multiple separators with a single one
    import re
    normalized = re.sub(r'/+', '/', p)
    
    # Remove trailing separator unless the whole path is just '/'
    if len(normalized) > 1 and normalized.endswith('/'):
        normalized = normalized[:-1]
        
    return normalized
