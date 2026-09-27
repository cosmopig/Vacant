from typing import List

def countPairs(nums: List[int]) -> int:
    v_sets = []
    for n in nums:
        s = str(n)
        v_set = {n}
        if len(s) > 1:
            chars = list(s)
            for i in range(len(chars)):
                for j in range(i + 1, len(chars)):
                    # swap chars[i] and chars[j]
                    chars[i], chars[j] = chars[j], chars[i]
                    v_set.add(int("".join(chars)))
                    # swap back to original for next iteration
                    chars[i], chars[j] = chars[j], chars[i]
        v_sets.append(v_set)
    
    count = 0
    for i in range(len(nums)):
        for j in range(i + 1, len(nums)):
            if nums[i] in v_sets[j] or nums[j] in v_sets[i]:
                count += 1
    return count
