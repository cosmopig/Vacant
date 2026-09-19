def validSequence(word1: str, word2: str):
    n = len(word1)
    m = len(word2)

    # max_pos[j] is the largest index i such that word2[j...m-1] 
    # is a subsequence of word1[i...n-1].
    max_pos = [0] * (m + 1)
    max_pos[m] = n
    curr_p = n
    for j in range(m - 1, -1, -1):
        # Find the largest index i < curr_p such that word1[i] == word2[j]
        # Actually, we want to find the largest possible index for word2[j].
        # To maximize it, we should pick the latest occurrence of word2[j] 
        # before max_pos[j+1].
        # Wait, if we want the largest i such that word2[j...m-1] is a subsequence of word1[i...n-1],
        # then for j=m-1, it's the last occurrence of word2[m-1] in word1.
        # For j=m-2, it's the last occurrence of word2[m-2] before max_pos[m-1].
        pass

    # Let's re-think: 
    # To find the largest index i such that word2[j...m-1] is a subsequence of word1[i...n-1]:
    # For j = m-1, max_pos[m-1] = last occurrence of word2[m-1] in word1.
    # For j = m-2, max_pos[m-2] = last occurrence of word2[m-2] before max_pos[m-1].
    # This is correct.

    max_pos = [0] * (m + 1)
    max_pos[m] = n
    last_occ = {} # char -> list of indices
    for i, char in enumerate(word1):
        if char not in last_occ:
            last_occ[char] = []
        last_occ[char].append(i)

    import bisect

    curr_limit = n
    for j in range(m - 1, -1, -1):
        char = word2[j]
        if char not in last_occ:
            return []
        indices = last_occ[char]
        # Find largest index i < curr_limit
        idx = bisect.bisect_left(indices, curr_limit)
        if idx == 0:
            return []
        max_pos[j] = indices[idx - 1]
        curr_limit = max_pos[j]

    # Now we have max_pos[j].
    # can_match(j, i, budget) is true if word2[j:] can be matched with <= budget mismatches in word1[i:].
    # For budget == 0:
    #   can_match(j, i, 0) is true iff there exists p >= i s.t. word1[p] == word2[j] and max_pos[j+1] > p.
    #   This is equivalent to saying the smallest such p is < max_pos[j].
    #   Wait, if we pick the smallest such p, it's always better for lexicographical order.
    #   So can_match(j, i, 0) is true iff min_p_exact(j, i) < max_pos[j].
    #   Actually, max_pos[j] IS the largest possible index for word2[j] such that it's part of a valid subsequence.
    #   So can_match(j, i, 0) is true iff there exists p >= i s.t. word1[p] == word2[j] and max_pos[j+1] > p.

    # Let's precompute min_p_exact[j][i]? No, too much memory.
    # We can use next_occ[char][i].
    next_occ = [{} for _ in range(n + 1)]
    for i in range(n - 1, -1, -1):
        next_occ[i] = next_occ[i+1].copy()
        next_occ[i][word1[i]] = i

    def get_min_p_exact(j, start_idx):
        char = word2[j]
        if char not in next_occ[start_idx]:
            return float('inf')
        p = next_occ[start_idx][char]
        if p < max_pos[j+1]: # This is wrong. It should be p < some limit? 
            # Actually, the condition for word2[j:] to be a subsequence of word1[i:] 
            # with 0 mismatches is that the greedy smallest indices are all < n.
            # But we want them to be part of a valid sequence where only one mismatch is allowed.
            pass

    # Let's simplify:
    # A sequence seq = [i_0, ..., i_{m-1}] is valid if there exists k such that 
    # for all j != k, word1[i_j] == word2[j].
    # This means we can pick ONE index i_k to be anything.

    # Let's precompute:
    # L[j]: greedy smallest indices matching word2 exactly.
    L = [0] * m
    curr = 0
    for j in range(m):
        while curr < n and word1[curr] != word2[j]:
            curr += 1
        if curr == n:
            # If exact match fails, we still need to check if almost equal is possible.
            pass
        L[j] = curr
        curr += 1

    # This L[j] is only for the case where all characters match exactly.
    # Let's use the property:
    # The lexicographically smallest valid sequence is either:
    # 1. The greedy smallest seq matching word2 exactly (if it exists).
    # 2. For some k, the greedy smallest seq where position k is free.

    # To find the best for a fixed k:
    # i_0 = L[0] if k > 0 else 0
    # i_1 = L[1] if k > 1 and L[1] > i_0 else (first occurrence of word2[1] after i_0)
    # ... this is still O(m^2).

    # Let's use the fact that we want to minimize i_0.
    # The smallest possible i_0 is:
    # - L[0] (if k > 0)
    # - 0 (if k = 0)
    # If there are multiple k's that give the same i_0, we move to i_1, and so on.

    # Let's precompute:
    # `min_p_exact[j][i]` = smallest p >= i s.t. word1[p] == word2[j] and max_pos[j+1] > p.
    # This can be done in O(n) for each j by using next_occ.

    # Actually, we only need to know if it's possible to complete the sequence 
    # with <= 1 mismatch total.
    # Let `can_match(j, i, budget)`:
    # - if budget == 0: return there exists p >= i s.t. word1[p] == word2[j] and max_pos[j+1] > p.
    #   This is true iff min_p_exact(j, i) < max_pos[j]. (Wait, no, it's just `min_p_exact(j, i)` exists).
    # - if budget == 1: return there exists p >= i s.t. word1[p] == word2[j] and can_match(j+1, p+1, 0) OR
    #   there exists p >= i s.t. word1[p] != word2[j] and can_match(j+1, p+1, 0).

    # Let's use the `max_pos` array again.
    # max_pos[j] is the largest index such that word2[j...m-1] is a subsequence of word1[max_pos[j]...n-1].
    # This means for any j, if we pick an index i_j < max_pos[j], 
    # then there exists a sequence of indices i_{j+1}, ..., i_{m-1} such that 
    # word1[i_r] == word2[r] and they are all > i_{r-1}.

    # So, can_match(j, i, budget):
    # - if budget == 0: return there exists p >= i s.t. word1[p] == word2[j] and max_pos[j+1] > p.
    #   This is true iff min_p_exact(j, i) < max_pos[j]. (Wait, no, it's just `min_p_exact(j, i)` exists).
    #   Actually, if we pick the smallest such p, then word2[j+1...] must be a subsequence of word1[p+1:].
    #   This is true iff max_pos[j+1] > p.

    # Let's precompute `min_p_exact(j, i)` for all j and i? No, too much memory.
    # But we only need it for the current i. 
    # We can use next_occ to find min_p_exact(j, i) in O(1).

    # Now, let's define:
    # `min_p_exact(j, i)` = smallest p >= i s.t. word1[p] == word2[j] and max_pos[j+1] > p.
    # `min_p_any(j, i)` = smallest p >= i s.t. max_pos[j+1] > p.

    # These can be computed in O(1) using next_occ and the fact that max_pos is monotonic.
    # min_p_any(j, i) is just `i` if max_pos[j+1] > i else infinity.

    # Now we can use greedy:
    # For j = 0 to m-1:
    #   Try p = current_idx (or current_idx + 1).
    #   If word1[p] == word2[j]:
    #     If can_match(j+1, p+1, budget) is true, pick p.
    #   Else:
    #     If budget > 0 and can_match(j+1, p+1, 0) is true, pick p.
    #   If neither, we need to find the smallest p' > p s.t. word1[p'] == word2[j] and can_match(j+1, p'+1, budget).

    # This still requires finding the smallest p'. 
    # But for a fixed j and budget, there are only two types of p':
    # 1. p' > p s.t. word1[p'] == word2[j] and max_pos[j+1] > p' (for budget=0)
    # 2. p' > p s.t. word1[p'] == word2[j] and can_match(j+1, p'+1, 1) (for budget=1)

    # Let's simplify: at each position j, we want the smallest p >= current_idx such that:
    # (word1[p] == word2[j] AND can_match(j+1, p+1, budget)) OR 
    # (word1[p] != word2[j] AND budget > 0 AND can_match(j+1, p+1, 0))

    # Let's precompute `min_p_exact_with_budget(j, i, budget)`:
    # - if budget == 0: smallest p >= i s.t. word1[p] == word2[j] and max_pos[j+1] > p.
    # - if budget == 1: smallest p >= i s.t. word1[p] == word2[j] and can_match(j+1, p+1, 1).

    # This is still a bit complex. Let's just use the fact that we want to minimize p.
    # The smallest possible p is `current_idx`.
    # If it doesn't work, the next smallest is `next_occ[word2[j]][current_idx]`.
    # Or if budget > 0, it could be some other index.

    # Let's use a simpler greedy:
    # At each position j, we want to find the smallest p >= current_idx such that:
    # there exists k >= j where (j == k or word1[p] == word2[j]) and 
    # for all r > j, if r != k then word1[i_r] == word2[r].

    # This is equivalent to:
    # There exists k >= j such that:
    # - If k == j: p can be anything, and we need to match word2[j+1:] with 0 mismatches.
    #   This is possible if there exists some p' >= current_idx s.t. max_pos[j+1] > p'.
    #   The smallest such p' is `current_idx`. So we need max_pos[j+1] > current_idx.
    # - If k > j: word1[p] must be word2[j], and we need to match word2[j+1:] with <= 1 mismatch.
    #   This is possible if there exists p' >= current_idx s.t. word1[p'] == word2[j] and can_match(j+1, p'+1, 1).

    # So at each position j:
    # Option 1 (k = j): smallest p >= current_idx such that max_pos[j+1] > p.
    #   This is `current_idx` if max_pos[j+1] > current_idx else infinity.
    # Option 2 (k > j): smallest p >= current_idx s.t. word1[p] == word2[j] and can_match(j+1, p+1, 1).

    # We want min(Option 1, Option 2).
    # To make this O(m), we need to efficiently find Option 2.
    # Option 2 is the smallest p >= current_idx s.t. word1[p] == word2[j] and can_match(j+1, p+1, 1).

    # Let's precompute `can_match(j, i, 0)`:
    # It's true iff there exists p >= i s.t. word1[p] == word2[j] and max_pos[j+1] > p.
    # This is true iff min_p_exact(j, i) < max_pos[j]. (Wait, no, it's just `min_p_exact(j, i)` exists).

    # Let's use the fact that we only need to know if *any* k >= j works.
    # This is true iff:
    # 1. max_pos[j+1] > current_idx (k = j)
    # 2. There exists p >= current_idx s.t. word1[p] == word2[j] and can_match(j+1, p+1, 1).

    # To find the smallest such p for Option 2:
    # We can precompute `min_p_exact_with_budget_1(j, i)`? No.
    # But we only need to check if it's possible. If it is, what is the smallest p?
    # The smallest p for Option 2 is either:
    # - `next_occ[word2[j]][current_idx]` (if it satisfies can_match(j+1, p+1, 1))
    # - or some larger one.

    # Actually, we can just iterate p = next_occ[word2[j]][current_idx], next_occ[word2[j]][p+1], ...
    # until we find one that satisfies can_match(j+1, p+1, 1).
    # Since we want the lexicographically smallest seq, this is correct.
    # To keep it O(n), we can observe that if `next_occ[word2[j]][current_idx]` doesn't work, 
    # then no larger p will work? No, that's not true.

    # Let's use the fact that `can_match(j+1, p+1, 1)` is monotonic in p!
    # As p increases, `can_match(j+1, p+1, 1)` can only go from True to False.
    # So we want the smallest p >= current_idx s.t. word1[p] == word2[j] and p < some limit.
    # What is that limit? It's the largest p such that `can_match(j+1, p+1, 1)` is true.

    # Let `limit_one_mismatch[j]` be the largest p s.t. `can_match(j, p, 1)` is true.
    # This can be computed in O(n).
    # Then Option 2 is: smallest p >= current_idx s.t. word1[p] == word2[j] and p < limit_one_mismatch[j+1].

    # Let's precompute `limit_one_mismatch[j]` for all j:
    # `limit_one_mismatch[m] = n`
    # For j from m-1 down to 0:
    #   `limit_one_mismatch[j]` is the largest p s.t. (word2[j:] can be matched with <= 1 mismatch in word1[p:])
    #   This is true if:
    #   - word2[j:] can be matched exactly in word1[p:] (i.e., max_pos[j] > p)
    #   - OR there exists some k >= j s.t. word2[k+1:] can be matched exactly in word1[p':] and word2[j...k] are matched with 1 mismatch? No.

    # Let's simplify: `can_match(j, i, 1)` is true iff:
    # - there exists p >= i s.t. word1[p] == word2[j] and max_pos[j+1] > p (0 mismatches)
    # - OR there exists p >= i s.t. max_pos[j+1] > p (1 mismatch at position j)

    # So `limit_one_mismatch[j]` is the largest p such that:
    # 1. There exists q >= p s.t. word1[q] == word2[j] and max_pos[j+1] > q.
    #    This means p <= max_pos[j].
    # 2. There exists q >= p s.t. max_pos[j+1] > q.
    #    This means p < max_pos[j+1].

    # So `limit_one_mismatch[j]` = max(max_pos[j], max_pos[j+1] - 1).
    # Wait, this is it!
    # For a fixed j:
    # Option 1 (k=j): smallest p >= current_idx s.t. p < max_pos[j+1].
    #   This is `current_idx` if current_idx < max_pos[j+1] else infinity.
    # Option 2 (k>j): smallest p >= current_idx s.t. word1[p] == word2[j] and p < limit_one_mismatch[j+1].

    # Let's re-verify:
    # If k=j, we mismatch at position j. We need to match word2[j+1:] with 0 mismatches in word1[p+1:].
    # This is possible iff max_pos[j+1] > p.
    # So Option 1 is smallest p >= current_idx s.t. p < max_pos[j+1].

    # If k>j, we match at position j. We need to match word2[j:] with <= 1 mismatch in word1[p:].
    # This is possible iff p < limit_one_mismatch[j].
    # So Option 2 is smallest p >= current_idx s.t. word1[p] == word2[j] and p < limit_one_mismatch[j].

    # Wait, if k > j, we match at position j, so the mismatch must happen at some k > j.
    # This means we need to match word2[j:] with <= 1 mismatch in word1[p:].
    # The smallest such p is what we want.
    # But wait, if we pick a very small p for Option 2, it might not be the best because we want the lexicographically smallest seq.
    # Actually, picking the smallest p at each step IS the greedy way to get the lexicographically smallest seq.

    # Let's refine:
    # At each position j:
    #   p1 = current_idx if current_idx < max_pos[j+1] else infinity
    #   p2 = smallest p >= current_idx s.t. word1[p] == word2[j] and p < limit_one_mismatch[j]
    #   Wait, the condition for Option 2 is that we match at position j, so it's `limit_one_mismatch[j]`? No, it should be `limit_one_mismatch` of the *remaining* part.

    # Let's re-think:
    # At each position j, we want to pick smallest p >= current_idx such that there exists k >= j where:
    # - If k == j: word1[p] can be anything, and word2[j+1:] matches exactly in word1[p+1:].
    #   This is possible iff max_pos[j+1] > p.
    # - If k > j: word1[p] must be word2[j], and word2[j:] matches with <= 1 mismatch in word1[p:].
    #   This is possible iff p < limit_one_mismatch[j].

    # So at each position j, we want min(p1, p2) where:
    # p1 = current_idx if current_idx < max_pos[j+1] else infinity
    # p2 = smallest p >= current_idx s.t. word1[p] == word2[j] and p < limit_one_mismatch[j].

    # Wait, `limit_one_mismatch[j]` is the largest p such that word2[j:] matches with <= 1 mismatch in word1[p:].
    # This means if we pick p < limit_one_mismatch[j], then there exists some k >= j such that word2[j:] matches with <= 1 mismatch.

    # Let's precompute `limit_one_mismatch[j]`:
    # max_pos[j] = largest index i s.t. word2[j...m-1] is a subsequence of word1[i...n-1].
    # limit_one_mismatch[j] = max(max_pos[j], max_pos[j+1] - 1) if j < m-1 else max_pos[j].

    # Let's double check:
    # If p < max_pos[j], then word2[j:] matches exactly in word1[p:]. (0 mismatches)
    # If p < max_pos[j+1] - 1, then there exists some q = max_pos[j+1]-1 such that word1[q] != word2[j] and word2[j+1:] matches exactly in word1[q+1:]. (1 mismatch at position j)
    # Wait, if p < max_pos[j+1] - 1, we can pick q = max_pos[j+1]-1 as our mismatch.
    # But we need to make sure that the indices are sorted!
    # If we pick i_j = p and then i_{j+1} = q, we need p < q.
    # Since q = max_pos[j+1]-1 and p < max_pos[j+1]-1, this is satisfied.

    # So `limit_one_mismatch[j]` is indeed `max(max_pos[j], max_pos[j+1] - 1)`.
    # And the greedy choice at each position j:
    # p1 = current_idx if current_idx < max_pos[j+1] else infinity
    # p2 = smallest p >= current_idx s.t. word1[p] == word2[j] and p < limit_one_mismatch[j]

    # Let's write the code.
