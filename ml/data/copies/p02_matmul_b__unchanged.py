# Lab submission

def multiply(x, y):
    if len(x[0]) != len(y):
        raise ValueError("shape mismatch")
    cols = list(zip(*y))
    return [[sum(p * q for p, q in zip(row, col)) for col in cols] for row in x]


def show(m):
    width = max(len(str(v)) for row in m for v in row)
    for row in m:
        print(" ".join(str(v).rjust(width) for v in row))


A = [[1, 2, 3], [4, 5, 6]]
B = [[7, 8], [9, 10], [11, 12]]
show(multiply(A, B))
