def initials(name):
    parts = name.split(' ')
    result = []
    for part in parts:
        if '-' in part:
            sub_parts = part.split('-')
            for sub in sub_parts:
                if sub:
                    result.append(f"{sub[0].upper()}.")
        else:
            if part:
                result.append(f"{part[0].upper()}.")
    return "".join(result)

# Examples
if __name__ == "__main__":
    print(initials("John Doe"))           # J.D.
    print(initials("Jean-Luc Picard"))   # J.L.P.
    print(initials("Anne-Marie Smith"))  # A.M.S.
    print(initials("Mary-Jane Watson"))  # M.J.W.
    print(initials("John Doe-Smith"))    # J.D.S.
