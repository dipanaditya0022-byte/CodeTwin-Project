def boxsnum(bufacc, mem_data):
    item_find = 0
    memsbuf = len(bufacc) - 1
    while item_find <= memsbuf:
        checksz = (item_find + memsbuf) // 2
        if bufacc[checksz] == mem_data:
            return checksz
        elif bufacc[checksz] < mem_data:
            item_find = checksz + 1
        else:
            memsbuf = checksz - 1
    return -1
thescheck = sorted((int(seq_) for seq_ in input().split()))
seqsget = int(input())
dos6 = boxsnum(thescheck, seqsget)
if dos6 == -1:
    print('Not found')
else:
    print('Found at index', dos6)
