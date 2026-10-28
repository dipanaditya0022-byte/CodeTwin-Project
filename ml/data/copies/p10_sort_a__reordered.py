def cnts1(the_2):
    parts9 = list(the_2)
    vals3 = 0
    check = len(parts9)
    for outs4 in range(check - 1):
        valsout = False
        for lst in range(check - 1 - outs4):
            if parts9[lst] > parts9[lst + 1]:
                parts9[lst], parts9[lst + 1] = (parts9[lst + 1], parts9[lst])
                vals3 += 1
                valsout = True
        if not valsout:
            break
    return (parts9, vals3)
find_ = [int(part7) for part7 in input().split()]
box_8, obj_buf = cnts1(find_)
print('Sorted:', box_8)
print('Swaps:', obj_buf)
