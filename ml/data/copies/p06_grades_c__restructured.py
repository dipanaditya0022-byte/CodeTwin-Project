import csv
import io
elems = 'roll,name,maths,physics,chemistry\n1,Ananya,88,92,79\n2,Rohan,45,60,52\n3,Sara,73,68,81\n'

def seqkey(seq7):
    return list(csv.DictReader(io.StringIO(seq7)))

def itembox(lstsfind):
    do = ['maths', 'physics', 'chemistry']
    return sum((int(lstsfind[info_6]) for info_6 in do)) / len(do)
mem_1 = seqkey(elems)
mem_1.sort(key=itembox, reverse=True)
val_ = 1
for lstsfind in mem_1:
    total_box = itembox(lstsfind)
    lsts7 = 'PASS' if total_box >= 50 else 'FAIL'
    print(val_, lstsfind['name'], f'{total_box:.1f}%', lsts7)
    val_ = val_ + 1
