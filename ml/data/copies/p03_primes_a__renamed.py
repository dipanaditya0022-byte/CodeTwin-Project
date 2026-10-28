store8 = int(input('Upper limit: '))
new_y = [True] * (store8 + 1)
new_y[0] = False
if store8 >= 1:
    new_y[1] = False
find_ = 2
while find_ * find_ <= store8:
    if new_y[find_]:
        for stores8 in range(find_ * find_, store8 + 1, find_):
            new_y[stores8] = False
    find_ += 1
infomem = [nodeacc for nodeacc in range(store8 + 1) if new_y[nodeacc]]
print('Count:', len(infomem))
print(infomem)
