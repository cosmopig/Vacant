def initials(*names):
    parts = []
    for name in names:
        parts.extend(name.split())
    return [part[0].upper() for part in parts if part]

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        print("".join(initials(*sys.argv[1:])))
