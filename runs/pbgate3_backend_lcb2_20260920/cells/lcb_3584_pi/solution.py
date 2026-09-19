def validSequence(word1: str, word2: str):
    import bisect

    n = len(word1)
    m = len(word2)

    next_occ = [[] for _ in range(26)]
    for i, char in enumerate(word1):
        next_occ[ord(char) - ord('a')].append(i)

    def get_next(char_idx, start_pos):
        indices = next_occ[char_idx]
        pos = bisect.bisect_left(indices, start_pos)
        if pos < len(indices):
            return indices[pos]
        return float('inf')

    # pref[j]: smallest index for word2[j] such that it matches and > pref[j-1].
    pref = [float('inf')] * m
    curr = -1
    for j in range(m):
        res = get_next(ord(word2[j]) - ord('a'), curr + 1)
        if res == float('inf'):
            break
        pref[j] = res
        curr = res

    # suff[j]: largest index for word2[j] such that it matches and < suff[j+1].
    suff = [float('-inf')] * m
    curr = n
    for j in range(m - 1, -1, -1):
        indices = next_occ[ord(word2[j]) - ord('a')]
        pos = bisect.bisect_left(indices, curr)
        if pos > 0:
            res = indices[pos - 1]
            suff[j] = res
            curr = res
        else:
            break

    best_seq = None

    # Case 1: No changes.
    all_match = True
    for j in range(m):
        if pref[j] == float('inf'):
            all_match = False
            break
    if all_match:
        best_seq = list(pref)

    # Case 2: Exactly one change at index k.
    for k in range(m):
        ik = -1
        if k == 0:
            ik = 0
        else:
            if pref[k-1] == float('inf'):
                continue
            ik = pref[k-1] + 1
        
        # Check if ik is valid (i.e., there exists a sequence for j > k starting after ik)
        is_valid = True
        if k + 1 < m:
            if suff[k+1] <= ik:
                is_valid = False
        elif ik >= n:
            is_valid = False

        if is_valid and ik < n:
            current_seq = []
            if k > 0:
                for j in range(k):
                    current_seq.append(pref[j])
            
            current_seq.append(ik)
            
            curr_idx = ik
            possible = True
            for j in range(k + 1, m):
                res = get_next(ord(word2[j]) - ord('a'), curr_idx + 1)
                if res == float('inf'):
                    possible = False
                    break
                current_seq.append(res)
                curr_idx = res
            
            if possible:
                if best_seq is None or current_seq < best_seq:
                    best_seq = current_seq

    return best_seq if best_seq is not None else []
