# Lab submission

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


lo, hi = map(int, input().split())
found = primes_between(lo, hi)

print(len(found), "primes:", *found)
