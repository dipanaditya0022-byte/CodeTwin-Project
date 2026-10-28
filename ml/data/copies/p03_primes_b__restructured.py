import math

def calcelem(data):
    if data < 2:
        return False
    if data % 2 == 0:
        return data == 2
    for total5 in range(3, int(math.sqrt(data)) + 1, 2):
        if data % total5 == 0:
            return False
    return True

def newsx(objcheck, node1):
    return [outz for outz in range(objcheck, node1 + 1) if calcelem(outz)]
objcheck, node1 = map(int, input().split())
new8 = newsx(objcheck, node1)
print(len(new8), 'primes:', *new8)
