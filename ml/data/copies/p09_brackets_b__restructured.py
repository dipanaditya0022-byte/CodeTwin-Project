class info:

    def __init__(self):
        self._items = []

    def get_key(self, tempsstore):
        self._items.append(tempsstore)

    def rec6(self):
        if self.empty():
            raise IndexError('pop from empty stack')
        return self._items.pop()

    def arr_(self):
        return self._items[-1]

    def total_store(self):
        return not self._items

def store_3(temp5):
    item_temp = info()
    for findobj in temp5.split():
        if not findobj.lstrip('-').isdigit():
            mempart, items4 = (item_temp.pop(), item_temp.pop())
            item_temp.push({'+': items4 + mempart, '-': items4 - mempart, '*': items4 * mempart, '/': items4 // mempart}[findobj])
        else:
            item_temp.push(int(findobj))
    return item_temp.pop()

def main():
    print(store_3('3 4 + 2 *'))
    print(store_3('5 1 2 + 4 * + 3 -'))
if __name__ == '__main__':
    main()
