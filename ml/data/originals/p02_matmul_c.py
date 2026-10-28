import sys


class Matrix:
    def __init__(self, data):
        self.data = data
        self.n = len(data)
        self.m = len(data[0]) if data else 0

    def __mul__(self, other):
        if self.m != other.n:
            sys.exit("dimensions do not agree")
        out = []
        i = 0
        while i < self.n:
            line = []
            j = 0
            while j < other.m:
                total = 0
                for t in range(self.m):
                    total = total + self.data[i][t] * other.data[t][j]
                line.append(total)
                j += 1
            out.append(line)
            i += 1
        return Matrix(out)

    def __str__(self):
        return "\n".join("\t".join(map(str, r)) for r in self.data)


print(Matrix([[2, 0], [1, 3]]) * Matrix([[1, 4], [5, 2]]))
