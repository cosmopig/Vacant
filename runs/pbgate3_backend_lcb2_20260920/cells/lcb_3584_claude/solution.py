def validSequence(word1: str, word2: str) -> list[int]:
    """
    Finds the lexicographically smallest sequence of indices in word1 such that
    the characters at these indices form a string almost equal to word2.
    A string x is called almost equal to y if you can change at most one character in x
    to make it identical to y.
    """
    n = len(word1)
    m = len(word2)

    # Precompute next positions for each character
    next_pos = [[n] * (n + 1) for _ in range(26)]
    for i in range(n - 1, -1, -1):
        for c in range(26):
            next_pos[c][i] = next_pos[c][i+1]
        next_pos[ord(word1[i]) - ord('a')][i] = i

    # Precompute max_starts: the largest index i_j such that word2[j:] can be completed.
    import bisect
    char_indices = [[] for _ in range(26)]
    for i, char in enumerate(word1):
        char_indices[ord(char) - ord('a')].append(i)

    max_starts = [-1] * m
    # Find largest index for word2[m-1]
    idx_list = char_indices[ord(word2[m-1]) - ord('a')]
    if idx_list:
        max_starts[m-1] = idx_list[-1]

    for j in range(m - 2, -1, -1):
        idx_list = char_indices[ord(word2[j]) - ord('a')]
        # Find largest i in idx_list such that i < max_starts[j+1]
        pos = bisect.bisect_left(idx_list, max_starts[j+1])
        if pos > 0:
            max_starts[j] = idx_list[pos - 1]

    # If any character in word2 cannot be matched at all, return []
    for j in range(m):
        if max_starts[j] == -1:
            return []

    def get_greedy_seq(start_indices):
        """Helper to build a sequence from a set of required characters and starting points."""
        res = []
        curr = 0
        for i, char in enumerate(start_indices):
            # If we need to match word2[i] exactly
            if i < len(start_indices) and start_indices[i] != -1:
                p = next_pos[ord(word2[i]) - ord('a')][curr]
                if p >= n: return None
                res.append(p)
                curr = p + 1
            else:
                # This part is handled by the specific k logic
                pass
        return res

    # Case 0: Exact match (no changes needed)
    best_seq = []
    curr = 0
    possible = True
    for i in range(m):
        p = next_pos[ord(word2[i]) - ord('a')][curr]
        if p >= n:
            possible = False
            break
        best_seq.append(p)
        curr = p + 1
    if possible:
        # best_seq is a candidate
        pass

    # We want the lexicographically smallest sequence, so we initialize with a very large one
    # or just compare as we go.
    final_best = None

    def update_best(seq):
        nonlocal final_best
        if seq is None: return
        if final_best is None or seq < final_best:
            final_best = list(seq)

    # Re-evaluate best_seq as a candidate
    update_best(best_seq)

    # Case 1: One change at position k in word2.
    for k in range(m):
        res = []
        curr = 0
        possible = True

        # Match greedily until k-1
        for j in range(k):
            p = next_pos[ord(word2[j]) - ord('a')][curr]
            if p >= n:
                possible = False
                break
            res.append(p)
            curr = p + 1

        if not possible: continue

        # Handle mismatch at k
        if k == 0:
            # Smallest i_0 such that word2[1:] can be completed in word1[i_0+1:]
            # This is true if next_pos[word2[1]][1] < max_starts[1] (if m > 1)
            # or always true if m == 1.
            i_k = 0
            if m > 1:
                p_next = next_pos[ord(word2[1]) - ord('a')][i_k + 1]
                if p_next >= max_starts[1]:
                    possible = False

            if possible:
                res.append(i_k)
                curr = i_k + 1
                # Continue greedily for j > k
                for j in range(k + 1, m):
                    p = next_pos[ord(word2[j]) - ord('a')][curr]
                    if p >= n:
                        possible = False
                        break
                    res.append(p)
                    curr = p + 1
        else:
            # Smallest i_k > i_{k-1} such that word2[k+1:] can be completed in word1[i_k+1:]
            i_k = res[-1] + 1
            if k < m - 1:
                p_next = next_pos[ord(word2[k+1]) - ord('a')][i_k + 1]
                if p_next >= max_starts[k+1]:
                    possible = False

            if possible:
                res.append(i_k)
                curr = i_k + 1
                # Continue greedily for j > k
                for j in range(k + 1, m):
                    p = next_pos[ord(word2[j]) - ord('a')][curr]
                    if p >= n:
                        possible = False
                        break
                    res.append(p)
                    curr = p + 1

        if possible:
            update_best(res)

    return final_best if final_best is not None else []
