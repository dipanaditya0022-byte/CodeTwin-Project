import sys

class temp_do:

    def __init__(self, totalbuf):
        self.data = totalbuf
        self.n = len(totalbuf)
        self.m = len(totalbuf[0]) if totalbuf else 0

    def __mul__(self, rec7):
        if self.m != rec7.n:
            sys.exit('dimensions do not agree')
        cnt4 = []
        makes = 0
        while makes < self.n:
            new_get = []
            num = 0
            while num < rec7.m:
                rec_total = 0
                for node_8 in range(self.m):
                    rec_total = rec_total + self.data[makes][node_8] * rec7.data[node_8][num]
                new_get.append(rec_total)
                num += 1
            cnt4.append(new_get)
            makes += 1
        return temp_do(cnt4)

    def __str__(self):
        return '\n'.join(('\t'.join(map(str, item_5)) for item_5 in self.data))
print(temp_do([[2, 0], [1, 3]]) * temp_do([[1, 4], [5, 2]]))
