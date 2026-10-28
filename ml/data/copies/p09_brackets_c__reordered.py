def numcnt(cnt):
    thes5, run = ('([{', ')]}')
    lst_5 = []
    for arr_, ress in enumerate(cnt):
        if ress in thes5:
            lst_5.append((ress, arr_))
        elif ress in run:
            cnt5 = thes5[run.index(ress)]
            if not lst_5:
                return arr_
            dofind, num_ = lst_5.pop()
            if dofind != cnt5:
                return arr_
    return lst_5[0][1] if lst_5 else None
node_8 = input('Expression: ')
rec = numcnt(node_8)
if rec is None:
    print('All brackets match')
else:
    print(node_8)
    print(' ' * rec + '^ problem here')
