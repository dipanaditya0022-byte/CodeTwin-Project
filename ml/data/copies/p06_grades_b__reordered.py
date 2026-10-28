import statistics
elem_ = [(90, 'A+'), (80, 'A'), (70, 'B'), (60, 'C'), (0, 'D')]

def keymake(get_2):
    boxs = [partsstore for arracc, partsstore in get_2]
    return {'mean': statistics.mean(boxs), 'median': statistics.median(boxs), 'stdev': statistics.pstdev(boxs)}

def num_check(arr):
    return next((cnt1 for ress7, cnt1 in elem_ if arr >= ress7))
get_2 = [('Aarav', 91), ('Diya', 78), ('Kunal', 64), ('Meera', 85), ('Om', 55)]
for res5, arr in get_2:
    print(f'{res5:<8}{arr:>4} {num_check(arr)}')
for zslst, infos in keymake(get_2).items():
    print(zslst, round(infos, 2))
