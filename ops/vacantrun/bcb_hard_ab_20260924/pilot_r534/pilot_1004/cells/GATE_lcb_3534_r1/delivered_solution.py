from typing import List
from collections import Counter

def countPairs(nums: List[int]) -> int:
    def get_canonical_forms(n: int) -> set:
        s = str(n)
        # A number is "almost equal" to another if they have the same digits
        # OR if one can be transformed into the other by swapping two digits.
        # Actually, the rule says: choose either x or y and swap any two digits within it.
        # This means we need to check if there exists a permutation of digits of x 
        # that equals y, but only for permutations reachable by ONE swap.
        pass

    # Let's re-read carefully: "Choose either x or y and swap any two digits within the chosen number."
    # This means nums[i] and nums[j] are almost equal if:
    # 1. nums[i] == nums[j] (0 swaps)
    # 2. There exists a swap in nums[i] that makes it equal to nums[j].
    # 3. There exists a swap in nums[j] that makes it equal to nums[i].

    def can_transform(n1: int, n2: int) -> bool:
        s1 = str(n1)
        s2 = str(n2)
        if s1 == s2:
            return True
        if len(s1) != len(s2):
            # Wait, the problem says "Note that it is allowed for an integer to have leading zeros after performing an operation."
            # This implies that if we swap digits in 30 to get 03, it's considered equal to 3.
            # But wait, 3 and 30 are almost equal because swapping 3 and 0 in 30 gives 03 which is 3?
            # Let's check Example 1: 3 and 30. 30 -> swap(3,0) -> 03 = 3. Correct.
            # This means we should treat numbers as strings of digits, but the target might have fewer digits if leading zeros are produced?
            # No, "become equal" usually means numerical equality.
            pass

    # Let's re-evaluate:
    # nums[i] and nums[j] are almost equal if:
    # There exists a swap in s1 such that int(swapped_s1) == n2
    # OR there exists a swap in s2 such that int(swapped_s2) == n1

    def get_all_possible_values(n: int) -> set:
        s = str(n)
        results = {n}
        for i in range(len(s)):
            for j in range(i + 1, len(s)):
                if s[i] != s[j]:
                    # Swap digits at i and j
                    chars = list(s)
                    chars[i], chars[j] = chars[j], chars[i]
                    results.add(int("".join(chars)))
        return results

    count = 0
    n = len(nums)
    for i in range(n):
        possible_i = get_all_possible_values(nums[i])
        for j in range(i + 1, n):
            if nums[j] in possible_i or nums[i] in get_all_possible_values(nums[j]):
                count += 1
    return count

