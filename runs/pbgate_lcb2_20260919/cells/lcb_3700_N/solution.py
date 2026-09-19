from typing import List
from collections import Counter

def subsequencesWithMiddleMode(nums: List[int]) -> int:
    MOD = 10**9 + 7
    n = len(nums)
    # We need to find the number of subsequences (a, b, c, d, e) such that
    # c is a unique mode. This means count(c) > count(x) for all x != c in the subsequence.
    # Since size is 5:
    # If count(c) = 3, then other two elements must be different from each other and not equal to c.
    #   Wait, if count(c) = 3, others can be same? No, because then they would also have count 2 or something.
    #   If count(c) = 3, the other two elements x, y must satisfy:
    #   - x != c, y != c
    #   - if x == y, then count(x) = 2 < 3 (ok)
    #   - if x != y, then count(x) = 1, count(y) = 1 < 3 (ok)
    # If count(c) = 4, the other element x must satisfy:
    #   - x != c
    #   - count(x) = 1 < 4 (ok)
    # If count(c) = 5, all elements are c.
    #   - count(c) = 5 (ok)
    # If count(c) = 2, the other three elements x, y, z must satisfy:
    #   - x != c, y != c, z != c
    #   - all counts < 2. This means x, y, z must be distinct and none equal to c.
    # If count(c) = 1, impossible for size 5 (other elements would have count >= 1).

    # Let's re-evaluate:
    # A subsequence of size 5 has a unique mode 'c' if:
    # freq(c) > freq(x) for all x != c.
    # Possible frequencies for c in a sequence of size 5:
    # - freq(c) = 5: All elements are c. (1 way to choose values, but we need subsequences)
    #   Number of ways: C(count_in_nums[c], 5)
    # - freq(c) = 4: Four elements are c, one is x != c.
    #   Number of ways: C(count_in_nums[c], 4) * sum(count_in_nums[x] for x != c)
    # - freq(c) = 3: Three elements are c, two others are x, y.
    #   Case 1: x == y (and x != c). Number of ways: C(count_in_nums[c], 3) * sum(C(count_in_nums[x], 2) for x != c)
    #   Case 2: x != y (and x, y != c). Number of ways: C(count_in_nums[c], 3) * sum(count_in_nums[x] * count_in_nums[y] for x < y, x != c, y != c)
    #   Wait, the order in subsequence matters? No, "subsequences" usually means indices are strictly increasing.
    #   The problem says "find the number of subsequences". Usually this refers to index-based selection.
    #   Example 1: nums = [1,1,1,1,1,1], output 6. C(6, 5) = 6. Correct.
    #   So we are counting sets of indices {i1, i2, i3, i4, i5} with i1 < i2 < i3 < i4 < i5 such that the values v[i1], ..., v[i5] satisfy the condition.
    #   The middle element is v[i3]. So c = v[i3].

    # Let's refine:
    # We need to count indices (i1, i2, i3, i4, i5) such that 0 <= i1 < i2 < i3 < i4 < i5 < n
    # and the value c = nums[i3] is a unique mode of {nums[i1], nums[i2], nums[i3], nums[i4], nums[i5]}.

    # Let's iterate over all possible middle indices i3.
    # For a fixed i3, let c = nums[i3].
    # We need to choose 2 indices from {0, ..., i3-1} and 2 indices from {i3+1, ..., n-1}.
    # Let the chosen values be {v1, v2, c, v4, v5}.
    # Condition: count(c) > count(x) for all x != c in {v1, v2, c, v4, v5}.

    # This is still a bit complex because the counts depend on how many times each value appears.
    # Since we only have 5 elements, the possible distributions of frequencies are:
    # 1. All same: (5) -> count(c)=5. Condition: 5 > 0 (True).
    # 2. Four same, one different: (4, 1) -> count(c)=4, count(x)=1. Condition: 4 > 1 (True).
    # 3. Three same, two same: (3, 2) -> count(c)=3, count(x)=2. Condition: 3 > 2 (True).
    # 4. Three same, two different: (3, 1, 1) -> count(c)=3, count(x)=1, count(y)=1. Condition: 3 > 1 (True).
    # 5. Two same, two same, one different: (2, 2, 1) -> count(c)=2, count(x)=2, count(y)=1. Condition: 2 > 2 (False).
    # 6. Two same, three different: (2, 1, 1, 1) -> count(c)=2, count(x)=1, count(y)=1, count(z)=1. Condition: 2 > 1 (True).
    # 7. All different: (1, 1, 1, 1, 1) -> count(c)=1, ... Condition: 1 > 1 (False).

    # So for a fixed i3 and c = nums[i3], we need to choose {v1, v2} from left and {v4, v5} from right
    # such that the resulting multiset of values {v1, v2, c, v4, v5} satisfies one of:
    # - All 5 are c.
    # - 4 are c, 1 is x != c.
    # - 3 are c, 2 are x (x != c).
    # - 3 are c, 1 is x, 1 is y (x, y != c and x != y).
    # - 2 are c, 1 is x, 1 is y, 1 is z (x, y, z != c and distinct).

    # Let L be the multiset of values in nums[0...i3-1]
    # Let R be the multiset of values in nums[i3+1...n-1]
    # We need to pick 2 from L and 2 from R.
    # This is still hard because we need to know how many c's are in L and R.

    # Let countL = number of times c appears in nums[0...i3-1]
    # Let countR = number of times c appears in nums[i3+1...n-1]
    # Let othersL = total elements in nums[0...i3-1] - countL
    # Let othersR = total elements in nums[i3+1...n-1] - countR

    # Total ways to pick 2 from L and 2 from R is C(i3, 2) * C(n-1-i3, 2).
    # We can subtract the "bad" cases or just sum the "good" ones.
    # Good cases for a fixed i3 (c = nums[i3]):
    # Let kL be number of c's picked from L (0 <= kL <= 2)
    # Let kR be number of c's picked from R (0 <= kR <= 2)
    # Total count of c is K = kL + kR + 1.
    # Number of other elements is 5 - K.
    # These 5-K elements must have frequencies < K.

    # Possible values for K:
    # K=5: (kL=2, kR=2). All others are c.
    #   Ways: C(countL, 2) * C(countR, 2)
    # K=4: (kL+kR = 3). One other element x != c.
    #   - kL=1, kR=2: C(countL, 1) * C(othersL, 1) * C(countR, 2)  -- wait, othersL is not correct because we need to pick one from L that is NOT c.
    #     Actually, if we pick kL elements from L and they are all c, then the other (2-kL) must be non-c.
    #   Let's re-think:
    #   For a fixed i3 and c = nums[i3]:
    #   We choose kL in [0, 2] from L that are equal to c.
    #   We choose (2-kL) from L that are NOT equal to c.
    #   We choose kR in [0, 2] from R that are equal to c.
    #   We choose (2-kR) from R that are NOT equal to c.
    #   Total count of c is K = kL + kR + 1.
    #   Number of non-c elements is M = (2-kL) + (2-kR).
    #   Condition: all non-c elements must have frequency < K.

    # Since M can be at most 4, and we only care if freq < K:
    # If K=5: M=0. Always true.
    # If K=4: M=1. The one non-c element has freq 1. 1 < 4 is always true.
    # If K=3: M=2. The two non-c elements can be same (freq 2) or different (freq 1, 1).
    #   Both are < 3. So always true!
    # If K=2: M=3. The three non-c elements must have freq < 2.
    #   This means they must all be distinct and none equal to c.
    # If K=1: M=4. Impossible (freq of some non-c would be >= 2, or if all 4 are distinct, then count(c)=1 is not unique mode).
    #   Wait, if K=1, we need freq < 1 for all others, which is impossible as there are 4 other elements.

    # So the condition "unique middle mode c" is equivalent to:
    # K = kL + kR + 1 >= 3  AND (if K=2 then M=3 and they are distinct)
    # Wait, let's re-check K=2:
    # If K=2, we have two c's and three non-c's. For c to be unique mode, all non-c's must have freq < 2.
    # This means the three non-c's must be distinct.
    # If K=3, we have three c's and two non-c's. They can be same or different (freq 2 or 1+1). Both are < 3.
    # If K=4, we have four c's and one non-c. Freq 1 < 4.
    # If K=5, we have five c's.

    # Summary for fixed i3 (c = nums[i3]):
    # Ways = Sum over kL in [0,2], kR in [0,2]:
    #   Ways(kL, kR) = C(countL, kL) * C(othersL, 2-kL) * C(countR, kR) * C(othersR, 2-kR)
    #   where K = kL + kR + 1.
    #   Condition:
    #   - If K >= 3: Always good.
    #   - If K == 2: Good only if the (2-kL) elements from L and (2-kR) elements from R are all distinct and none equal to c.
    #     Wait, "none equal to c" is already handled by using `othersL` and `othersR`.
    #     The condition is: the set of (2-kL) elements from L and (2-kR) elements from R must have all distinct values.

    # Let's simplify:
    # Total ways = Sum_{kL, kR} C(countL, kL) * C(othersL, 2-kL) * C(countR, kR) * C(othersR, 2-kR)
    # such that K >= 3.
    # Plus the cases where K=2 and the (2-kL) + (2-kR) = 3 elements are distinct.

    # Let's refine the K=2 case:
    # K=2 means kL+kR = 1.
    # Case A: kL=1, kR=0. We pick one c from L, zero c from R.
    #   We need to pick (2-1)=1 element from othersL and (2-0)=2 elements from othersR such that the 3 elements are distinct.
    # Case B: kL=0, kR=1. We pick zero c from L, one c from R.
    #   We need to pick (2-0)=2 elements from othersL and (2-1)=1 element from othersR such that the 3 elements are distinct.

    # This is getting complicated because "distinct" depends on the actual values in `othersL` and `othersR`.
    # However, we only need to know how many ways to pick them such that they are distinct.
    # Let S_L be the set of values in L \ {c}, and S_R be the set of values in R \ {c}.
    # We want to pick 1 from S_L and 2 from S_R such that all 3 are distinct.
    # Or 2 from S_L and 1 from S_R such that all 3 are distinct.

    # Let's reconsider the constraints: n <= 1000.
    # We can afford O(n^2) or even slightly more.
    # For each i3, we can pre-calculate countL, countR, othersL, othersR in O(1) after O(n) preprocessing.
    # But the "distinct" part is still tricky.

    # Wait! If K=2, and we need 3 distinct elements from S_L and S_R:
    # Let nL = number of unique values in L \ {c}
    # Let nR = number of unique values in R \ {c}
    # This is still not enough because we need to know the counts of each value.

    # Actually, if K=2, and we pick 3 elements from S_L and S_R:
    # Total ways to pick 3 elements (with replacement of values but distinct indices) is C(othersL, m1) * C(othersR, m2).
    # We want the number of such selections where all chosen values are distinct.

    # Let's re-read: "unique middle mode".
    # Example 2: nums = [1,2,2,3,3,4]
    # Subsequences of size 5:
    # [1, 2, 2, 3, 4] -> c=2. Freqs: {1:1, 2:2, 3:1, 4:1}. Mode is 2 (freq 2). Unique? Yes.
    # [1, 2, 3, 3, 4] -> c=3. Freqs: {1:1, 2:1, 3:2, 4:1}. Mode is 3 (freq 2). Unique? Yes.
    # [1, 2, 2, 3, 3] -> c=2. Freqs: {1:1, 2:2, 3:2}. Modes are 2 and 3. Unique? No.

    # In Example 2, for [1, 2, 2, 3, 3], the middle element is 2.
    # The values are {1, 2, 2, 3, 3}. Frequencies: 1:1, 2:2, 3:2.
    # Mode is not unique because both 2 and 3 appear twice.

    # So my K=2 analysis was correct: if K=2, all other elements must have freq < 2.
    # Since there are 5-K = 3 other elements, they must all be distinct.

    # Let's simplify the problem by noticing that for a fixed i3 and c = nums[i3]:
    # We want to count (v1, v2) from L and (v4, v5) from R such that:
    # 1. K = count(c in {v1, v2, c, v4, v5}) >= 3
    # 2. OR K = 2 and all other values are distinct.

    # Let's use the property that n is small (1000).
    # For each i3:
    # countL = number of times nums[i3] appears in nums[:i3]
    # countR = number of times nums[i3] appears in nums[i3+1:]
    # othersL = i3 - countL
    # othersR = (n - 1 - i3) - countR

    # Ways for K >= 3:
    # Sum over kL, kR such that kL + kR + 1 >= 3:
    #   C(countL, kL) * C(othersL, 2-kL) * C(countR, kR) * C(othersR, 2-kR)

    # Ways for K = 2 and distinct others:
    # This happens if (kL+kR = 1).
    # Case 1: kL=1, kR=0. We need to pick 1 from othersL and 2 from othersR such that they are all distinct.
    #   Let S_L be the set of values in L \ {c}, S_R be the set of values in R \ {c}.
    #   We want to pick x from S_L and y, z from S_R such that x, y, z are distinct and x != c, y != c, z != c.
    # Case 2: kL=0, kR=1. We need to pick 2 from othersL and 1 from othersR such that they are all distinct.

    # To do this efficiently for each i3:
    # For a fixed c = nums[i3]:
    # Let L_vals = Counter(nums[:i3])
    # Let R_vals = Counter(nums[i3+1:])
    # countL = L_vals[c]
    # countR = R_vals[c]
    # othersL = sum(v for v in L_vals if v != c)  -- wait, this is not right. 
    # othersL is the number of elements in nums[:i3] that are not equal to c.
    # Let unique_L = set of values in nums[:i3] \ {c}
    # Let unique_R = set of values in nums[i3+1:] \ {c}

    # Actually, for K=2 and distinct others:
    # If kL=1, kR=0: we need x from S_L (size 1) and y, z from S_R (size 2) such that x,y,z are distinct.
    #   Number of ways = sum_{x in unique_L} [ C(othersR, 2) - (number of pairs {y,z} in othersR such that y=x or z=x or y=z) ]
    #   This is still a bit complex.

    # Let's re-think: for K=2 and distinct others, we need to pick 3 indices from L \ {c} and R \ {c} such that the values are distinct.
    # This is equivalent to picking 3 distinct values from (unique_L union unique_R)
    # but with some constraints on how many come from L and how many from R.

    # Wait, if n=1000, we can just iterate over all i3.
    # For each i3, we can compute countL, countR, othersL, othersR in O(1) after O(n) preprocessing.
    # To handle the "distinct" part for K=2:
    # We need to pick 3 indices from L \ {c} and R \ {c} such that their values are distinct.
    # Let mL = number of elements in L \ {c}, mR = number of elements in R \ {c}.
    # Total ways to pick 3 indices is C(mL, m1) * C(mR, m2) where m1+m2=3.
    # We want the number of such selections where all values are distinct.

    # Let's use inclusion-exclusion or just count:
    # Number of ways to pick 3 indices from L \ {c} and R \ {c} with distinct values:
    # = (Total ways to pick 3 indices) - (ways where at least two have same value).

    # This is still hard. Let's simplify.
    # Is there a simpler way?
    # What if we iterate over all possible sets of frequencies?
    # For size 5, the only distributions that work are:
    # - (5) : c appears 5 times.
    # - (4, 1) : c appears 4 times, x appears 1 time.
    # - (3, 2) : c appears 3 times, x appears 2 times.
    # - (3, 1, 1) : c appears 3 times, x appears 1 time, y appears 1 time.
    # - (2, 1, 1, 1) : c appears 2 times, x appears 1 time, y appears 1 time, z appears 1 time.

    # Let's count these directly for each i3:
    # For a fixed i3 and c = nums[i3]:
    # 1. (5): All 5 are c.
    #   Ways = C(countL, 2) * C(countR, 2)
    # 2. (4, 1): 4 are c, 1 is x != c.
    #   - kL=2, kR=1: C(countL, 2) * C(countR, 1) * othersR  -- wait, othersR is total non-c in R.
    #     Actually, if we pick one from othersR, it's just `othersR`.
    #   - kL=1, kR=2: C(countL, 1) * C(countR, 2) * othersL
    #   - kL=2, kR=0: C(countL, 2) * C(countR, 0) * (othersL + othersR) -- wait, this is not right.
    #     If we pick one from L and it's not c, then the other must be c? No.
    #   Let's use kL, kR as number of c's picked from L and R.
    #   K = kL + kR + 1.
    #   If K=4: we need to pick one more element x != c.
    #   This x can come from L (if we picked only 1 c from L) or from R (if we picked only 1 c from R).
    #   Wait, if kL=2 and kR=1, then K=4. We need to pick one more element from othersR.
    #   If kL=1 and kR=2, then K=4. We need to pick one more element from othersL.
    #   If kL=2 and kR=0, then K=3... no, K = 2+0+1 = 3.

    # Let's use the kL, kR approach again:
    # For a fixed i3 and c = nums[i3]:
    # Total ways = 0
    # for kL in [0, 2]:
    #   for kR in [0, 2]:
    #     K = kL + kR + 1
    #     m_left = 2 - kL
    #     m_right = 2 - kR
    #     ways = C(countL, kL) * C(othersL, m_left) * C(countR, kR) * C(othersR, m_right)
    #     if K >= 3:
    #       total += ways
    #     elif K == 2:
    #       # Need to pick m_left + m_right = 3 elements from othersL and othersR such that they are all distinct.
    #       # This is only possible if we have enough unique values.
    #       # Since we need to do this for each i3, let's see if we can simplify.
    #       # m_left + m_right = 3 means (m_left=1, m_right=2) or (m_left=2, m_right=1).
    #       # Case kL=1, kR=0: pick 1 from othersL, 2 from othersR such that all 3 are distinct.
    #       # Case kL=0, kR=1: pick 2 from othersL, 1 from othersR such that all 3 are distinct.

    # Let's pre-calculate for each i3 and c = nums[i3]:
    # countL, countR, othersL, othersR
    # And also the set of values in L \ {c} and R \ {c}.
    # Actually, we only need to know how many ways to pick 1 from S_L and 2 from S_R such that they are distinct.
    # Let S_L be the multiset of values in L \ {c}, S_R be the multiset of values in R \ {c}.
    # Number of ways to pick x from S_L, y, z from S_R (distinct):
    # = sum_{x in unique(S_L)} [ C(othersR, 2) - (number of pairs {y,z} in S_R such that y=x or z=x or y=z) ]

    # This is still a bit much. Let's see if there's an even simpler way.
    # What if we just iterate over all possible values of x and y? No, too many.
    # But wait, n=1000. For each i3, we can afford O(n) to compute these things.
    # Total complexity O(n^2).

    # Let's refine the K=2 case:
    # We need to pick 3 elements from S_L and S_R such that they are distinct.
    # Let m1 = number of elements picked from S_L, m2 = number of elements picked from S_R. (m1+m2=3)
    # If m1=1, m2=2:
    #   Ways = sum_{x in unique(S_L)} [ C(othersR, 2) - (count of x in S_R) * (othersR - count of x in S_R) - C(count of x in S_R, 2) ]
    #   Wait, if we pick y, z from S_R:
    #   - they are same: C(count(v), 2) for each v in unique(S_R)
    #   - they are different and one is x: count(x in S_R) * (othersR - count(x in S_R))
    #   - they are different and neither is x: C(othersR, 2) - count(x in S_R)*(othersR - count(x in S_R)) - C(count(x in S_R), 2)
    # This is getting very complicated. Is there a simpler way to think about "distinct"?

    # Let's re-read: "unique middle mode".
    # If K=2, we have two c's and three other elements x, y, z.
    # For c to be the unique mode, all other elements must have frequency < 2.
    # This means x, y, z must be distinct and none of them can be c.
    # So we need to pick 3 indices from L \ {c} and R \ {c} such that their values are distinct.

    # Let's use the fact that there are only a few ways to pick 3 elements:
    # - All 3 from S_L (m1=3, m2=0) -> Not possible since we only have 2 slots in L and R.
    #   Wait, kL+kR = 1 means one of {kL, kR} is 1 and the other is 0.
    #   If kL=1, then m_left = 2-1 = 1. If kR=0, then m_right = 2-0 = 2.
    #   So we pick 1 from S_L and 2 from S_R.
    #   If kL=0, then m_left = 2-0 = 2. If kR=1, then m_right = 2-1 = 1.
    #   So we pick 2 from S_L and 1 from S_R.

    # In both cases, we need to pick 3 elements total (m1+m2=3) such that they are all distinct.
    # Let's say we want to pick m1 from S_L and m2 from S_R such that all m1+m2 elements are distinct.
    # This is equivalent to:
    # Sum over all sets of 3 distinct values {v1, v2, v3} from (unique(S_L) union unique(S_R)):
    #   Number of ways to pick these 3 values such that m1 come from S_L and m2 come from S_R.

    # This is still a bit much. Let's try another way.
    # For a fixed i3 and c = nums[i3]:
    # Let countL = number of times c appears in L
    # Let countR = number of times c appears in R
    # Let othersL = total elements in L - countL
    # Let othersR = total elements in R - countR
    # Total ways to pick 2 from L and 2 from R is C(i3, 2) * C(n-1-i3, 2).
    # We want to subtract the "bad" cases.
    # A case is bad if:
    # 1. K < 3 (i.e., K=1 or K=2)
    # 2. OR K=2 and some other elements are not distinct.

    # Let's simplify:
    # For a fixed i3, c = nums[i3]:
    # Total ways to pick 2 from L and 2 from R is C(i3, 2) * C(n-1-i3, 2).
    # A selection of 5 elements {v1, v2, c, v4, v5} is GOOD if:
    # - count(c) >= 3
    # - OR (count(c) == 2 and all other 3 elements are distinct)

    # Let's use the kL, kR approach again. It's much cleaner.
    # For a fixed i3 and c = nums[i3]:
    # total_good = 0
    # for kL in [0, 1, 2]:
    #   for kR in [0, 1, 2]:
    #     K = kL + kR + 1
    #     m_left = 2 - kL
    #     m_right = 2 - kR
    #     if K >= 3:
    #       total_good += C(countL, kL) * C(othersL, m_left) * C(countR, kR) * C(othersR, m_right)
    #     elif K == 2:
    #       # Need to pick m_left + m_right = 3 elements from othersL and othersR such that they are all distinct.
    #       # This is only possible if (m_left=1, m_right=2) or (m_left=2, m_right=1).
    #       if m_left == 1 and m_right == 2:
    #         # Pick x from S_L, {y, z} from S_R such that x, y, z are distinct.
    #         # Ways = sum_{x in unique(S_L)} [ C(othersR, 2) - (count of x in S_R)*(othersR - count of x in S_R) - C(count of x in S_R, 2) ]
    #       elif m_left == 2 and m_right == 1:
    #         # Pick {x, y} from S_L, z from S_R such that x, y, z are distinct.
    #         # Ways = sum_{z in unique(S_R)} [ C(othersL, 2) - (count of z in S_L)*(othersL - count of z in S_L) - C(count of z in S_L, 2) ]

    # To make this O(n^2), for each i3 we need to compute these sums quickly.
    # For a fixed c = nums[i3]:
    # Let L_vals = Counter(nums[:i3])
    # Let R_vals = Counter(nums[i3+1:])
    # countL = L_vals[c]
    # countR = R_vals[c]
    # othersL = sum(v for v in L_vals if v != c) -- No, this is wrong. 
    # othersL = i3 - countL
    # othersR = (n-1-i3) - countR

    # Let's pre-calculate the Counters for all prefixes and suffixes?
    # That would be O(n^2).
    # For each i, prefix_counts[i] = Counter of nums[:i]
    # Then for each i3:
    #   L_vals = prefix_counts[i3]
    #   R_vals = suffix_counts[i3+1]
    # This is O(n^2) space and time. n=1000, so 10^6 entries in Counter might be okay.

    # Wait, we can just iterate i3 from 0 to n-1:
    #   L_vals = Counter()
    #   for i3 in range(n):
    #     R_vals = Counter(nums[i3+1:]) # This is O(n) inside the loop -> O(n^2) total.
    #     ...
    #     L_vals[nums[i3]] += 1

    # Let's refine the K=2 sums:
    # For a fixed c = nums[i3]:
    # S_L = {v for v in L_vals if v != c}
    # S_R = {v for v in R_vals if v != c}
    # othersL = sum(count for v, count in L_vals.items() if v != c)
    # othersR = sum(count for v, count in R_vals.items() if v != c)

    # Sum1 (m_left=1, m_right=2):
    #   sum_{x in unique(S_L)} [ C(othersR, 2) - (R_vals[x] * (othersR - R_vals[x])) - C(R_vals[x], 2) ]
    #   = sum_{x in unique(S_L)} [ othersR*(othersR-1)/2 - R_vals[x]*(othersR - R_vals[x]) - R_vals[x]*(R_vals[x]-1)/2 ]
    #   = sum_{x in unique(S_L)} [ (othersR^2 - othersR)/2 - (R_vals[x]*othersR - R_vals[x]^2) - (R_vals[x]^2 - R_vals[x])/2 ]
    #   = sum_{x in unique(S_L)} [ (othersR^2 - othersR - 2*R_vals[x]*othersR + 2*R_vals[x]^2 - R_vals[x]^2 + R_vals[x])/2 ]
    #   = sum_{x in unique(S_L)} [ (othersR^2 - othersR - 2*R_vals[x]*othersR + R_vals[x]^2 + R_vals[x])/2 ]

    # This can be computed in O(unique(S_L)) which is O(n).
    # Total complexity O(n^2).

    # Let's double check the K=2 sum:
    # We want to pick x from S_L and {y, z} from S_R such that x, y, z are distinct.
    # The number of ways to pick {y, z} from S_R is C(othersR, 2).
    # From these, we subtract:
    # - pairs where y=z (same value): sum_{v in unique(S_R)} C(count(v), 2)
    # - pairs where y=x or z=x (one is x): count(x in S_R) * (othersR - count(x in S_R))
    # Wait, if we subtract both, we might be subtracting the case y=z=x twice.
    # If y=z=x, it's counted in both "y=z" and "y=x or z=x".
    # So we should add it back? No, because we want to exclude any pair where y=z OR (y=x or z=x).
    # The set of bad pairs is {pairs with same value} UNION {pairs with at least one x}.
    # |A U B| = |A| + |B| - |A \cap B|.
    # A = {pairs with same value}, B = {pairs with at least one x}.
    # A \cap B = {pair where y=z=x}.
    # So ways = C(othersR, 2) - [ sum_{v in unique(S_R)} C(count(v), 2) + count(x in S_R)*(othersR - count(x in S_R)) - C(count(x in S_R), 2) ]
    #   = C(othersR, 2) - sum_{v in unique(S_R)} C(count(v), 2) - count(x in S_R)*(othersR - count(x in S_R)) + C(count(x in S_R), 2)

    # Let's re-verify:
    # Total pairs from othersR = C(othersR, 2).
    # Bad pairs are those where y=z OR (y=x or z=x).
    # Pairs with same value: sum_{v in unique(S_R)} C(count(v), 2)
    # Pairs with at least one x: count(x in S_R) * (othersR - count(x in S_R)) + C(count(x in S_R), 2)
    # The intersection is the pair where y=z=x, which is C(count(x in S_R), 2).
    # So bad pairs = sum_{v in unique(S_R)} C(count(v), 2) + count(x in S_R)*(othersR - count(x in S_R))
    # Wait, if y=z=x, it's counted in the first sum (as v=x) and also in the second part.
    # Let's re-calculate:
    # Bad pairs = {pairs with same value} \cup {pairs where at least one is x}.
    # |Bad| = |{y=z}| + |{y=x or z=x}| - |{y=z and (y=x or z=x)}|
    # |{y=z}| = sum_{v in unique(S_R)} C(count(v), 2)
    # |{y=x or z=x}| = count(x in S_R)*(othersR - count(x in S_R)) + C(count(x in S_R), 2)
    # {y=z and (y=x or z=x)} is the case y=z=x, which has C(count(x in S_R), 2) ways.
    # So |Bad| = sum_{v in unique(S_R)} C(count(v), 2) + count(x in S_R)*(othersR - count(x in S_R))
    # This looks correct!

    # Let's re-check:
    # If othersR = {1, 1, 2, 3} and x=1.
    # C(4, 2) = 6 pairs: {(1,1), (1,2), (1,3), (1,2), (1,3), (2,3)}
    # Bad pairs: y=z is (1,1). |{y=z}| = 1.
    # At least one x=1: (1,1), (1,2), (1,3), (1,2), (1,3). |{at least one x}| = 5.
    # Intersection y=z=x=1: (1,1). |{y=z=x}| = 1.
    # |Bad| = 1 + 5 - 1 = 5.
    # Good pairs: 6 - 5 = 1. The only good pair is (2,3). Correct!

    # So for K=2 and m_left=1, m_right=2:
    # Ways = sum_{x in unique(S_L)} [ C(othersR, 2) - sum_{v in unique(S_R)} C(count(v), 2) - count(x in S_R)*(othersR - count(x in S_R)) ]

    # And for K=2 and m_left=2, m_right=1:
    # Ways = sum_{z in unique(S_R)} [ C(othersL, 2) - sum_{v in unique(S_L)} C(count(v), 2) - count(z in S_L)*(othersL - count(z in S_L)) ]

    # This is O(n^2). Let's implement it.
