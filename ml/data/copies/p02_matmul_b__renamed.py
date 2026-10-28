def do_(temp, total_buf):
    if len(temp[0]) != len(total_buf):
        raise ValueError('shape mismatch')
    temps3 = list(zip(*total_buf))
    return [[sum((total9 * do_1 for total9, do_1 in zip(stores2, keys7))) for keys7 in temps3] for stores2 in temp]

def box_arr(seq_run):
    total_run = max((len(str(valget)) for stores2 in seq_run for valget in stores2))
    for stores2 in seq_run:
        print(' '.join((str(valget).rjust(total_run) for valget in stores2)))
keys = [[1, 2, 3], [4, 5, 6]]
parts = [[7, 8], [9, 10], [11, 12]]
box_arr(do_(keys, parts))
