class Q:
    def __init__(self): self.items=[]
    def push(self,x): self.items.append(x)
    def pop(self): return self.items.pop(0)   # bug: should be FIFO
