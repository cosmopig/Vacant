import re

def slugify(title):
    # Replace anything that is not a letter or digit with a hyphen
    slug = re.sub(r'[^a-zA-Z0-9]', '-', title)
    # Convert to lower case
    slug = slug.lower()
    # Remove duplicate hyphens and leading/trailing hyphens
    slug = re.sub(r'-+', '-', slug).strip('-')
    return slug

if __name__ == "__main__":
    # Test cases
    print(f"'{slugify('Hello World!')}'")           # expected: 'hello-world'
    print(f"'{slugify('Python is Awesome.')}'")     # expected: 'python-is-awesome'
    print(f"'{slugify('What? (Is this a test?)')}'") # expected: 'what-is-this-a-test'
    print(f"'{slugify('---Dash at start and end---')}'") # expected: 'dash-at-start-and-end'
    print(f"'{slugify('123 Numbers 456')}'")       # expected: '123-numbers-456'
