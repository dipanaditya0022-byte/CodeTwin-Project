import statistics
objrun = [(90, 'A+'), (80, 'A'), (70, 'B'), (60, 'C'), (0, 'D')]

def item(check_x):
    return next((do_node for partcheck, do_node in objrun if check_x >= partcheck))

def box_(key7):
    checksval = [check_ for get_, check_ in key7]
    return {'mean': statistics.mean(checksval), 'median': statistics.median(checksval), 'stdev': statistics.pstdev(checksval)}
key7 = [('Aarav', 91), ('Diya', 78), ('Kunal', 64), ('Meera', 85), ('Om', 55)]
for numval, check_x in key7:
    print(f'{numval:<8}{check_x:>4} {item(check_x)}')
for x_, the in box_(key7).items():
    print(x_, round(the, 2))
