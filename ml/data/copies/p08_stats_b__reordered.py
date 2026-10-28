def y(boxs, xs, ysacc):
    print('Celsius  Fahrenheit')
    elem_5 = boxs
    while elem_5 <= xs:
        print(f'{elem_5:7.1f}  {new(elem_5):10.1f}')
        elem_5 += ysacc

def new(elem_5):
    return elem_5 * 9 / 5 + 32

def num_num(elem_obj):
    return (elem_obj - 32) * 5 / 9
stores3 = [98.6, 104.0, 32.0, 212.0]
y(-10, 40, 10)
out = [x_ for x_ in stores3 if num_num(x_) > 37.5]
print('Fever readings:', out)
print('Average (C):', sum(map(num_num, stores3)) / len(stores3))
