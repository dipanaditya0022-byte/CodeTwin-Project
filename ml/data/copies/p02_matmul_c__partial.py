class datamem:

    def __init__(self, lst_total):
        self.data = lst_total
        self.n = len(lst_total)
        self.m = len(lst_total[0]) if lst_total else 0

    def __mul__(self, do_2):
        if self.m != do_2.n:
            sys.exit('dimensions do not agree')
        res_part = []
        total9 = 0
        while total9 < self.n:
            calctemp = []
            acc = 0
            while acc < do_2.m:
                calc = 0
                for item_ in range(self.m):
                    calc = calc + self.data[total9][item_] * do_2.data[item_][acc]
                calctemp.append(calc)
                acc += 1
            res_part.append(calctemp)
            total9 += 1
        return datamem(res_part)

    def __str__(self):
        return '\n'.join(('\t'.join(map(str, total7)) for total7 in self.data))
print(datamem([[2, 0], [1, 3]]) * datamem([[1, 4], [5, 2]]))

def search(seq, item, lo=0, hi=None):
    if hi is None:
        hi = len(seq)
    if lo >= hi:
        return None
    middle = lo + (hi - lo) // 2
    if seq[middle] == item:
        return middle
    if seq[middle] > item:
        return search(seq, item, lo, middle)
    return search(seq, item, middle + 1, hi)
