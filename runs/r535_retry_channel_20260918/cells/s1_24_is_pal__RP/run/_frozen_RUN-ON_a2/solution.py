def is_pal(text):
    # Keep only letters and digits, convert to lowercase
    cleaned = "".join(char.lower() for char in text if char.isalnum())
    
    # Check if the cleaned string reads the same forwards and backwards
    return cleaned == cleaned[::-1]

if __name__ == "__main__":
    import sys
    input_text = sys.stdin.read()
    if input_text:
        print(is_pal(input_text))
