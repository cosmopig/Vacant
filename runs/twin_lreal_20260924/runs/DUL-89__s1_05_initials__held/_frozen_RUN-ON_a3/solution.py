def solution(name: str) -> str:
    parts = name.split()
    initials = [part[0].upper() for part in parts]
    return "".join(initials)

if __name__ == "__main__":
    import sys
    input_data = sys.stdin.read().strip()
    if input_data:
        print(solution(input_data))
