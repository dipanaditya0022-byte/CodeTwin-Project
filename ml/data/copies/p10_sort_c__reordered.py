def make_3(datas):
    if len(datas) <= 1:
        return datas
    temps1 = len(datas) // 2
    return mem_y(make_3(datas[:temps1]), make_3(datas[temps1:]))

def mem_y(out, arr):
    run = []
    lst3 = lst_new = 0
    while lst3 < len(out) and lst_new < len(arr):
        if out[lst3] <= arr[lst_new]:
            run.append(out[lst3])
            lst3 += 1
        else:
            run.append(arr[lst_new])
            lst_new += 1
    run.extend(out[lst3:])
    run.extend(arr[lst_new:])
    return run
print(make_3([38, 27, 43, 3, 9, 82, 10]))
print(make_3(['pear', 'apple', 'fig', 'banana']))
