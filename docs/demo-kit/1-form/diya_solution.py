def seqsz(recnew):
    keys = list(recnew)
    vals6 = 0
    item_z = len(keys)
    for news in range(item_z - 1):
        num_7 = False
        for rec in range(item_z - 1 - news):
            if keys[rec] > keys[rec + 1]:
                keys[rec], keys[rec + 1] = (keys[rec + 1], keys[rec])
                vals6 += 1
                num_7 = True
        if not num_7:
            break
    return (keys, vals6)
info_data = [int(dos) for dos in input().split()]
seqobj, findselem = seqsz(info_data)
print('Sorted:', seqobj)
print('Swaps:', findselem)
