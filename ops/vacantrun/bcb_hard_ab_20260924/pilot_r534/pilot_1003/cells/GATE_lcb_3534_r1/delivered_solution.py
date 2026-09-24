from typing import List

def countPairs(nums: List[int]) -> int:
    count = 0
    n = len(nums)
    for i in range(n):
        for j in range(i + 1, n):
            x = nums[i]
            y = nums[j]
            if x == y:
                count += 1
                continue
            
            sx = list(str(x))
            sy = list(str(y))
            
            is_almost_equal = False
            
            # Try swapping digits in sx to get y
            if len(sx) >= 2:
                for k in range(len(sx)):
                    for l in range(k + 1, len(sx)):
                        sx[k], sx[l] = sx[l], sx[k]
                        if int("".join(sx)) == y:
                            is_almost_equal = True
                            break
                        sx[k], sx[l] = sx[l], sx[k] # swap back
                    if is_almost_equal:
                        break
            
            if is_almost_equal:
                count += 1
                continue
                
            # Try swapping digits in sy to get x
            if len(sy) >= 2:
                for k in range(len(sy)):
                    for l in range(k + 1, len(sy)):
                        sy[k], sy[l] = sy[l], sy[k]
                        if int("".join(sy)) == x:
                            is_almost_equal = True
                            break
                        sy[k], sy[l] = sy[l], sy[k] # swap back
                    if is_almost_equal:
                        break
            
            if is_almost_equal:
                count += 1
                
    return count
