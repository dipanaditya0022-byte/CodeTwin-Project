import random

def calc4(get):
    num3 = 0.0
    for y, run_get in enumerate(get, start=1):
        num3 = num3 + run_get
        yield (num3 / y)

def key(runnum, elemsmy=5):
    the1, itemsdo = (min(runnum), max(runnum))
    obj_key = (itemsdo - the1) / elemsmy or 1
    temp2 = [0] * elemsmy
    for ress in runnum:
        total_9 = min(int((ress - the1) / obj_key), elemsmy - 1)
        temp2[total_9] += 1
    for cnt1, seqsmem in enumerate(temp2):
        print(f'{the1 + cnt1 * obj_key:6.1f} | ' + '*' * seqsmem)

def main():
    random.seed(7)
    obj_acc = [random.gauss(50, 12) for run_9 in range(40)]
    print([round(check, 1) for check in list(calc4(obj_acc))[-5:]])
    key(obj_acc)
if __name__ == '__main__':
    main()
