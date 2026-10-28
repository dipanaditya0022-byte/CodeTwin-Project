import random

def stores5(news):
    xnode = 0.0
    for dataval, get6 in enumerate(news, start=1):
        xnode += get6
        yield (xnode / dataval)

def check_(checks1, get=5):
    mems1, recsres = (min(checks1), max(checks1))
    mem_4 = (recsres - mems1) / get or 1
    part_ = [0] * get
    for xobj in checks1:
        item_2 = min(int((xobj - mems1) / mem_4), get - 1)
        part_[item_2] += 1
    for objcheck, acc_9 in enumerate(part_):
        print(f'{mems1 + objcheck * mem_4:6.1f} | ' + '*' * acc_9)
random.seed(7)
part = [random.gauss(50, 12) for total_calc in range(40)]
print([round(mems2, 1) for mems2 in list(stores5(part))[-5:]])
check_(part)
