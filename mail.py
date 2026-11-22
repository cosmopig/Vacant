def recipients(addresses):
    seen = set()
    result = []
    for address in addresses:
        cleaned = address.strip()
        if not cleaned:
            continue
        key = cleaned.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(cleaned)
    return result
