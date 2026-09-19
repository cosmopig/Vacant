from typing import List

def validSequence(word1: str, word2: str) -> List[int]:
    n = len(word1)
    m = len(word2)
    
    # Precompute the leftmost possible indices for each character in word2
    # such that they form a subsequence of word1.
    # However, we need to allow at most one change.
    
    # Let's re-evaluate: 
    # We want lexicographically smallest sequence of indices [i_0, i_1, ..., i_{m-1}]
    # such that word1[i_j] == word2[j] for all j except at most one index k.
    # For the changed index k, word1[i_k] can be anything (we change it to word2[k]).
    
    # To get lexicographically smallest indices:
    # We want i_0 as small as possible, then i_1 as small as possible, etc.
    
    # Since we only have one change allowed, there are two cases:
    # 1. Zero changes: word2 is a subsequence of word1.
    # 2. One change at index k in word2: word2[0...k-1] + char_at_i_k + word2[k+1...m-1]
    #    where we "change" word1[i_k] to word2[k]. This means i_k can be any index 
    #    that appears after i_{k-1} and before i_{k+1}.
    
    # Actually, the condition is: there exists an index k in [0, m-1] such that
    # if we change word1[i_k] to word2[k], then word1[i_j] == word2[j] for all j != k.
    # This is equivalent to saying: 
    # There exists an index k in [0, m-1] such that the sequence of indices i_0, ..., i_{m-1}
    # satisfies:
    # - i_0 < i_1 < ... < i_{m-1}
    # - word1[i_j] == word2[j] for all j != k
    # - For the index k, word1[i_k] can be anything (because we can change it to word2[k]).
    
    # To find the lexicographically smallest sequence:
    # We can iterate over all possible positions k of the "changed" character in word2.
    # But there are m such positions, and for each, we want the best indices.
    # This still feels like it could be slow if not careful.
    
    # Let's simplify: 
    # A sequence i_0, ..., i_{m-1} is valid if there exists k \in [0, m-1] such that
    # for all j \neq k, word1[i_j] == word2[j].
    
    # Let L[j] be the smallest possible index i_j such that word1[i_0...i_j] 
    # matches word2[0...j] with zero changes.
    L = [0] * m
    curr = 0
    for j in range(m):
        while curr < n and word1[curr] != word2[j]:
            curr += 1
        if curr >= n:
            # No zero-change subsequence exists for the prefix.
            # But a one-change might still exist.
            break
        L[j] = curr
        curr += 1
    else:
        # Zero-change subsequence exists. The smallest indices are L[0], L[1], ...
        # Wait, this is not correct because changing an earlier character might allow 
        # a smaller index for a later character.
        pass

    # Let's use the property that we want lexicographically smallest [i_0, ..., i_{m-1}].
    # This means we want i_0 to be as small as possible.
    # If we can pick i_0 such that there exists a valid sequence starting with i_0, 
    # then i_0 is the best choice.
    
    # A sequence i_0, ..., i_{m-1} is valid if:
    # \exists k \in [0, m-1] s.t. \forall j \neq k, word1[i_j] == word2[j].
    
    # Let's precompute:
    # pref[j]: the smallest index i_j such that word1[i_0...i_j] matches word2[0...j] 
    #            with zero changes, and i_r < i_{r+1}.
    # suff[j]: the largest index i_j such that word1[i_j...i_{m-1}] matches word2[j...m-1]
    #            with zero changes, and i_r < i_{r+1}.

    pref = [float('inf')] * m
    curr = 0
    for j in range(m):
        while curr < n and word1[curr] != word2[j]:
            curr += 1
        if curr < n:
            pref[j] = curr
            curr += 1
        else:
            break

    suff = [float('inf')] * m
    curr = n - 1
    for j in range(m - 1, -1, -1):
        while curr >= 0 and word1[curr] != word2[j]:
            curr -= 1
        if curr >= 0:
            suff[j] = curr
            curr -= 1
        else:
            break

    # Now, for a fixed k (the index of the changed character in word2):
    # We want to find i_0, ..., i_{m-1} such that:
    # - i_0 < i_1 < ... < i_{k-1} < i_k < i_{k+1} < ... < i_{m-1}
    # - word1[i_j] == word2[j] for j != k
    # - i_j is as small as possible.
    
    # For a fixed k:
    # i_0 = pref[0]
    # i_1 = pref[1] (but must be > i_0) -> actually, if we use the greedy 
    # approach for pref, it already gives the smallest indices.
    # So for j < k, i_j = pref[j].
    # For j > k, i_j is the smallest index > i_{j-1} such that word1[i_j] == word2[j].
    # And we need to ensure there exists some i_k > i_{k-1} and < i_{k+1}.
    
    # This still feels like we can iterate k from 0 to m-1.
    # For each k, the best sequence is:
    # i_0 = pref[0]
    # ...
    # i_{k-1} = pref[k-1]
    # i_k = smallest index > i_{k-1} (if k>0) or 0 (if k=0) such that there exists 
    #       a valid sequence for the rest.
    # The "rest" is word2[k+1...m-1] matching a subsequence of word1 starting after i_k.
    # This means we need suff[k+1] > i_k.
    
    best_seq = None

    for k in range(m):
        current_seq = []
        possible = True
        last_idx = -1
        
        # Indices before k
        for j in range(k):
            idx = pref[j]
            if idx <= last_idx: # Should not happen with greedy pref
                possible = False
                break
            current_seq.append(idx)
            last_idx = idx
        
        if not possible: continue
        
        # Index k (the changed one)
        # We want the smallest i_k > last_idx such that there exists a valid 
        # sequence for j > k.
        # A valid sequence for j > k exists if suff[j] is reachable.
        # Specifically, we need i_{k+1} < i_{k+2} ... and word1[i_j] == word2[j].
        # The smallest possible value for i_{k+1} is the one that allows 
        # the rest of the sequence to be completed.
        # This is exactly what suff[k+1] helps with? No, suff is largest.
        # Let's use a different approach for the suffix.
        
        # Let's redefine:
        # min_suffix_idx[j]: smallest index i_j such that word2[j...m-1] 
        #                      is a subsequence of word1[i_j...n-1] 
        #                      with zero changes.
        # This is just the greedy matching from the right.
        pass

    # Let's restart the logic.
    # A sequence i_0, ..., i_{m-1} is valid if there exists k such that:
    # word1[i_j] == word2[j] for all j != k.
    
    # To find the lexicographically smallest:
    # We want to minimize i_0, then i_1, etc.
    
    # Let's precompute:
    # L[j]: smallest index i_j such that word2[0...j] is a subsequence of 
    #        word1[0...i_j] with zero changes. (Greedy from left)
    L = [float('inf')] * m
    curr = 0
    for j in range(m):
        while curr < n and word1[curr] != word2[j]:
            curr += 1
        if curr < n:
            L[j] = curr
            curr += 1
        else: break

    # R[j]: largest index i_j such that word2[j...m-1] is a subsequence of 
    #        word1[i_j...n-1] with zero changes. (Greedy from right)
    R = [float('inf')] * m
    curr = n - 1
    for j in range(m - 1, -1, -1):
        while curr >= 0 and word1[curr] != word2[j]:
            curr -= 1
        if curr >= 0:
            R[j] = curr
            curr -= 1
        else: break

    # Now, for a fixed k (the changed index):
    # i_0 = L[0]
    # i_1 = L[1]
    # ...
    # i_{k-1} = L[k-1]
    # i_k = smallest index > i_{k-1} such that there exists a sequence 
    #       for j > k.
    # The condition for "there exists a sequence for j > k" is:
    # There exist i_{k+1}, ..., i_{m-1} such that 
    # i_k < i_{k+1} < ... < i_{m-1} and word1[i_j] == word2[j] for j > k.
    # The smallest possible value for i_{k+1} is L[k+1] if we didn't have the 
    # constraint i_k < i_{k+1}.
    # With the constraint, the smallest i_{k+1} is the first occurrence of word2[k+1] 
    # after i_k. Let's call this next_occ(char, start_idx).
    # But we also need to ensure that from i_{k+1}, we can complete the rest.
    # The condition for completing the rest is:
    # there exists a zero-change subsequence of word2[k+1...m-1] in word1[i_{k+1}+1...n-1].
    # This is true if and only if the greedy matching from the right works.
    # The largest possible index for i_{k+1} is R[k+1].
    # So we need to find smallest i_k > i_{k-1} such that there exists 
    # i_{k+1} with i_k < i_{k+1} and i_{k+1} <= R[k+1] (and i_{k+1} is an occurrence of word2[k+1]).
    # Actually, it's simpler: we need to find smallest i_k > i_{k-1} such that 
    # there exists a zero-change subsequence of word2[k+1...m-1] in word1[i_k+1...n-1].
    # This is true if and only if R[k+1] > i_k. (Wait, R[k+1] is the largest index for i_{k+1}).
    # If R[k+1] exists and R[k+1] > i_k, then there's at least one index for i_{k+1} 
    # that is > i_k. Since we want the smallest such sequence, we can just pick 
    # the smallest possible indices for j > k greedily.

    best_seq = []
    
    for k in range(m):
        current_seq = []
        possible = True
        last_idx = -1
        
        # Indices before k: must be zero-change and greedy
        for j in range(k):
            idx = L[j]
            if idx <= last_idx:
                possible = False
                break
            current_seq.append(idx)
            last_idx = idx
        
        if not possible: continue
        
        # Index k: smallest i_k > last_idx such that R[k+1] > i_k (if k < m-1)
        # or just any i_k > last_idx (if k == m-1).
        # Wait, if k < m-1, we need to ensure there's enough room for word2[k+1...m-1].
        # The condition is: there exists a zero-change subsequence of word2[k+1...m-1] 
        # in word1[i_k+1...n-1].
        # This is true if and only if the greedy matching from the right for word2[k+1...m-1]
        # ends at an index > i_k.
        # The largest such index is R[k+1]. So we need R[k+1] > i_k.
        # Wait, no. If R[k+1] exists, it's the largest possible index for i_{k+1}.
        # We need to know if there is ANY index for i_{k+1} that is > i_k 
        # and allows completing the rest.
        # The smallest such index would be the first occurrence of word2[k+1] after i_k,
        # say it's 'next'. We need next < R[k+2] (if k+2 < m) ... no.
        # Let's use: there exists a zero-change subsequence of word2[k+1...m-1] 
        # in word1[i_k+1...n-1]. This is true if and only if R[k+1] > i_k.
        # Wait, R[k+1] is the largest index for i_{k+1}. If R[k+1] exists and 
        # we can find an occurrence of word2[k+1] at some index p such that 
        # last_idx < p <= R[k+1], then it's possible.
        # Actually, the condition "there exists a zero-change subsequence of 
        # word2[k+1...m-1] in word1[i_k+1...n-1]" is equivalent to:
        # there exists some index p > last_idx such that word1[p] == word2[k+1] 
        # and the remaining word2[k+2...m-1] can be matched in word1[p+1...n-1].
        # The second part is true if R[k+2] > p (if k+2 < m).
        # So we need to find smallest p > last_idx such that:
        # 1. word1[p] == word2[k+1] (if k+1 < m) OR p is any index > last_idx (if k=m-1)
        # 2. If k+1 < m, then R[k+2] > p (if k+2 < m) or R[k+1] exists and we can pick some p.
        
        # Let's simplify:
        # For a fixed k, the sequence is i_0, ..., i_{m-1}.
        # j < k: i_j = L[j]. (Must check if L[j] > L[j-1])
        # j = k: i_k = smallest index > i_{k-1} such that there exists a zero-change 
        #           subsequence of word2[k+1...m-1] in word1[i_k+1...n-1].
        # This condition is equivalent to R[k+1] > i_k (if k < m-1) or always true (if k = m-1).
        # Wait, if R[k+1] exists, it's the largest index for i_{k+1}. 
        # If we pick some p for i_k, we need to be able to pick i_{k+1} > p.
        # This is possible if and only if there is an occurrence of word2[k+1] at some 
        # index q such that p < q <= R[k+1].
        # If no such q exists, then we can't pick this i_k.
        # But wait, the smallest possible q for word2[k+1] after p is what we want.
        # Let next_occ(char, start) be the first occurrence of char in word1 at index >= start.
        # We need: next_occ(word2[k+1], i_k + 1) <= R[k+1].
        
        # This is getting complicated. Let's use a simpler observation:
        # For a fixed k, we want the lexicographically smallest sequence.
        # i_0 = L[0]
        # ...
        # i_{k-1} = L[k-1]
        # i_k = smallest index > i_{k-1} such that there exists some p > i_k 
        #       where word2[k+1...m-1] is a zero-change subsequence of word1[p...n-1].
        # The condition "word2[k+1...m-1] is a zero-change subsequence of word1[p...n-1]" 
        # is equivalent to R[k+1] >= p.
        # So we need smallest i_k > i_{k-1} such that there exists some p > i_k 
        # with word2[k+1...m-1] being a zero-change subsequence of word1[p...n-1].
        # This is equivalent to: there exists some p > i_k such that R[k+1] >= p.
        # Which means R[k+1] must exist and R[k+1] > i_k.
        # Wait, if R[k+1] exists, then the smallest possible p is next_occ(word2[k+1], i_k + 1).
        # We need next_occ(word2[k+1], i_k + 1) <= R[k+1].
        # If k = m-1, we just need i_k > i_{k-1}. Smallest such is i_{k-1} + 1.
        
        # Let's refine:
        # For a fixed k:
        # 1. Check if L[0...k-1] are strictly increasing and < n. If not, k is invalid.
        # 2. Find smallest i_k > i_{k-1} (or i_k >= 0 if k=0) such that:
        #    a. If k < m-1: R[k+1] exists and there is an occurrence of word2[k+1] 
        #       at some index q > i_k such that q <= R[k+1].
        #       Actually, the smallest such q is next_occ(word2[k+1], i_k + 1).
        #       So we need next_occ(word2[k+1], i_k + 1) <= R[k+1].
        #    b. If k = m-1: any i_k > i_{k-1} (or i_k >= 0). Smallest is i_{k-1}+1 or 0.
        
        # To do this efficiently, we need next_occ for each character.
        pass

    # Let's use a different approach:
    # For each k \in [0, m-1]:
    #   The sequence is i_0, ..., i_{m-1}.
    #   i_j = L[j] for j < k.
    #   i_k = smallest index > i_{k-1} such that there exists a zero-change 
    #        subsequence of word2[k+1...m-1] in word1[i_k+1...n-1].
    #   For j > k, i_j is the smallest index > i_{j-1} such that word1[i_j] == word2[j].

    # Precompute next_occ[char][idx] = first occurrence of char in word1 at index >= idx.
    next_occ = [[float('inf')] * (n + 1) for _ in range(26)]
    for c_idx in range(26):
        char = chr(ord('a') + c_idx)
        last = float('inf')
        for i in range(n - 1, -1, -1):
            if word1[i] == char:
                last = i
            next_occ[c_idx][i] = last

    # Precompute R[j]: largest index i_j such that word2[j...m-1] is a zero-change 
    #                  subsequence of word1[i_j...n-1].
    R = [float('inf')] * m
    curr = n - 1
    for j in range(m - 1, -1, -1):
        while curr >= 0 and word1[curr] != word2[j]:
            curr -= 1
        if curr >= 0:
            R[j] = curr
            curr -= 1
        else:
            break

    best_seq = []
    for k in range(m):
        current_seq = []
        possible = True
        last_idx = -1
        
        # j < k
        for j in range(k):
            idx = L[j]
            if idx <= last_idx:
                possible = False
                break
            current_seq.append(idx)
            last_idx = idx
        
        if not possible: continue
        
        # i_k
        i_k = float('inf')
        if k == m - 1:
            i_k = last_idx + 1
            if i_k < n:
                current_seq.append(i_k)
            else:
                possible = False
        else:
            # Need smallest i_k > last_idx such that next_occ(word2[k+1], i_k + 1) <= R[k+1]
            # This is equivalent to finding smallest i_k > last_idx such that 
            # there exists some q > i_k with word1[q] == word2[k+1] and q <= R[k+1].
            # The smallest such q is next_occ(word2[k+1], last_idx + 1).
            # If this q exists and q <= R[k+1], then the smallest i_k is simply last_idx + 1.
            # Wait, no. i_k can be any index > last_idx as long as there's room for word2[k+1...m-1].
            # The condition "there exists a zero-change subsequence of word2[k+1...m-1] 
            # in word1[i_k+1...n-1]" is exactly R[k+1] > i_k.
            # So we need smallest i_k > last_idx such that R[k+1] > i_k.
            # This means i_k = last_idx + 1, provided last_idx + 1 < R[k+1].
            # But wait, if k < m-1, we also need to make sure word2[k+1...m-1] is a subsequence.
            # The condition for that is R[k+1] exists and R[k+1] > i_k.
            # Is there any other constraint on i_k? No, because we can change word1[i_k].
            # So i_k = last_idx + 1. We just need to check if R[k+1] > i_k.
            # Wait, what if k < m-1 and word2[k+1...m-1] is a subsequence of word1[i_k+1...n-1]?
            # That's exactly what R[k+1] > i_k means (if we define R[k+1] as the largest 
            # index for i_{k+1}).
            # Let's re-verify: if R[k+1] is the largest possible index for i_{k+1}, 
            # and we pick some i_k < R[k+1], can we always find a valid sequence?
            # Yes, because we can just greedily pick indices for word2[k+1...m-1] 
            # starting from the first occurrence of word2[k+1] after i_k.
            # The only requirement is that this greedy matching doesn't exceed R[k+1].
            # But if we pick the smallest possible indices, they will definitely be <= R[k+1].
            
            i_k = last_idx + 1
            if i_k < n and (k == m - 1 or R[k+1] > i_k):
                current_seq.append(i_k)
            else:
                possible = False
        
        if not possible: continue
        
        # j > k
        last_idx = current_seq[-1]
        for j in range(k + 1, m):
            idx = next_occ[ord(word2[j]) - ord('a')][last_idx + 1]
            if idx <= last_idx or idx >= n:
                possible = False
                break
            current_seq.append(idx)
            last_idx = idx
        
        if possible and len(current_seq) == m:
            if not best_seq or current_seq < best_seq:
                best_seq = current_seq

    return best_seq if best_seq else []
