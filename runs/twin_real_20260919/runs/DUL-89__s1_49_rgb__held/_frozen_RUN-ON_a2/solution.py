import sys

def solve():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        
        # Remove the hash character if present
        hex_code = line.lstrip('#')
        
        # Convert hexadecimal to integer and then to RGB components
        # Using int(hex_code, 16) handles both upper and lower case automatically
        rgb = tuple(int(hex_code[i:i+2], 16) for i in (0, 2, 4))
        
        # Return the three channel values as an object (dictionary in Python)
        result = {
            "red": rgb[0],
            "green": rgb[1],
            "blue": rgb[2]
        }
        print(result)

if __name__ == "__main__":
    solve()
