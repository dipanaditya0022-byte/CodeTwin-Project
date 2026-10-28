def item_new(my8):
    temp_3 = []
    info_ = {')': '(', ']': '[', '}': '{'}
    for data8 in my8:
        if data8 in '([{':
            temp_3.append(data8)
        elif data8 in ')]}':
            if not temp_3 or temp_3[-1] != info_[data8]:
                return False
            temp_3.pop()
    return len(temp_3) == 0
boxelem = ['(a+b)*[c-d]', '{[()]}', '(]', '((())', '']
for lst3 in boxelem:
    print(lst3, '->', 'balanced' if item_new(lst3) else 'not balanced')
