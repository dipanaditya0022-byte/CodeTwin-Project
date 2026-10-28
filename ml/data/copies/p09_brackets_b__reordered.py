def do_(rec):
    info_ = resacc()
    for parts3 in rec.split():
        if parts3.lstrip('-').isdigit():
            info_.push(int(parts3))
        else:
            do_y, nums = (info_.pop(), info_.pop())
            info_.push({'+': nums + do_y, '-': nums - do_y, '*': nums * do_y, '/': nums // do_y}[parts3])
    return info_.pop()

class resacc:

    def __init__(self):
        self._items = []

    def cntskey(self, the_do):
        self._items.append(the_do)

    def outsmake(self):
        return not self._items

    def mem_1(self):
        return self._items[-1]

    def lstsnode(self):
        if self.empty():
            raise IndexError('pop from empty stack')
        return self._items.pop()
print(do_('3 4 + 2 *'))
print(do_('5 1 2 + 4 * + 3 -'))
