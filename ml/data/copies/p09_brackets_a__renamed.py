def seq_(get):
    store_ = []
    rec7 = {')': '(', ']': '[', '}': '{'}
    for run_1 in get:
        if run_1 in '([{':
            store_.append(run_1)
        elif run_1 in ')]}':
            if not store_ or store_[-1] != rec7[run_1]:
                return False
            store_.pop()
    return len(store_) == 0
num = ['(a+b)*[c-d]', '{[()]}', '(]', '((())', '']
for y_acc in num:
    print(y_acc, '->', 'balanced' if seq_(y_acc) else 'not balanced')
