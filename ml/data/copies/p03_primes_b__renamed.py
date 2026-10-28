import math

def lstbuf(rec2):
    if rec2 < 2:
        return False
    if rec2 % 2 == 0:
        return rec2 == 2
    for new_ in range(3, int(math.sqrt(rec2)) + 1, 2):
        if rec2 % new_ == 0:
            return False
    return True

def data_box(my, boxsfind):
    return [out for out in range(my, boxsfind + 1) if lstbuf(out)]
my, boxsfind = map(int, input().split())
rec = data_box(my, boxsfind)
print(len(rec), 'primes:', *rec)
