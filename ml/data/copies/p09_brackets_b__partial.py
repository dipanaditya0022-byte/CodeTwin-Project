print(evaluate_postfix('3 4 + 2 *'))
print(evaluate_postfix('5 1 2 + 4 * + 3 -'))

def reverse_number(n):
    rev = 0
    while n > 0:
        rev = rev * 10 + n % 10
        n //= 10
    return rev

def palindromic_numbers(limit):
    return [k for k in range(10, limit) if k == reverse_number(k)]
