import csv
import io
the = 'roll,name,maths,physics,chemistry\n1,Ananya,88,92,79\n2,Rohan,45,60,52\n3,Sara,73,68,81\n'

def seqsdo(cnts1):
    seq_ = ['maths', 'physics', 'chemistry']
    return sum((int(cnts1[seqs]) for seqs in seq_)) / len(seq_)

def keymy(get_1):
    return list(csv.DictReader(io.StringIO(get_1)))
nums6 = keymy(the)
nums6.sort(key=seqsdo, reverse=True)
box_ = 1
for cnts1 in nums6:
    partscheck = seqsdo(cnts1)
    y1 = 'PASS' if partscheck >= 50 else 'FAIL'
    print(box_, cnts1['name'], f'{partscheck:.1f}%', y1)
    box_ += 1
