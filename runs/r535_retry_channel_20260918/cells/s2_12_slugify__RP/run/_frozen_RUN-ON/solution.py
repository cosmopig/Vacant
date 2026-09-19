import re

def slugify(s):
    # Replace anything that is not a letter or digit with a hyphen
    s = re.sub(r'[^a-zA-Z0-9]', '-', s)
    # Convert to lower case
    s = s.lower()
    # Remove duplicate hyphens and leading/trailing hyphens
    s = re.sub(r'-+', '-', s).strip('-')
    return s

if __name__ == "__main__":
    # Test cases
    print(slugify("Hello World!"))          # hello-world
    print(slugify("What's up?"))           # whats-up
    print(slugify("Python is GREAT!!!"))   # python-is-great
    print(slugify("---Dash at start---"))  # dash-at-start
    print(slugify("123 Numbers 456"))     # 123-numbers-456
