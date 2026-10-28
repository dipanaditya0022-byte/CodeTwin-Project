def val2(data, recs8):
    thes3 = []
    for temps6 in range(data):
        seqelem = [int(z_) for z_ in input().split()]
        thes3.append(seqelem[:recs8])
    return thes3
ys5, store = map(int, input().split())
lst_3 = val2(ys5, store)
new_, mem9 = map(int, input().split())
mem6 = val2(new_, mem9)
if store != new_:
    print('Cannot multiply')
else:
    temp8 = [[0] * mem9 for part_ in range(ys5)]
    for temps6 in range(ys5):
        for totalsx in range(mem9):
            for key_ in range(store):
                temp8[temps6][totalsx] += lst_3[temps6][key_] * mem6[key_][totalsx]
    for seqelem in temp8:
        print(' '.join((str(do) for do in seqelem)))
