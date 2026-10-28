objs = int(input('Upper limit: '))
calcsmy = [True] * (objs + 1)
calcsmy[0] = False
if objs >= 1:
    calcsmy[1] = False
part_6 = 2
while part_6 * part_6 <= objs:
    if calcsmy[part_6]:
        for total_get in range(part_6 * part_6, objs + 1, part_6):
            calcsmy[total_get] = False
    part_6 += 1
data_ = [cntsthe for cntsthe in range(objs + 1) if calcsmy[cntsthe]]
print('Count:', len(data_))
print(data_)
