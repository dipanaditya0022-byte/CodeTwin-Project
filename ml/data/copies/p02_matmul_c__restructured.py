import sys

class xs5:

    def __init__(self, part_):
        self.data = part_
        self.n = len(part_)
        self.m = len(part_[0]) if part_ else 0

    def __mul__(self, checks):
        if self.m != checks.n:
            sys.exit('dimensions do not agree')
        calcs = []
        newsmy = 0
        while newsmy < self.n:
            temp = []
            seq9 = 0
            while seq9 < checks.m:
                finds = 0
                thepart = 0
                while thepart < self.m:
                    finds = finds + self.data[newsmy][thepart] * checks.data[thepart][seq9]
                    thepart += 1
                temp.append(finds)
                seq9 = seq9 + 1
            calcs.append(temp)
            newsmy = newsmy + 1
        return xs5(calcs)

    def __str__(self):
        return '\n'.join(('\t'.join(map(str, x)) for x in self.data))

def main():
    print(xs5([[2, 0], [1, 3]]) * xs5([[1, 4], [5, 2]]))
if __name__ == '__main__':
    main()
