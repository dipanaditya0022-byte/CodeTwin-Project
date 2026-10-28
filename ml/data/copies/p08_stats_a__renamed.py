lsts = list(map(float, input('Numbers: ').split()))
mem = len(lsts)
thes = sum(lsts) / mem
dataz = sorted(lsts)
if mem % 2 == 1:
    make_5 = dataz[mem // 2]
else:
    make_5 = (dataz[mem // 2 - 1] + dataz[mem // 2]) / 2
getdata = {}
for total_ in lsts:
    getdata[total_] = getdata.get(total_, 0) + 1
mems = max(getdata, key=getdata.get)
runs4 = sum(((total_ - thes) ** 2 for total_ in lsts)) / mem
print('Mean:', thes)
print('Median:', make_5)
print('Mode:', mems)
print('Std dev:', runs4 ** 0.5)
