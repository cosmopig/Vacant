import re

def initials(name):
    # The parts of a name are separated by spaces.
    parts = name.split(' ')
    initials_list = []
    for part in parts:
        if not part:
            continue
        # Compound given names joined by punctuation marks (e.g., "Jean-Pierre")
        # both halves are part of how someone is addressed, so we take the first letter 
        # of each segment separated by common punctuation marks.
        segments = re.split(r'[-.,;:]', part)
        for segment in segments:
            if segment:
                initials_list.append(f"{segment[0].upper()}.")
    
    result = "".join(initials_list)
    # If the name ends with a punctuation mark that was already handled, 
    # we might have double dots or trailing dots.
    # The goal is "A.L." for "ada lovelace".
    # My current logic: "ada" -> "A.", "lovelace" -> "L." -> "A.L."
    # If name was "Ada Lovelace", it would still be "A.L."
    # What if the name is "Jean-Luc Picard"? 
    # "Jean-Luc" -> ["J.", "L."] -> "J.L."
    # "Picard" -> ["P."] -> "P."
    # Total: "J.L.P."
    
    # Let's check if there are any double dots that need to be collapsed.
    # If a part was "Jean-Luc", segments are ["Jean", "Luc"]. 
    # initials_list becomes ["J.", "L."]
    # If the next part is "Picard", it becomes ["P."]
    # Result: "J.L.P."
    
    # What if a name has punctuation like "Ada, Lovelace"?
    # parts = ["Ada,", "Lovelace"]
    # "Ada," -> segments ["Ada", ""] -> initials_list ["A."]
    # "Lovelace" -> segments ["Lovelace"] -> initials_list ["A.", "L."]
    # Result: "A.L."
    
    # The only issue is if we have multiple dots at the end or something.
    # Let's refine it to ensure no double dots and a single trailing dot if needed.
    # Actually, the test says 'ada lovelace' -> 'A.L.'
    # My current code gives 'A.L.' for 'ada lovelace'.
    # Wait, why did it fail? Let me check the error again.
    # "initials args=('ada lovelace',) got='AL' want='A.L.'"
    # Ah! I was getting 'AL' before because I didn't have the dots.
    # Now I have them. Let's see what it gives now.
    
    return result.replace("..", ".")

