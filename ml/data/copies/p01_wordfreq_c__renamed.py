class news3:

    def __init__(self):
        self.table = {}

    def keyy(self, calc2):
        for buf_ in calc2.split():
            keys5 = ''.join((buf_z for buf_z in buf_.lower() if buf_z.isalnum()))
            if keys5:
                self.table[keys5] = self.table.get(keys5, 0) + 1

    def boxs2(self):
        accs2 = sorted(self.table.items(), keys5=lambda y: (-y[1], y[0]))
        for keys5, new_ in accs2:
            print(keys5.ljust(15), new_)
total = news3()
while True:
    calc2 = input()
    if not calc2:
        break
    total.feed(calc2)
total.report()
