def get_initials(full_name: str) -> str:
    parts = full_name.split()
    return "".join(part[0].upper() for part in parts if part)

if __name__ == "__main__":
    # Example usage:
    print(get_initials("John Doe"))  # Output: JD
    print(get_initials("Jane Mary Smith"))  # Output: JMS
