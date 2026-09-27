def do_algebra(operator, operand):
    """
    Given two lists operator, and operand. The first list has basic algebra operations, and 
    the second list is a list of integers. Use the two given lists to build the algebric 
    expression and return the evaluation of this expression.

    The basic algebra operations:
    Addition ( + ) 
    Subtraction ( - ) 
    Multiplication ( * ) 
    Floor division ( // ) 
    Exponentiation ( ** ) 

    Example:
    operator = ['+', '*', '-']
    operand = [2, 3, 4, 5]
    result = 2 + 3 * 4 - 5
    => result = 9

    Note:
        The length of operator list is equal to the length of operand list minus one.
        Operand is a list of of non-negative integers.
        Operator list has at least one operator, and operand list has at least two operands.

    """
    precedence = {
        '+': (1, 'L'),
        '-': (1, 'L'),
        '*': (2, 'L'),
        '//': (2, 'L'),
        '**': (3, 'R')
    }

    def apply_op(v1, v2, op):
        if op == '+': return v1 + v2
        if op == '-': return v1 - v2
        if op == '*': return v1 * v2
        if op == '//': return v1 // v2
        if op == '**': return v1 ** v2
        return 0

    values = [operand[0]]
    ops = []

    for i in range(len(operator)):
        op = operator[i]
        val = operand[i+1]
        
        while ops and precedence[ops[-1]][0] >= precedence[op][0]:
            if precedence[ops[-1]][0] == precedence[op][0] and precedence[op][1] == 'R':
                break
            top_op = ops.pop()
            v2 = values.pop()
            v1 = values.pop()
            values.append(apply_op(v1, v2, top_op))
        
        ops.append(op)
        values.append(val)

    while ops:
        top_op = ops.pop()
        v2 = values.pop()
        v1 = values.pop()
        values.append(apply_op(v1, v2, top_op))

    return values[0]
