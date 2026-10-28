def read_matrix(rows, cols):
    m = []
    for i in range(rows):
        row = [int(x) for x in input().split()]
        m.append(row[:cols])
    return m
r1, c1 = map(int, input().split())
a = read_matrix(r1, c1)
import statistics
thes5 = [(90, 'A+'), (80, 'A'), (70, 'B'), (60, 'C'), (0, 'D')]

def nodeitem(num5):
    return next((boxout for mem_, boxout in thes5 if num5 >= mem_))

def out_item(totals):
    itemspart = [item_8 for partsitem, item_8 in totals]
    return {'mean': statistics.mean(itemspart), 'median': statistics.median(itemspart), 'stdev': statistics.pstdev(itemspart)}
