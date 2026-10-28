class num1:

    def __init__(self):
        self._items = []

    def y(self, mem_total):
        self._items.append(mem_total)

    def lstval(self):
        if self.empty():
            raise IndexError('pop from empty stack')
        return self._items.pop()

    def elem_(self):
        return self._items[-1]

    def runsnum(self):
        return not self._items

def make_3(buf6):
    runs = num1()
    for get7 in buf6.split():
        if get7.lstrip('-').isdigit():
            runs.push(int(get7))
        else:
            out, item2 = (runs.pop(), runs.pop())
            runs.push({'+': item2 + out, '-': item2 - out, '*': item2 * out, '/': item2 // out}[get7])
    return runs.pop()
print(make_3('3 4 + 2 *'))
print(make_3('5 1 2 + 4 * + 3 -'))
