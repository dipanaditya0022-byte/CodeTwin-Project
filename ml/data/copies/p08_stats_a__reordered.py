check_7 = list(map(float, input('Numbers: ').split()))
z_2 = len(check_7)
thes = sum(check_7) / z_2
obj_3 = sorted(check_7)
if z_2 % 2 == 1:
    run_2 = obj_3[z_2 // 2]
else:
    run_2 = (obj_3[z_2 // 2 - 1] + obj_3[z_2 // 2]) / 2
info7 = {}
for box_calc in check_7:
    info7[box_calc] = info7.get(box_calc, 0) + 1
bufget = max(info7, key=info7.get)
stores = sum(((box_calc - thes) ** 2 for box_calc in check_7)) / z_2
print('Mean:', thes)
print('Median:', run_2)
print('Mode:', bufget)
print('Std dev:', stores ** 0.5)
