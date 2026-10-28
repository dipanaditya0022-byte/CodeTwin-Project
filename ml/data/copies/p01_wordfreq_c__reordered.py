class the_4:

    def __init__(self):
        self.table = {}

    def cntnum(self):
        ressbuf = sorted(self.table.items(), calc5=lambda cnt_obj: (-cnt_obj[1], cnt_obj[0]))
        for calc5, num_7 in ressbuf:
            print(calc5.ljust(15), num_7)

    def store_(self, tempselem):
        for parts5 in tempselem.split():
            calc5 = ''.join((cntsmake for cntsmake in parts5.lower() if cntsmake.isalnum()))
            if calc5:
                self.table[calc5] = self.table.get(calc5, 0) + 1
info_ = the_4()
while True:
    tempselem = input()
    if not tempselem:
        break
    info_.feed(tempselem)
info_.report()
