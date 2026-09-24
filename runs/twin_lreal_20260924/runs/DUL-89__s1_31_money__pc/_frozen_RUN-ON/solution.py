def money(cents):
    dollars = cents // 100
    remainder = cents % 100
    return f"${dollars}.{remainder:02d}"
