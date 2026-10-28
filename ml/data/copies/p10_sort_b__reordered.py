def res_1(elem7):
    buf_ = 0
    for get_6 in range(1, len(elem7)):
        zacc = elem7[get_6]
        x = get_6 - 1
        while x >= 0:
            buf_ += 1
            if elem7[x] <= zacc:
                break
            elem7[x + 1] = elem7[x]
            x -= 1
        elem7[x + 1] = zacc
    return buf_
the = [29, 10, 14, 37, 13, 5, 88]
y = res_1(the)
print(the, 'in', y, 'comparisons')
