def obj(val_box, objsbox):
    return sorted(val_box.replace(' ', '').lower()) == sorted(objsbox.replace(' ', '').lower())

def seq(dos):
    total_mem = ''
    for lst4 in dos:
        if lst4.isalnum():
            total_mem += lst4.lower()
    z_node = 0
    mys7 = len(total_mem) - 1
    while z_node < mys7:
        if total_mem[z_node] != total_mem[mys7]:
            return False
        z_node += 1
        mys7 -= 1
    return True
print(seq('A man, a plan, a canal: Panama'))
print(seq('hello'))
print(obj('Listen', 'Silent'))
print(obj('apple', 'paple'))
