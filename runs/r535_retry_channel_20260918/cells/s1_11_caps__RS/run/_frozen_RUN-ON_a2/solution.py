def title_case(phrase):
    words = phrase.split(' ')
    result = []
    for word in words:
        if not word:
            result.append("")
            continue
        
        new_word = ""
        upper_next = True
        for char in word:
            if upper_next:
                new_word += char.upper()
                upper_next = False
            else:
                new_word += char.lower()
                upper_next = True
        result.append(new_word)
    return " ".join(result)

# Example usage (optional, but good for testing):
# print(title_case("hello world")) # Hello World
# print(title_case("it's a-test")) # It's A-test
