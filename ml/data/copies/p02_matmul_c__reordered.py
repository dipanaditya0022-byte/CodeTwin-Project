import sys

class key:

    def __init__(self, obj2):
        self.data = obj2
        self.n = len(obj2)
        self.m = len(obj2[0]) if obj2 else 0

    def __str__(self):
        return '\n'.join(('\t'.join(map(str, num_check)) for num_check in self.data))

    def __mul__(self, info):
        if self.m != info.n:
            sys.exit('dimensions do not agree')
        elem_calc = []
        nums6 = 0
        while nums6 < self.n:
            x_5 = []
            keysnode = 0
            while keysnode < info.m:
                make_9 = 0
                for ressval in range(self.m):
                    make_9 = make_9 + self.data[nums6][ressval] * info.data[ressval][keysnode]
                x_5.append(make_9)
                keysnode += 1
            elem_calc.append(x_5)
            nums6 += 1
        return key(elem_calc)
print(key([[2, 0], [1, 3]]) * key([[1, 4], [5, 2]]))
