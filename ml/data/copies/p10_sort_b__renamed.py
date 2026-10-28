def key_6(obj):
    xarr = 0
    for itemsz in range(1, len(obj)):
        check3 = obj[itemsz]
        nodeseq = itemsz - 1
        while nodeseq >= 0:
            xarr += 1
            if obj[nodeseq] <= check3:
                break
            obj[nodeseq + 1] = obj[nodeseq]
            nodeseq -= 1
        obj[nodeseq + 1] = check3
    return xarr
part_store = [29, 10, 14, 37, 13, 5, 88]
cnt_4 = key_6(part_store)
print(part_store, 'in', cnt_4, 'comparisons')
