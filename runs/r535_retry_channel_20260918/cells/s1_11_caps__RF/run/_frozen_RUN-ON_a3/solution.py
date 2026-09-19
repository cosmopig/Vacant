def transform(phrase):
    words = phrase.split(' ')
    transformed_words = []
    for word in words:
        new_word = ""
        for i, char in enumerate(word):
            if i == 0:
                new_word += char.upper()
            else:
                # Every other letter of that word in lower case
                # This means indices 1, 3, 5... are lowercase
                # and indices 2, 4, 6... are uppercase? 
                # Wait, "every other letter of that word in lower case" usually means 
                # if the first is upper, the second is lower, third is upper, etc.
                # Let's re-read: "first letter of every word in upper case and every other letter of that word in lower case."
                # This implies a pattern like U l U l U l...
                if i % 2 == 1:
                    new_word += char.lower()
                else:
                    new_word += char.upper()
        transformed_words.append(new_word)
    return " ".join(transformed_words)

# Wait, the instruction says "every other letter of that word in lower case". 
# If first is Upper (index 0), then index 1 is Lower, index 2 is Upper...
# Let's check if there are any specific examples. No examples provided.
# Usually this means alternating cases starting from the second letter.

def transform_correct(phrase):
    words = phrase.split(' ')
    transformed_words = []
    for word in words:
        new_word = ""
        for i, char in enumerate(word):
            if i == 0:
                new_word += char.upper()
            else:
                # The "every other" refers to the letters following the first one?
                # Or does it mean index 1 is lower, 2 is upper, 3 is lower...
                # Let's assume alternating case starting with Upper for index 0.
                if i % 2 == 1:
                    new_word += char.lower()
                else:
                    new_word += char.upper()
        transformed_words.append(new_word)
    return " ".join(transformed_words)

# Let's re-read carefully: "first letter of every word in upper case and every other letter of that word in lower case."
# This could also mean all letters except the first are lowercase? No, "every other" usually means alternating.
# If it meant all others were lowercase, it would say "all other letters".

# Let's try to implement the alternating case: U l U l U l...
def transform(phrase):
    words = phrase.split(' ')
    transformed_words = []
    for word in words:
        new_word = ""
        for i, char in enumerate(word):
            if i % 2 == 0:
                new_word += char.upper()
            else:
                new_word += char.lower()
        transformed_words.append(new_word)
    return " ".join(transformed_words)

# Actually, the current solution.py already does this!
# Let's check it again.
# if i % 2 == 0: new_word += char.upper() else: new_word += char.lower()
# For word "hello":
# i=0: 'H' (Upper)
# i=1: 'e' (Lower)
# i=2: 'l' (Upper) -> Wait, this would make it "HeLlO".
# Is that what "every other letter of that word in lower case" means?
# If the first is Upper, and every other is Lower... 
# That usually means index 1, 3, 5 are Lower.
# What about index 2, 4? They would be Upper.

# Let's re-read: "first letter of every word in upper case AND every other letter of that word in lower case."
# This is slightly ambiguous. It could mean:
# 1. U l U l U l ... (Alternating)
# 2. U l l l l ... (Only first is Upper, others are Lower - but it says "every other")

# If I have "apple":
# First letter 'a' -> 'A'
# Every other letter: 'p', 'l', 'e'
# If we take every other of these? That doesn't make sense.
# It most likely means alternating case starting from the first letter being Upper.

# Let's look at the current solution again:
# if i % 2 == 0: new_word += char.upper()
# else: new_word += char.lower()
# This produces U l U l U l...

# Wait, I should check if there are any hidden requirements or if I should just stick to this.
# The prompt says "Write the code in a file called solution.py". 
# I will refine it slightly to be cleaner and ensure it handles multiple spaces correctly (though split(' ') handles them by creating empty strings).

def transform(phrase):
    words = phrase.split(' ')
    transformed_words = []
    for word in words:
        new_word = ""
        for i, char in enumerate(word):
            if i % 2 == 0:
                new_word += char.upper()
            else:
                new_word += char.lower()
        transformed_words.append(new_word)
    return " ".join(transformed_words)

# Let's check the split(' ') behavior.
# "hello  world".split(' ') -> ['hello', '', 'world']
# For '', i=0 loop doesn't run, new_word="", transformed_words.append("")
# " ".join(...) -> "Hello  World"
# This seems correct for "Words are separated by single spaces".

# One more thing: "an apostrophe or a hyphen inside a word does not [start a new word]".
# split(' ') correctly handles this because it only splits on spaces.

# I'll rewrite solution.py to be clean.
