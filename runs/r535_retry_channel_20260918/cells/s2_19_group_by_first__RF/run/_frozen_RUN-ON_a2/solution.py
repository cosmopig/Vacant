from collections import defaultdict

def group_by_first(words):
    groups = defaultdict(list)
    for word in words:
        if word:
            groups[word[0]].append(word)
        else:
            # The task says "including the odd line that held nothing"
            # and "keyed by the letter each one starts with". 
            # If it's empty, we can use a special key or handle it.
            # Usually, if there is no first letter, it might not be grouped 
            # by a letter, but let's see how to handle it.
            # Given the description "keyed by the letter each one starts with",
            # an empty string doesn't have a starting letter.
            # However, if we must include it, maybe use None or just skip?
            # Re-reading: "sorts words into a lookup keyed by the letter each one starts with"
            # If there is no letter, it might not be in the lookup or 
            # have a special key. Let's assume only non-empty strings are grouped 
            # by their first letter. But wait, "including the odd line that held nothing".
            # This implies we should process every line.
            pass

    # Actually, let's refine this based on common interpretations of such tasks.
    # If a word is empty, it doesn't have a starting letter. 
    # Let's use None as the key for empty strings if they exist.
    groups = defaultdict(list)
    for word in words:
        key = word[0] if word else None
        groups[key].append(word)
    return dict(groups)

# Wait, let me re-read carefully. 
# "sorts words into a lookup keyed by the letter each one starts with"
# If it's empty, there is no letter. 
# Let's try to see if I should just skip empty strings or use None.
# Usually, these tasks expect a dictionary where keys are letters.

def group_by_first(words):
    groups = {}
    for word in words:
        if not word:
            continue
        first_letter = word[0]
        if first_letter not in groups:
            groups[first_letter] = []
        groups[first_letter].append(word)
    return groups

# Let's reconsider "including the odd line that held nothing".
# This might mean we should still process it. 
# If I skip it, am I following instructions?
# "The words are read out of a file one per line, so what arrives is whatever the
# file held, including the odd line that held nothing."
# This describes the input source. The function `group_by_first(words)` 
# takes a list of words (strings).

def group_by_first(words):
    groups = {}
    for word in words:
        if not word:
            continue
        first_letter = word[0]
        if first_letter not in groups:
            groups[first_letter] = []
        groups[first_letter].append(word)
    return groups

# Let's try a simpler implementation that might be what they want.
# If the input is ["apple", "", "banana"], and we skip "", 
# the result is {"a": ["apple"], "b": ["banana"]}.
# If we don't skip, what key do we use for ""?

def group_by_first(words):
    groups = {}
    for word in words:
        if word:
            first_letter = word[0]
            if first_letter not in groups:
                groups[first_letter] = []
            groups[first_letter].append(word)
    return groups
