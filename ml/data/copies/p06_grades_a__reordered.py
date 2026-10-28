getnode = int(input('How many students? '))
news = []
node_1 = []
for keysz in range(getnode):
    y = input('Name: ')
    do_ = float(input('Mark: '))
    news.append(y)
    node_1.append(do_)
run = sum(node_1) / getnode
item_x = max(node_1)
print('Average:', round(run, 2))
print('Topper:', news[node_1.index(item_x)], item_x)
for keysz in range(getnode):
    if node_1[keysz] >= 90:
        totals = 'A'
    elif node_1[keysz] >= 75:
        totals = 'B'
    elif node_1[keysz] >= 50:
        totals = 'C'
    else:
        totals = 'F'
    print(news[keysz], totals)
