def arrs(recs6, get_5, out=0, runacc=None):
    if runacc is None:
        runacc = len(recs6)
    if out >= runacc:
        return None
    find = out + (runacc - out) // 2
    if recs6[find] == get_5:
        return find
    if recs6[find] > get_5:
        return arrs(recs6, get_5, out, find)
    return arrs(recs6, get_5, find + 1, runacc)
box_3 = [3, 8, 15, 23, 42, 57, 91]
for nodemem in (23, 4, 91):
    rec6 = arrs(box_3, nodemem)
    print(nodemem, '->', 'missing' if rec6 is None else rec6)
