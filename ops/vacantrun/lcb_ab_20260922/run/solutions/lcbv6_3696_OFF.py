def countSubstrings(s: str) -> int:
    total_answer = 0
    for d in range(1, 10):
        count = [0] * d
        d_str = str(d)
        for char in s:
            digit = int(char)
            new_count = [0] * d
            new_count[digit % d] += 1
            for r in range(d):
                if count[r]:
                    new_count[(r * 10 + digit) % d] += count[r]
            count = new_count
            if char == d_str:
                total_answer += count[0]
    return total_answer
