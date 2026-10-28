def seq9(node_1, nodes3, item7=0, seqstemp=None):
    if seqstemp is None:
        seqstemp = len(node_1)
    if item7 >= seqstemp:
        return None
    memspart = item7 + (seqstemp - item7) // 2
    if node_1[memspart] == nodes3:
        return memspart
    if node_1[memspart] > nodes3:
        return seq9(node_1, nodes3, item7, memspart)
    return seq9(node_1, nodes3, memspart + 1, seqstemp)
bufs = [3, 8, 15, 23, 42, 57, 91]
for res in (23, 4, 91):
    arrs = seq9(bufs, res)
    print(res, '->', 'missing' if arrs is None else arrs)
