def validSequence(word1: str, word2: str):
    import bisect

    n = len(word1)
    m = len(word2)

    pos = [[] for _ in range(26)]
    for i, c in enumerate(word1):
        pos[ord(c) - ord('a')].append(i)

    def get_next_pos(char_idx, current_min_idx):
        p = pos[char_idx]
        idx = bisect.bisect_left(p, current_min_idx)
        if idx < len(p):
            return p[idx]
        return float('inf')

    # Precompute the smallest possible indices for each suffix of word2 starting from some index in word1.
    # Actually, we need to know if it's possible to complete a sequence of length (m-j) 
    # using characters from word2[j:] starting from index p in word1.
    # Let can_complete(j, p) be true if there exists indices i_j < i_{j+1} < ... < i_{m-1}
    # such that all i_x > p and for x != k (some fixed k), word1[i_x] == word2[x].

    # This is still slightly wrong because of the "at most one change" rule.
    # The rule says: there exists some k in [0, m-1] such that 
    # for all j != k, word1[i_j] == word2[j].
    # For a fixed k, we want to find the lexicographically smallest sequence i_0, ..., i_{m-1}.

    best_seq = None

    for k in range(m):
        current_seq = []
        curr_idx = 0
        possible = True
        
        # For j < k, we must have word1[i_j] == word2[j]
        for j in range(k):
            p = get_next_pos(ord(word2[j]) - ord('a'), curr_idx)
            if p == float('inf'):
                possible = False
                break
            current_seq.append(p)
            curr_idx = p + 1
        
        if not possible: continue
        
        # For j = k, i_k is the smallest index > i_{k-1} (or >=0 if k=0)
        # To make it lexicographically smallest, we want i_k to be as small as possible.
        # The smallest possible value for i_k is curr_idx.
        current_seq.append(curr_idx)
        curr_idx = current_seq[-1] + 1
        
        # For j > k, we must have word1[i_j] == word2[j]
        for j in range(k + 1, m):
            p = get_next_pos(ord(word2[j]) - ord('a'), curr_idx)
            if p == float('inf'):
                possible = False
                break
            current_seq.append(p)
            curr_idx = p + 1
        
        if possible:
            # Check if the sequence is valid (indices are strictly increasing and < n)
            if current_seq[-1] < n:
                if best_seq is None or current_seq < best_seq:
                    best_seq = current_seq

    return best_seq if best_seq is not None else []
