def read_matrix(rows, cols):
    m = []
    for i in range(rows):
        row = [int(x) for x in input().split()]
        m.append(row[:cols])
    return m


r1, c1 = map(int, input().split())
a = read_matrix(r1, c1)
r2, c2 = map(int, input().split())
b = read_matrix(r2, c2)
if c1 != r2:
    print("Cannot multiply")
else:
    result = [[0] * c2 for _ in range(r1)]
    for i in range(r1):
        for j in range(c2):
            for k in range(c1):
                result[i][j] += a[i][k] * b[k][j]
    for row in result:
        print(" ".join(str(v) for v in row))
