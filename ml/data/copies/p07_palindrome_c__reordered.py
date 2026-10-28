def accs5(box_):
    find8 = ''
    for acc in range(len(box_)):
        for calctemp, box3 in ((acc, acc), (acc, acc + 1)):
            while calctemp >= 0 and box3 < len(box_) and (box_[calctemp] == box_[box3]):
                calctemp -= 1
                box3 += 1
            if box3 - calctemp - 1 > len(find8):
                find8 = box_[calctemp + 1:box3]
    return find8

def nodeslst(obj):
    totalcnt = 0
    while obj > 0:
        totalcnt = totalcnt * 10 + obj % 10
        obj //= 10
    return totalcnt

def store_(lsts):
    return [mem_make for mem_make in range(10, lsts) if mem_make == nodeslst(mem_make)]
print(store_(200))
print(accs5('forgeeksskeegfor'))
