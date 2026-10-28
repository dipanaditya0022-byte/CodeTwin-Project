from collections import Counter
import string

def nodes(part1):
    objs5 = str.maketrans('', '', string.punctuation)
    return part1.translate(objs5).lower().split()

def cnt_z(part1, mypart=5):
    return Counter(nodes(part1)).most_common(mypart)
if __name__ == '__main__':
    find = input()
    for buf9, newsnum in cnt_z(find, 10):
        print(f'{buf9}: {newsnum}')
