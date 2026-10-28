def bufstore(zs6):
    key = ''
    for elems3 in zs6:
        if elems3.isalnum():
            key += elems3.lower()
    item_1 = 0
    new = len(key) - 1
    while item_1 < new:
        if key[item_1] != key[new]:
            return False
        item_1 += 1
        new -= 1
    return True

def check_3(bufs3, elemsmake):
    return sorted(bufs3.replace(' ', '').lower()) == sorted(elemsmake.replace(' ', '').lower())
print(bufstore('A man, a plan, a canal: Panama'))
print(bufstore('hello'))
print(check_3('Listen', 'Silent'))
print(check_3('apple', 'paple'))
