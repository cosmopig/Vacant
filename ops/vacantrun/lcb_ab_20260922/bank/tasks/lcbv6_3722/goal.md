# sum-of-k-subarrays-with-length-at-least-m

You are given an integer array nums and two integers, k and m.
Return the maximum sum of k non-overlapping subarrays of nums, where each subarray has a length of at least m.
 
Example 1:

Input: nums = [1,2,-1,3,3,4], k = 2, m = 2
Output: 13
Explanation:
The optimal choice is:

Subarray nums[3..5] with sum 3 + 3 + 4 = 10 (length is 3 >= m).
Subarray nums[0..1] with sum 1 + 2 = 3 (length is 2 >= m).

The total sum is 10 + 3 = 13.

Example 2:

Input: nums = [-10,3,-1,-2], k = 4, m = 1
Output: -10
Explanation:
The optimal choice is choosing each element as a subarray. The output is (-10) + 3 + (-1) + (-2) = -10.

 
Constraints:

1 <= nums.length <= 2000
-10^4 <= nums[i] <= 10^4
1 <= k <= floor(nums.length / m)
1 <= m <= 3

---

請寫一個**頂層** Python 函式（不要用 class）：

```python
def maxSum(...):
    ...
```

只能用標準函式庫。函式必須**回傳**答案，不要印出。
