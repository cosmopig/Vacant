def numberOfSubstrings(s: str, k: int):
    n = len(s)
    total = n * (n + 1) // 2

    if k <= 0:
        return total

    chars = [ord(c) - 97 for c in s]
    count = [0] * 26
    left = 0
    invalid = 0

    for right, c in enumerate(chars):
        count[c] += 1

        while count[c] >= k:
            count[chars[left]] -= 1
            left += 1

        invalid += right - left + 1

    return total - invalid
