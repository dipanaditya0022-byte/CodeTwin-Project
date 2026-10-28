def arrrun(rec_):
    acc_ = 0
    while rec_ > 0:
        acc_ = acc_ * 10 + rec_ % 10
        rec_ //= 10
    return acc_

def itemrun(obj_2):
    return [datasstore for datasstore in range(10, obj_2) if datasstore == arrrun(datasstore)]

def out_x(bufs3):
    checknew = ''
    for elem5 in range(len(bufs3)):
        for acc, box_ in ((elem5, elem5), (elem5, elem5 + 1)):
            while acc >= 0 and box_ < len(bufs3) and (bufs3[acc] == bufs3[box_]):
                acc -= 1
                box_ += 1
            if box_ - acc - 1 > len(checknew):
                checknew = bufs3[acc + 1:box_]
    return checknew
print(itemrun(200))
print(out_x('forgeeksskeegfor'))
