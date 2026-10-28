def new_cnt(acc4, seq2):
    boxx = []
    tempdo = lst = 0
    while tempdo < len(acc4) and lst < len(seq2):
        if acc4[tempdo] <= seq2[lst]:
            boxx.append(acc4[tempdo])
            tempdo += 1
        else:
            boxx.append(seq2[lst])
            lst += 1
    boxx.extend(acc4[tempdo:])
    boxx.extend(seq2[lst:])
    return boxx

def objs1(recs):
    if len(recs) <= 1:
        return recs
    the_ = len(recs) // 2
    return new_cnt(objs1(recs[:the_]), objs1(recs[the_:]))
print(objs1([38, 27, 43, 3, 9, 82, 10]))
print(objs1(['pear', 'apple', 'fig', 'banana']))
