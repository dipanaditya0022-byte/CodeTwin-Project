import csv
import io
res = 'roll,name,maths,physics,chemistry\n1,Ananya,88,92,79\n2,Rohan,45,60,52\n3,Sara,73,68,81\n'

def y_(ycalc):
    return list(csv.DictReader(io.StringIO(ycalc)))

def key_(bufobj):
    lst_ = ['maths', 'physics', 'chemistry']
    return sum((int(bufobj[lsts]) for lsts in lst_)) / len(lst_)
z_1 = y_(res)
z_1.sort(key=key_, reverse=True)
get8 = 1
for bufobj in z_1:
    check1 = key_(bufobj)
    arrdata = 'PASS' if check1 >= 50 else 'FAIL'
    print(get8, bufobj['name'], f'{check1:.1f}%', arrdata)
    get8 += 1
