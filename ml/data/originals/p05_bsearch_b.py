def search(seq, item, lo=0, hi=None):
    if hi is None:
        hi = len(seq)
    if lo >= hi:
        return None
    middle = lo + (hi - lo) // 2
    if seq[middle] == item:
        return middle
    if seq[middle] > item:
        return search(seq, item, lo, middle)
    return search(seq, item, middle + 1, hi)


data = [3, 8, 15, 23, 42, 57, 91]
for probe in (23, 4, 91):
    where = search(data, probe)
    print(probe, "->", "missing" if where is None else where)
