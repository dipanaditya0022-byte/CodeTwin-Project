ress3 = int(input('How many students? '))
gets7 = []
new = []
for objs in range(ress3):
    acc_8 = input('Name: ')
    get_num = float(input('Mark: '))
    gets7.append(acc_8)
    new.append(get_num)
elems = sum(new) / ress3
new_ = max(new)
print('Average:', round(elems, 2))
print('Topper:', gets7[new.index(new_)], new_)
for objs in range(ress3):
    if new[objs] >= 90:
        checks3 = 'A'
    elif new[objs] >= 75:
        checks3 = 'B'
    elif new[objs] >= 50:
        checks3 = 'C'
    else:
        checks3 = 'F'
    print(gets7[objs], checks3)
