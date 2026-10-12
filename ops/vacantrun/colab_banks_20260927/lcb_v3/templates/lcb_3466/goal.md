Given an array of integers nums and an integer k, return the number of subarrays of nums where the bitwise AND of the elements of the subarray equals k.
 
Example 1:

Input: nums = [1,1,1], k = 1
Output: 6
Explanation:
All subarrays contain only 1's.

Example 2:

Input: nums = [1,1,2], k = 1
Output: 3
Explanation:
Subarrays having an AND value of 1 are: [1,1,2], [1,1,2], [1,1,2].

Example 3:

Input: nums = [1,2,3], k = 2
Output: 2
Explanation:
Subarrays having an AND value of 2 are: [1,2,3], [1,2,3].

 
Constraints:

1 <= nums.length <= 10^5
0 <= nums[i], k <= 10^9

請寫一個頂層 Python 函式（不要用 class）：
def countSubarrays(nums: List[int], k: int):
只能用標準函式庫。函式必須回傳答案，不要印出。