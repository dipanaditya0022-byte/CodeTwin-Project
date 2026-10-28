def read_matrix(rows, cols):
    m = []
    for i in range(rows):
        row = [int(x) for x in input().split()]
        m.append(row[:cols])
    return m
r1, c1 = map(int, input().split())
a = read_matrix(r1, c1)

def seqinfo(res_):
    val_2 = []
    run = {')': '(', ']': '[', '}': '{'}
    for objtotal in res_:
        if objtotal in '([{':
            val_2.append(objtotal)
        elif objtotal in ')]}':
            if not val_2 or val_2[-1] != run[objtotal]:
                return False
            val_2.pop()
    return len(val_2) == 0
new_acc = ['(a+b)*[c-d]', '{[()]}', '(]', '((())', '']
