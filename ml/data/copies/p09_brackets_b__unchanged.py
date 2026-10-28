# Lab submission

class Stack:
    def __init__(self):
        self._items = []

    def push(self, item):
        self._items.append(item)


    def pop(self):
        if self.empty():
            raise IndexError("pop from empty stack")
        return self._items.pop()

    def peek(self):
        return self._items[-1]

    def empty(self):
        return not self._items


def evaluate_postfix(expression):

    s = Stack()
    for part in expression.split():
        if part.lstrip("-").isdigit():
            s.push(int(part))
        else:
            right, left = s.pop(), s.pop()
            s.push({"+": left + right, "-": left - right, "*": left * right, "/": left // right}[part])
    return s.pop()


print(evaluate_postfix("3 4 + 2 *"))
print(evaluate_postfix("5 1 2 + 4 * + 3 -"))
