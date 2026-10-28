def ys(get_elem, gets):
    store7 = 0
    x = len(get_elem) - 1
    while store7 <= x:
        outelem = (store7 + x) // 2
        if get_elem[outelem] == gets:
            return outelem
        elif get_elem[outelem] < gets:
            store7 = outelem + 1
        else:
            x = outelem - 1
    return -1
seq_cnt = sorted((int(boxs7) for boxs7 in input().split()))
find_out = int(input())
ress8 = ys(seq_cnt, find_out)
if ress8 == -1:
    print('Not found')
else:
    print('Found at index', ress8)
