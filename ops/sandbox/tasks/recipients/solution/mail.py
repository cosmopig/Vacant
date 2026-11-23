def recipients(addresses):
    result = []
    seen = set()
    for address in addresses:
        clean = address.strip()
        if clean and clean.casefold() not in seen:
            result.append(clean)
            seen.add(clean.casefold())
    return result
