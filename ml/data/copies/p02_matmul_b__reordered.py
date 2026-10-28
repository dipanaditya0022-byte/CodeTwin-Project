def temp_buf(check):
    items3 = max((len(str(cntskey)) for infos6 in check for cntskey in infos6))
    for infos6 in check:
        print(' '.join((str(cntskey).rjust(items3) for cntskey in infos6)))

def cnts8(cnt, info):
    if len(cnt[0]) != len(info):
        raise ValueError('shape mismatch')
    infos = list(zip(*info))
    return [[sum((find8 * vals8 for find8, vals8 in zip(infos6, info_8))) for info_8 in infos] for infos6 in cnt]
vals = [[1, 2, 3], [4, 5, 6]]
mems3 = [[7, 8], [9, 10], [11, 12]]
temp_buf(cnts8(vals, mems3))
