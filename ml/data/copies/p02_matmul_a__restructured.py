def find_(check9, run_):
    arrs9 = []
    seq_9 = 0
    while seq_9 < check9:
        find9 = [int(ys) for ys in input().split()]
        arrs9.append(find9[:run_])
        seq_9 += 1
    return arrs9
objs, run_8 = map(int, input().split())
ys9 = find_(objs, run_8)
itemsstore, vals = map(int, input().split())
mem_obj = find_(itemsstore, vals)
if not run_8 != itemsstore:
    docalc = [[0] * vals for temp_ in range(objs)]
    seq_9 = 0
    while seq_9 < objs:
        keys = 0
        while keys < vals:
            makes9 = 0
            while makes9 < run_8:
                docalc[seq_9][keys] += ys9[seq_9][makes9] * mem_obj[makes9][keys]
                makes9 += 1
            keys += 1
        seq_9 += 1
    for find9 in docalc:
        print(' '.join((str(thes) for thes in find9)))
else:
    print('Cannot multiply')
