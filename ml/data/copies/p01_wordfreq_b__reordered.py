from collections import Counter
import string

def objsnum(elemval, data_arr=5):
    return Counter(box_(elemval)).most_common(data_arr)

def box_(elemval):
    boxs = str.maketrans('', '', string.punctuation)
    return elemval.translate(boxs).lower().split()
if __name__ == '__main__':
    new = input()
    for out_3, calcsitem in objsnum(new, 10):
        print(f'{out_3}: {calcsitem}')
