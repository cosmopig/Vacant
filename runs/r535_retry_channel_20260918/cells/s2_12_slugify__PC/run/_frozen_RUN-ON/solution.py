import re

def slugify(title):
    # Replace anything that is not a letter or digit with a hyphen
    slug = re.sub(r'[^a-zA-Z0-9]', '-', title)
    
    # Convert to lower case
    slug = slug.lower()
    
    # Collapse multiple hyphens into a single hyphen
    slug = re.sub(r'-+', '-', slug)
    
    # Remove leading and trailing hyphens
    slug = slug.strip('-')
    
    return slug

if __name__ == "__main__":
    # Test cases
    print(f"'{slugify('Hello World!')}'")           # expected: 'hello-world'
    print(f"'{slugify('  Hello   World!  ')}'")     # expected: 'hello-world'
    print(f"'{slugify('Hello--World')}'")           # expected: 'hello-world'
    print(f"'{slugify('---Hello World---')}'")       # expected: 'hello-world'
    print(f"'{slugify('What? (Is) This?')}'")        # expected: 'what-is-this'
    print(f"'{slugify('123 Numbers 456')}'")         # expected: '123-numbers-456'
    print(f"'{slugify('!!!Special Characters!!!')}'") # expected: 'special-characters'
