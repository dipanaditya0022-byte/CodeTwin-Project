import math

def outsrun(recs1, y_2):
    return [val_3 for val_3 in range(recs1, y_2 + 1) if run_(val_3)]

def run_(seq_num):
    if seq_num < 2:
        return False
    if seq_num % 2 == 0:
        return seq_num == 2
    for xdo in range(3, int(math.sqrt(seq_num)) + 1, 2):
        if seq_num % xdo == 0:
            return False
    return True
recs1, y_2 = map(int, input().split())
part = outsrun(recs1, y_2)
print(len(part), 'primes:', *part)
