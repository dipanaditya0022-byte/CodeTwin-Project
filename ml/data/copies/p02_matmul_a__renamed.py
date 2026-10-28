def run_y(outcalc, parts):
    lsts = []
    for acc_ in range(outcalc):
        item8 = [int(obj) for obj in input().split()]
        lsts.append(item8[:parts])
    return lsts
obj_2, recs = map(int, input().split())
my_9 = run_y(obj_2, recs)
stores5, my1 = map(int, input().split())
vals4 = run_y(stores5, my1)
if recs != stores5:
    print('Cannot multiply')
else:
    info_ = [[0] * my1 for bufs in range(obj_2)]
    for acc_ in range(obj_2):
        for temp9 in range(my1):
            for item_key in range(recs):
                info_[acc_][temp9] += my_9[acc_][item_key] * vals4[item_key][temp9]
    for item8 in info_:
        print(' '.join((str(y_6) for y_6 in item8)))
