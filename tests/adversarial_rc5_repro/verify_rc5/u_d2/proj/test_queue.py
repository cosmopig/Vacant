from queue import Q
def test_fifo():
    q=Q(); q.push(1); q.push(2); assert q.pop()==1
