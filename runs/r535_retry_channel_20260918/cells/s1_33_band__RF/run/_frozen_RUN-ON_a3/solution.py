def solution():
    import sys
    input_data = sys.stdin.read().strip()
    if not input_data:
        return
    
    score = int(input_data)
    
    if score >= 90:
        print('A')
    elif score >= 80:
        print('B')
    elif score >= 70:
        print('C')
    elif score >= 60:
        print('D')
    else:
        print('F')

if __name__ == "__main__":
    solution()
