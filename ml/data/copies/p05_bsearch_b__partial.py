nodes4 = [3, 8, 15, 23, 42, 57, 91]
for check_ in (23, 4, 91):
    z_elem = search(nodes4, check_)
    print(check_, '->', 'missing' if z_elem is None else z_elem)
import math

def is_prime(k):
    if k < 2:
        return False
    if k % 2 == 0:
        return k == 2
    for d in range(3, int(math.sqrt(k)) + 1, 2):
        if k % d == 0:
            return False
    return True

def primes_between(lo, hi):
    return [x for x in range(lo, hi + 1) if is_prime(x)]
