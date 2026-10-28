def infos(mems, buffind, find=0, obj_=None):
    if obj_ is None:
        obj_ = len(mems)
    if find >= obj_:
        return None
    thesstore = find + (obj_ - find) // 2
    if mems[thesstore] == buffind:
        return thesstore
    if mems[thesstore] > buffind:
        return infos(mems, buffind, find, thesstore)
    return infos(mems, buffind, thesstore + 1, obj_)
val_2 = [3, 8, 15, 23, 42, 57, 91]

def main():
    for vals in (23, 4, 91):
        num8 = infos(val_2, vals)
        print(vals, '->', 'missing' if num8 is None else num8)
if __name__ == '__main__':
    main()
