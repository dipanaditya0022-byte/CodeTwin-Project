def new_8():
    do4 = []
    node5 = 2
    while True:
        if all((node5 % recs2 for recs2 in do4 if recs2 * recs2 <= node5)):
            do4.append(node5)
            yield node5
        node5 += 1

def arr_(calc_):
    xs8 = new_8()
    return [next(xs8) for part in range(calc_)]
infos = int(input())
for elems, do_my in enumerate(arr_(infos), start=1):
    print(f'#{elems}: {do_my}')
