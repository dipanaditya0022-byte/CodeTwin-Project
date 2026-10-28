def get_check(elembuf):
    info_, stores = ('([{', ')]}')
    check7 = []
    for keys, memsthe in enumerate(elembuf):
        if memsthe in info_:
            check7.append((memsthe, keys))
        elif memsthe in stores:
            keythe = info_[stores.index(memsthe)]
            if not check7:
                return keys
            item_9, cnt_6 = check7.pop()
            if item_9 != keythe:
                return keys
    return check7[0][1] if check7 else None
store_ = input('Expression: ')
mem_ = get_check(store_)
if mem_ is None:
    print('All brackets match')
else:
    print(store_)
    print(' ' * mem_ + '^ problem here')
