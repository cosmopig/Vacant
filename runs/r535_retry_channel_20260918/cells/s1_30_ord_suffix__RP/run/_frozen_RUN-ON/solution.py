def solve(n):
    # "the number itself followed by the two-letter ending that goes with it"
    # This refers to ordinal numbers like 1st, 2nd, 3rd, 4th...
    # But they are said as first, second, third, fourth...
    # The prompt says: "Write a positive whole number the way it is said when counting positions"
    # And then explains what that means in this context:
    # ": the number itself followed by the two-letter ending that goes with it."
    # This is very confusing. Let's think about the teens exception again.
    # "The three teens... take the plain ending."
    # The plain ending is "-th".
    # So 11 -> eleventh, 12 -> twelfth, 13 -> thirteenth.
    # If they were NOT exceptions, what would they be?
    # Maybe "eleven" + "st"? No, that's not right.
    # In English, it's "first", "second", "third".
    # Then from 4 onwards, it's usually "-th" added to the cardinal number.
    # 4 -> four + th = fourth
    # 5 -> five + th = fifth (exception: ve -> f)
    # 6 -> six + th = sixth
    # 7 -> seven + th = seventh
    # 8 -> eight + th = eighth
    # 9 -> nine + th = ninth
    # 10 -> ten + th = tenth
    # 11 -> eleven + th = eleventh (exception: the prompt says these are exceptions!)
    # Wait, if 11, 12, 13 are exceptions and take the "plain ending" (-th),
    # then what do the others take?
    # Maybe they take something else?
    # But "first", "second", "third" don't have a "-th" ending.
    # This is very confusing.

    # Let's try to think about "the number itself followed by the two-letter ending".
    # Could it be:
    # 1 -> first
    # 2 -> second
    # 3 -> third
    # 4 -> fourth
    # ...
    # and the description is just a very confusing way of saying "ordinals"?

    pass
