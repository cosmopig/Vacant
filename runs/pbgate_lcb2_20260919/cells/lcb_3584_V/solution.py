def validSequence(word1: str, word2: str):
    n = len(word1)
    m = len(word2)

    L = [0] * m
    curr = 0
    for i in range(m):
        while curr < n and word1[curr] != word2[i]:
            curr += 1
        if curr >= n:
            return []
        L[i] = curr
        curr += 1

    R = [0] * m
    curr = n - 1
    for i in range(m - 1, -1, -1):
        while curr >= 0 and word1[curr] != word2[i]:
            curr -= 1
        if curr < 0:
            return []
        R[i] = curr
        curr -= 1

    P = [0] * m
    prev_p = -1
    for i in range(m):
        P[i] = max(L[i], prev_p + 1)
        prev_p = P[i]

    IsP_correct = [True] * m
    for i in range(m):
        if P[i] > R[i]:
            IsP_correct[i] = False
        if i > 0 and not IsP_correct[i-1]:
            IsP_correct[i] = False

    A = [L[j] - j for j in range(m)]
    B = [R[j] - j for j in range(m)]

    minB_suffix = [0] * (m + 1)
    minB_suffix[m] = float('inf')
    for i in range(m - 1, -1, -1):
        minB_suffix[i] = min(B[i], minB_suffix[i+1])

    J_max = -1
    for j in range(m):
        if A[j] > minB_suffix[j]:
            J_max = max(J_max, j)

    candidates = []

    # Case: No mismatch (all word1[i_k] == word2[k])
    possible_none = True
    for i in range(m):
        if not IsP_correct[i]:
            possible_none = False
            break
    if possible_none:
        candidates.append(list(P))

    # Case: Mismatch at position k (word1[i_k] can be anything)
    for k in range(m):
        if k > 0 and not IsP_correct[k-1]:
            continue
        
        p_min = P[k-1] + 1 if k > 0 else 0
        
        if k == m - 1:
            p_max = n - 1
        else:
            p_max = minB_suffix[k+1] + (k - 1)
            
        if p_min <= p_max and k >= J_max:
            res = [0] * m
            for j in range(k):
                res[j] = P[j]
            res[k] = p_min
            prev = res[k]
            for j in range(k + 1, m):
                res[j] = max(L[j], prev + 1)
                prev = res[j]
            candidates.append(res)

    if not candidates:
        return []
    
    return min(candidates)
