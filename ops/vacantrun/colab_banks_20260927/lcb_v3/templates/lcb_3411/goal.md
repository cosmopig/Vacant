A powerful array for an integer x is the shortest sorted array of powers of two that sum up to x. For example, the powerful array for 11 is [1, 2, 8].
The array big_nums is created by concatenating the powerful arrays for every positive integer i in ascending order: 1, 2, 3, and so forth. Thus, big_nums starts as [1, 2, 1, 2, 4, 1, 4, 2, 4, 1, 2, 4, 8, ...].
You are given a 2D integer matrix queries, where for queries[i] = [from_i, to_i, mod_i] you should calculate (big_nums[from_i] * big_nums[from_i + 1] * ... * big_nums[to_i]) % mod_i.
Return an integer array answer such that answer[i] is the answer to the i^th query.
 
Example 1:

Input: queries = [[1,3,7]]
Output: [4]
Explanation:
There is one query.
big_nums[1..3] = [2,1,2]. The product of them is 4. The remainder of 4 under 7 is 4.

Example 2:

Input: queries = [[2,5,3],[7,7,4]]
Output: [2,2]
Explanation:
There are two queries.
First query: big_nums[2..5] = [1,2,4,1]. The product of them is 8. The remainder of 8 under 3 is 2.
Second query: big_nums[7] = 2. The remainder of 2 under 4 is 2.

 
Constraints:

1 <= queries.length <= 500
queries[i].length == 3
0 <= queries[i][0] <= queries[i][1] <= 10^15
1 <= queries[i][2] <= 10^5

請寫一個頂層 Python 函式（不要用 class）：
def findProductsOfElements(queries: List[List[int]]):
只能用標準函式庫。函式必須回傳答案，不要印出。