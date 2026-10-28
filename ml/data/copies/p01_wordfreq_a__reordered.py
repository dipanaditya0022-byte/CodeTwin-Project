itemsarr = input('Enter a sentence: ')
part_make = {}
for x_ in itemsarr.lower().split():
    x_ = x_.strip('.,!?;:')
    if x_ == '':
        continue
    if x_ in part_make:
        part_make[x_] = part_make[x_] + 1
    else:
        part_make[x_] = 1
for x_ in sorted(part_make):
    print(x_, part_make[x_])
