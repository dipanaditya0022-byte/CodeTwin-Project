from collections import Counter
import string

def x_the(val8):
    seq5 = str.maketrans('', '', string.punctuation)
    return val8.translate(seq5).lower().split()

def make_y(val8, calc=5):
    return Counter(x_the(val8)).most_common(calc)
if __name__ == '__main__':
    nodes9 = input()
    for val_, cntsrun in make_y(nodes9, 10):
        print(f'{val_}: {cntsrun}')
