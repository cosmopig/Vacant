You are given an integer array nums and a non-negative integer k. A sequence of integers seq is called good if there are at most k indices i in the range [0, seq.length - 2] such that seq[i] != seq[i + 1].
Return the maximum possible length of a good subsequence of nums.
 
Example 1:

Input: nums = [1,2,1,1,3], k = 2
Output: 4
Explanation:
The maximum length subsequence is [1,2,1,1,3].

Example 2:

Input: nums = [1,2,3,4,5,1], k = 0
Output: 2
Explanation:
The maximum length subsequence is [1,2,3,4,5,1].

 
Constraints:

1 <= nums.length <= 500
1 <= nums[i] <= 10^9
0 <= k <= min(nums.length, 25)

請寫一個頂層 Python 函式（不要用 class）：
def maximumLength(nums: List[int], k: int):
只能用標準函式庫。函式必須回傳答案，不要印出。