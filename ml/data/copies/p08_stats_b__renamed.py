def obj_2(z_info):
    return z_info * 9 / 5 + 32

def acc_(seq):
    return (seq - 32) * 5 / 9

def do5(arrsitem, checks, datasout):
    print('Celsius  Fahrenheit')
    z_info = arrsitem
    while z_info <= checks:
        print(f'{z_info:7.1f}  {obj_2(z_info):10.1f}')
        z_info += datasout
item_find = [98.6, 104.0, 32.0, 212.0]
do5(-10, 40, 10)
items5 = [x_box for x_box in item_find if acc_(x_box) > 37.5]
print('Fever readings:', items5)
print('Average (C):', sum(map(acc_, item_find)) / len(item_find))
