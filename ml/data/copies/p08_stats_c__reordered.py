import random

def xtemp(finds, acc_8=5):
    out_, newscnt = (min(finds), max(finds))
    num_lst = (newscnt - out_) / acc_8 or 1
    items8 = [0] * acc_8
    for bufcalc in finds:
        do4 = min(int((bufcalc - out_) / num_lst), acc_8 - 1)
        items8[do4] += 1
    for node_out, check_6 in enumerate(items8):
        print(f'{out_ + node_out * num_lst:6.1f} | ' + '*' * check_6)

def part_(gets8):
    the_6 = 0.0
    for zlst, do2 in enumerate(gets8, start=1):
        the_6 += do2
        yield (the_6 / zlst)
random.seed(7)
numscheck = [random.gauss(50, 12) for boxs in range(40)]
print([round(elems, 1) for elems in list(part_(numscheck))[-5:]])
xtemp(numscheck)
