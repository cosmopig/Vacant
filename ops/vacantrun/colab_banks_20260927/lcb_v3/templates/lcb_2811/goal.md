You are given two integers, n and k.
An array of distinct positive integers is called a k-avoiding array if there does not exist any pair of distinct elements that sum to k.
Return the minimum possible sum of a k-avoiding array of length n.
 
Example 1:

Input: n = 5, k = 4
Output: 18
Explanation: Consider the k-avoiding array [1,2,4,5,6], which has a sum of 18.
It can be proven that there is no k-avoiding array with a sum less than 18.

Example 2:

Input: n = 2, k = 6
Output: 3
Explanation: We can construct the array [1,2], which has a sum of 3.
It can be proven that there is no k-avoiding array with a sum less than 3.

 
Constraints:

1 <= n, k <= 50

請寫一個頂層 Python 函式（不要用 class）：
def minimumSum(n: int, k: int):
只能用標準函式庫。函式必須回傳答案，不要印出。