def numberOfSubstrings(s: str, k: int):
    n = len(s)
    total = n * (n + 1) // 2

    if k <= 0:
        return total

    counts = [0] * 26
    left = 0
    invalid = 0

    for right, ch in enumerate(s):
        idx = ord(ch) - ord('a')
        counts[idx] += 1

        while counts[idx] >= k:
            left_idx = ord(s[left]) - ord('a')
            counts[left_idx] -= 1
            left += 1

        invalid += right - left + 1

    return total - invalid
