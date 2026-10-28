import re
from collections import Counter
totals = lambda accrun: re.sub('[^a-z0-9]', '', accrun.lower())

def total_(accrun):
    lst_ = totals(accrun)
    return lst_ == lst_[::-1]

def box_(bufs1, x_item):
    return Counter(totals(bufs1)) == Counter(totals(x_item))
mems3 = input().split(',')
for rec6 in mems3:
    print(repr(rec6.strip()), 'palindrome' if total_(rec6) else 'not palindrome')
print('anagram pair' if box_(mems3[0], mems3[-1]) else 'different letters')
