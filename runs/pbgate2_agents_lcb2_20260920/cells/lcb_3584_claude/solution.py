def validSequence(word1: str, word2: str) -> list[int]:
    """
    Finds the lexicographically smallest sequence of indices in word1 such that
    the characters at these indices form a string almost equal to word2.
    A string x is almost equal to y if you can change at most one character in x
    to make it identical to y.
    """
    n = len(word1)
    m = len(word2)

    # We need to find a subsequence of length m from word1 that matches word2
    # with at most one mismatch.
    # Since we want the lexicographically smallest sequence of indices,
    # we should try to pick the smallest possible index for each position in word2.

    # Let's pre-calculate the next occurrence of each character in word1.
    next_occ = [[-1] * 26 for _ in range(n + 1)]
    for i in range(n - 1, -1, -1):
        for j in range(26):
            next_occ[i][j] = next_occ[i+1][j]
        next_occ[i][ord(word1[i]) - ord('a')] = i

    # We want to find a sequence of indices [i0, i1, ..., im-1] such that:
    # 1. 0 <= i0 < i1 < ... < im-1 < n
    # 2. word1[i0]word1[i1]...word1[im-1] is almost equal to word2
    # 3. [i0, i1, ..., im-1] is lexicographically smallest.

    # To find the lexicographically smallest sequence of indices:
    # We can use a greedy approach with backtracking or dynamic programming.
    # However, since we only have ONE mismatch allowed, we can iterate over
    # which position in word2 (if any) has the mismatch.

    best_seq = []

    def find_min_indices(mismatch_idx: int = -1):
        """
        Finds the lexicographically smallest sequence of indices where
        the character at index `mismatch_idx` in word2 is allowed to be different
        from the corresponding character in word1.
        If mismatch_idx is -1, all characters must match exactly.
        """
        seq = []
        curr_pos = 0
        for i in range(m):
            # Try to find the smallest index j >= curr_pos such that:
            # if i == mismatch_idx, word1[j] can be anything (but we want smallest j)
            # else, word1[j] must equal word2[i].

            found = False
            for j in range(curr_pos, n):
                if i == mismatch_idx:
                    # Any character works, but we need to ensure there's enough
                    # characters left for the remaining m - 1 - i positions.
                    if n - j >= m - i:
                        seq.append(j)
                        curr_pos = j + 1
                        found = True
                        break
                else:
                    if word1[j] == word2[i]:
                        seq.append(j)
                        curr_pos = j + 1
                        found = True
                        break
            if not found:
                return None
        return seq

    # Case 0: No mismatch (all characters match exactly)
    res = find_min_indices(-1)
    if res is not None:
        best_seq = res

    # Case 1: Exactly one mismatch at position k in word2
    for k in range(m):
        res = find_min_indices(k)
        if res is not None:
            if not best_seq or res < best_seq:
                best_seq = res

    return best_seq if best_seq else []

