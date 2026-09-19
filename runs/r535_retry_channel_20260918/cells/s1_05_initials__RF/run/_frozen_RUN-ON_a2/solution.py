def get_initials(full_name):
    parts = full_name.split()
    return "".join(part[0].upper() for part in parts)

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        print(get_initials(" ".join(sys.argv[1:])))
