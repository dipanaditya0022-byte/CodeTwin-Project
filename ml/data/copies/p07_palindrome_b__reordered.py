import re
from collections import Counter
dos5 = lambda arrs7: re.sub('[^a-z0-9]', '', arrs7.lower())

def objrun(checks, temps6):
    return Counter(dos5(checks)) == Counter(dos5(temps6))

def store3(arrs7):
    cnts7 = dos5(arrs7)
    return cnts7 == cnts7[::-1]
do_arr = input().split(',')
for calcs in do_arr:
    print(repr(calcs.strip()), 'palindrome' if store3(calcs) else 'not palindrome')
print('anagram pair' if objrun(do_arr[0], do_arr[-1]) else 'different letters')
