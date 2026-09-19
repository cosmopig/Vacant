def initials(full_name):
    parts = full_name.split()
    return [part[0].upper() for part in parts if part]

if __name__ == "__main__":
    # Examples
    print(initials("John Doe"))  # ['J', 'D']
    print(initials("Mary Jane Watson"))  # ['M', 'J', 'W']
    print(initials("  johndoe  "))  # ['J']
