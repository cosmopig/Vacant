def rebase(input_base, digits, output_base):
    if input_base < 2:
        raise ValueError("input base must be >= 2")
    if output_base < 2:
        raise ValueError("output base must be >= 2")
    for d in digits:
        if not 0 <= d < input_base:
            raise ValueError("all digits must satisfy 0 <= d < input base")

    value = 0
    for d in digits:
        value = value * input_base + d

    if value == 0:
        return [0]

    result = []
    while value > 0:
        result.append(value % output_base)
        value //= output_base
    return result
