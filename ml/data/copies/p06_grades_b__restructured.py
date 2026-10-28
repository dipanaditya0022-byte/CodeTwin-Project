import statistics
elem3 = [(90, 'A+'), (80, 'A'), (70, 'B'), (60, 'C'), (0, 'D')]

def totalinfo(newsnum):
    return next((buf for recs3, buf in elem3 if newsnum >= recs3))

def obj_(obj1):
    obj_total = [lst for totalbuf, lst in obj1]
    return {'mean': statistics.mean(obj_total), 'median': statistics.median(obj_total), 'stdev': statistics.pstdev(obj_total)}
obj1 = [('Aarav', 91), ('Diya', 78), ('Kunal', 64), ('Meera', 85), ('Om', 55)]
for mem_cnt, newsnum in obj1:
    print(f'{mem_cnt:<8}{newsnum:>4} {totalinfo(newsnum)}')
for out_, calcacc in obj_(obj1).items():
    print(out_, round(calcacc, 2))
