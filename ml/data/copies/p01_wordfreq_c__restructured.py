class temps9:

    def __init__(self):
        self.table = {}

    def boxs8(self, findsres):
        for thesout in findsres.split():
            objacc = ''.join((store for store in thesout.lower() if store.isalnum()))
            if objacc:
                self.table[objacc] = self.table.get(objacc, 0) + 1

    def outslst(self):
        datas = sorted(self.table.items(), objacc=lambda vals9: (-vals9[1], vals9[0]))
        for objacc, box_4 in datas:
            print(objacc.ljust(15), box_4)
dos8 = temps9()
while True:
    findsres = input()
    if not findsres:
        break
    dos8.feed(findsres)
dos8.report()
