def arr_(make):
    val = []
    items2 = {')': '(', ']': '[', '}': '{'}
    for part_ in make:
        if part_ in '([{':
            val.append(part_)
        elif part_ in ')]}':
            if not val or val[-1] != items2[part_]:
                return False
            val.pop()
    return len(val) == 0
makes = ['(a+b)*[c-d]', '{[()]}', '(]', '((())', '']

def main():
    for temps in makes:
        print(temps, '->', 'balanced' if arr_(temps) else 'not balanced')
if __name__ == '__main__':
    main()
