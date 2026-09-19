def titleize(s):
    words = s.split(' ')
    result = []
    for word in words:
        if not word:
            result.append("")
            continue
        # If the word is all uppercase, keep it as is (acronym)
        if word.isupper():
            result.append(word)
        else:
            # Capitalize only the first letter and leave the rest as they are
            # But wait, if I have "NASA", .isupper() is True.
            # If I have "the", .isupper() is False. word[0].upper() + word[1:] -> "The"
            # If I have "report", .isupper() is False. word[0].upper() + word[1:] -> "Report"
            # So why did it fail? 
            # Oh, wait! The test says: titleize args=('the NASA report',) got='The Nasa Report' want='The NASA Report'
            # My current code for 'NASA': isupper() is True, so result.append('NASA'). Correct.
            # My current code for 'report': isupper() is False, word[0].upper() + word[1:] -> 'Report'. Correct.
            # My current code for 'the': isupper() is False, word[0].upper() + word[1:] -> 'The'. Correct.
            # So why did it get 'The Nasa Report'? 
            # Let me check my solution.py again.
            result.append(word[0].upper() + word[1:])
    return ' '.join(result)

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        print(titleize(sys.argv[1]))
