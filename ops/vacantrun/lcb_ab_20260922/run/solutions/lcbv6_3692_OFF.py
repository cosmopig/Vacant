import bisect

def kmp_search(text, pattern):
    if not pattern:
        return list(range(len(text) + 1))
    m = len(pattern)
    n = len(text)
    pi = [0] * m
    for i in range(1, m):
        j = pi[i-1]
        while j > 0 and pattern[i] != pattern[j]:
            j = pi[j-1]
        if pattern[i] == pattern[j]:
            j += 1
        pi[i] = j
    
    indices = []
    q = 0
    for i in range(n):
        while q > 0 and pattern[q] != text[i]:
            q = pi[q-1]
        if pattern[q] == text[i]:
            q += 1
        if q == m:
            indices.append(i - m + 1)
            q = pi[q-1]
    return indices

def shortestMatchingSubstring(s, p):
    parts = p.split('*')
    A = parts[0]
    B = parts[1]
    C = parts[2]
    
    len_A = len(A)
    len_B = len(B)
    len_C = len(C)
    
    pos_B = kmp_search(s, B) if len_B > 0 else None
    pos_C = [idx + len_C for idx in kmp_search(s, C)] if len_C > 0 else None
    
    min_len = float('inf')
    n = len(s)
    
    for i in range(n + 1):
        if s[i : i + len_A] == A:
            # Find min_j1 >= i + len_A
            if len_B > 0:
                idx = bisect.bisect_left(pos_B, i + len_A)
                if idx < len(pos_B):
                    min_j1 = pos_B[idx]
                else:
                    continue
            else:
                min_j1 = i + len_A
            
            # Find min_k >= min_j1 + len_B + len_C
            if len_C > 0:
                idx = bisect.bisect_left(pos_C, min_j1 + len_B + len_C)
                if idx < len(pos_C):
                    min_k = pos_C[idx]
                else:
                    continue
            else:
                min_k = min_j1 + len_B
            
            # The substring is s[i : min_k]
            # We must ensure min_k <= n and i <= min_k
            if min_k <= n and i <= min_k:
                min_len = min(min_len, min_k - i)
                
    return min_len if min_len != float('inf') else -1
